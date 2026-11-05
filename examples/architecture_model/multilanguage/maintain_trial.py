"""Reproduce explicit baseline adoption and one-root maintenance through the CLI."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    args = parser.parse_args()
    output = args.model_dir.resolve()
    target = args.target.resolve()
    model_file = output / "model.json"

    def invoke(label: str, arguments: list[str]) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "architecture_model", *arguments], capture_output=True, text=True, timeout=210
        )
        (output / f"{label}.response.json").write_text(result.stdout, encoding="utf-8")
        (output / f"{label}.stderr.log").write_text(result.stderr, encoding="utf-8")
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout)["result"]

    prefix = ["model", "--file", str(model_file)]
    old = json.loads(model_file.read_text(encoding="utf-8"))
    (output / "revision-2.json").write_text(json.dumps(old, indent=2) + "\n", encoding="utf-8")
    original_definitions = {name: old[name] for name in ("components", "relations", "scenarios")}
    operations = []
    snapshots = {}
    for root in ("frontend", "backend"):
        destination = output / f"{root}-baseline.facts.json"
        invoke(
            root + "-baseline-export",
            [
                "facts",
                "export",
                "--repo",
                str(target / root),
                "--project-id",
                old["project"]["id"],
                "--source-root-id",
                root,
                "--tools",
                str(args.tools.resolve()),
                "--output",
                str(destination),
            ],
        )
        snapshot = json.loads(destination.read_text(encoding="utf-8"))
        snapshots[root] = snapshot
        if snapshot["id"] not in {item["id"] for item in old["facts"]}:
            operations.append({"action": "create", "collection": "facts", "id": snapshot["id"], "value": snapshot})
    for binding in old["bindings"]:
        original = next(item for item in old["facts"] if item["id"] == binding["snapshot_id"])
        snapshot = snapshots[original["source_root_id"]]
        if snapshot["id"] == binding["snapshot_id"]:
            continue
        location = binding["location"]
        catalog = snapshot["symbols"] if location["symbol"] else snapshot["file_locations"]
        key = f"{location['path']}|{location['symbol']}" if location["symbol"] else location["path"]
        assert catalog[key] == location and snapshot["source"]["digest"] == binding["source_version"]
        history = [
            *binding["history"],
            {name: binding[name] for name in ("snapshot_id", "source_version", "location")}
            | {"reason": "Explicitly adopt final exporter descriptor after inspecting unchanged source bytes"},
        ]
        operations.append(
            {
                "action": "update",
                "collection": "bindings",
                "id": binding["id"],
                "value": {"snapshot_id": snapshot["id"], "history": history},
            }
        )
    if operations:
        patch = {
            "author": "M5 external Agent",
            "summary": "Adopt final native exporter metadata with unchanged source evidence",
            "operations": operations,
        }
        patch_file = output / "adopt-baseline.patch.json"
        patch_file.write_text(json.dumps(patch, indent=2) + "\n", encoding="utf-8")
        invoke("adopt-baseline-validate", prefix + ["validate", "--patch", str(patch_file)])
        invoke(
            "adopt-baseline-apply",
            prefix + ["apply", "--patch", str(patch_file), "--expected-revision", str(old["revision"])],
        )
    baseline = json.loads(model_file.read_text(encoding="utf-8"))
    backend_before = [
        item
        for item in baseline["bindings"]
        if next(fact for fact in baseline["facts"] if fact["id"] == item["snapshot_id"])["source_root_id"] == "backend"
    ]
    changed_file = target / "frontend/src/utils.ts"
    before = changed_file.read_bytes()
    assert b'"notes.txt"' in before
    changed_file.write_bytes(before.replace(b'"notes.txt"', b'"notes.txt".trim()'))
    (output / "frontend-source-change.patch").write_text(
        'Change only frontend/src/utils.ts: openDocument normalizes the configured path using "notes.txt".trim().\n',
        encoding="utf-8",
    )
    changed_facts = output / "frontend-changed.facts.json"
    invoke(
        "frontend-changed-export",
        [
            "facts",
            "export",
            "--repo",
            str(target / "frontend"),
            "--project-id",
            old["project"]["id"],
            "--source-root-id",
            "frontend",
            "--tools",
            str(args.tools.resolve()),
            "--output",
            str(changed_facts),
        ],
    )
    report = invoke("maintenance-preview", prefix + ["maintenance-preview", "--facts", str(changed_facts)])
    assert {item["binding_id"] for item in report["observations"]} == {"open", "preview", "invoke"}
    assert all(item["disposition"] == "changed" for item in report["observations"])
    invoke(
        "maintenance-refresh",
        prefix
        + [
            "maintenance-refresh",
            "--facts",
            str(changed_facts),
            "--expected-revision",
            str(baseline["revision"]),
            "--token",
            report["token"],
            "--author",
            "M5 external Agent",
        ],
    )
    pending = invoke("maintenance-pending", prefix + ["maintenance"])
    assert all("read-file-ipc" in item["relation_ids"] for item in pending["observations"])
    assert all(set(item["scenario_ids"]) == {"open-document", "preview-document"} for item in pending["observations"])
    for index, item in enumerate(report["observations"]):
        current = json.loads(model_file.read_text(encoding="utf-8"))
        choice = item["candidates"][0]
        invoke(
            f"rebind-{index}",
            prefix
            + [
                "maintenance-rebind",
                "--item",
                item["id"],
                "--candidate",
                choice["key"],
                "--expected-revision",
                str(current["revision"]),
                "--author",
                "M5 external Agent",
                "--reason",
                "Inspected frontend path edit; preserve both business explanations and candidate IPC assumptions",
            ],
        )
        review = {
            "author": "M5 external Agent",
            "reason": "Inspected path normalization: trimming the configured notes.txt literal preserves the same input and IPC operation/payload. Candidate contract remains conditional; this review proves no runtime execution.",
            "outcome": "confirmed",
            "source_version": item["target_source_version"],
            "operations": [],
        }
        review_file = output / f"review-{index}.json"
        review_file.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
        current = json.loads(model_file.read_text(encoding="utf-8"))
        invoke(
            f"resolve-{index}",
            prefix
            + [
                "maintenance-resolve",
                "--item",
                item["id"],
                "--review",
                str(review_file),
                "--expected-revision",
                str(current["revision"]),
            ],
        )
    final = json.loads(model_file.read_text(encoding="utf-8"))
    assert all(final[name] == value for name, value in original_definitions.items())
    assert [
        item for item in final["bindings"] if item["id"] in {entry["id"] for entry in backend_before}
    ] == backend_before
    assert all(next(item for item in final["facts"] if item["id"] == fact["id"]) == fact for fact in old["facts"])
    result = {
        "old_revision": old["revision"],
        "final_revision": final["revision"],
        "backend_bindings_unchanged": True,
        "old_catalogs_unchanged": True,
        "definitions_unchanged": True,
        "granularity": "whole containing file, so preview and invoke also reviewed",
        "pending": invoke("maintenance-final", prefix + ["maintenance"]),
    }
    (output / "maintenance-check.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    source_map = output / "current-source-map.json"
    source_map.write_text(json.dumps({root: str(target / root) for root in ("frontend", "backend")}), encoding="utf-8")
    invoke(
        "final-export",
        prefix + ["export-html", "--output", str(output / "index.html"), "--source-map", str(source_map)],
    )
    print(json.dumps({"revision": final["revision"], "current_pending": result["pending"]["current_pending_ids"]}))


if __name__ == "__main__":
    main()
