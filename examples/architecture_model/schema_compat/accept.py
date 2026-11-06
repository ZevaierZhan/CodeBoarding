"""Run isolated compatibility acceptance; all inputs and outputs stay in the supplied private directory."""

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from architecture_model.store import load_json
from architecture_model.validation import validate_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--source-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    original = args.model.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original_bytes = original.read_bytes()
    checksum = hashlib.sha256(original_bytes).hexdigest()
    copied = output / "model.json"
    shutil.copyfile(original, copied)
    raw = load_json(copied)
    before = validate_model(raw).model_dump()
    assert validate_model(before).model_dump() == before
    prefix = [sys.executable, "-m", "architecture_model", "model", "--file", str(copied)]

    def cli(name: str, *arguments: str) -> dict:
        with (output / f"{name}.json").open("xb") as stdout, (output / f"{name}.stderr.log").open("xb") as stderr:
            result = subprocess.run([*prefix, *arguments], stdout=stdout, stderr=stderr, timeout=1800)
        envelope = load_json(output / f"{name}.json")
        if not isinstance(envelope, dict):
            raise RuntimeError(f"Invalid CLI envelope: {name}")
        if result.returncode or not envelope["ok"]:
            raise RuntimeError(f"Acceptance command failed: {name}; inspect private output")
        print(name, "passed", flush=True)
        return envelope["result"]

    cli("validate", "validate")
    read = cli("read", "read")
    assert read["model_id"] == before["id"] and read["revision"] == before["revision"]
    for collection in (
        "facts",
        "bindings",
        "components",
        "relations",
        "scenarios",
        "opinions",
        "verifications",
        "revisions",
    ):
        assert read["model"][collection] == before[collection]
    maintenance = cli("maintenance", "maintenance")
    cli(
        "coverage",
        "coverage-report",
        "--source-map",
        str(args.source_map.resolve()),
        "--output",
        str(output / "coverage-report.json"),
    )
    cli("html", "export-html", "--source-map", str(args.source_map.resolve()), "--output", str(output / "before.html"))
    assert copied.read_bytes() == original_bytes
    scenario = next(item for item in before["scenarios"] if any(step.get("facet_checks") for step in item["steps"]))
    steps = deepcopy(scenario["steps"])
    step = next(item for item in steps if item.get("facet_checks"))
    label = next(iter(step["facet_checks"]))
    step["facet_checks"][
        label
    ] += " [Compatibility rehearsal: authored interpretation; execution records remain separate.]"
    amendment = {
        "author": "compatibility-acceptance",
        "summary": "Clarify one existing analysis question in an isolated copy",
        "operations": [
            {"action": "update", "collection": "scenarios", "id": scenario["id"], "value": {"steps": steps}}
        ],
    }
    patch = output / "patch.json"
    patch.write_text(json.dumps(amendment, ensure_ascii=False, indent=2), encoding="utf-8")
    cli("validate-patch", "validate", "--patch", str(patch))
    difference = cli("diff", "diff", "--patch", str(patch))
    assert scenario["id"] in difference["diff"]["scenario_ids"]
    cli("apply", "apply", "--patch", str(patch), "--expected-revision", str(before["revision"]))
    after = validate_model(load_json(copied)).model_dump()
    assert after["id"] == before["id"] and after["revision"] == before["revision"] + 1
    for collection in ("facts", "bindings", "components", "relations", "opinions", "verifications"):
        assert after[collection] == before[collection]
    assert after["revisions"][:-1] == before["revisions"]
    assert after["maintenance"][: len(before["maintenance"])] == before["maintenance"]
    expected = deepcopy(before["scenarios"])
    next(item for item in expected if item["id"] == scenario["id"])["steps"] = steps
    assert after["scenarios"] == expected
    assert after.get("maintenance_targets", {}) == before.get("maintenance_targets", {})
    assert after["maintenance_target_snapshot_id"] == before["maintenance_target_snapshot_id"]
    cli("validate-after", "validate")
    cli(
        "html-after",
        "export-html",
        "--source-map",
        str(args.source_map.resolve()),
        "--output",
        str(output / "after.html"),
    )
    assert original.read_bytes() == original_bytes
    summary = {
        "model_id": before["id"],
        "revision_before": before["revision"],
        "revision_after": after["revision"],
        "original_sha256": checksum,
        "original_unchanged": True,
        "round_trip": True,
        "historical_records_preserved": True,
        "pending_before": len(maintenance["pending_ids"]),
        "current_pending_before": len(maintenance["current_pending_ids"]),
        "maintenance_before": len(before["maintenance"]),
        "maintenance_after": len(after["maintenance"]),
        "format_valid": True,
        "runtime_behavior_verified": False,
    }
    (output / "acceptance.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Isolated acceptance complete", flush=True)


if __name__ == "__main__":
    main()
