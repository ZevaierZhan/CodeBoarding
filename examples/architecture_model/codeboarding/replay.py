"""Replay authored patches and explicit maintenance decisions on a fresh model."""

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS = Path(__file__).resolve().parent


def run(output: Path, node: Path, pyright: Path, tokei: Path) -> None:
    scope = json.loads((ARTIFACTS / "scope.json").read_text(encoding="utf-8"))
    source_manifest = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "architecture_model").glob("*.py")
    }
    if source_manifest != scope["included"]:
        raise ValueError(
            "Product source differs from the recorded trial; review the authored explanations before replay"
        )
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    (source / "architecture_model").mkdir(parents=True)
    for path in (ROOT / "architecture_model").glob("*.py"):
        shutil.copyfile(path, source / "architecture_model" / path.name)
    journal: list[dict] = []

    def command(*arguments: object) -> dict:
        argv = [sys.executable, "-m", "architecture_model", *map(str, arguments)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=210)
        envelope = json.loads(result.stdout)
        journal.append(
            {
                "argv": argv,
                "exit_code": result.returncode,
                "response_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            }
        )
        write(output / "commands.json", journal)
        if result.returncode or not envelope["ok"]:
            raise RuntimeError(envelope)
        return envelope["result"]

    tools = ("--node", node, "--pyright", pyright, "--tokei", tokei)
    before_path = output / "facts-before.json"
    command(
        "facts",
        "export",
        "--repo",
        source,
        "--project-id",
        "codeboarding-architecture-model",
        "--output",
        before_path,
        *tools,
    )
    facts = json.loads(before_path.read_text(encoding="utf-8"))
    prefix = ("model", "--file", output / "model.json")
    command(*prefix, "init", "--project", ARTIFACTS / "project.json", "--author", "replay-agent")

    def apply(path: Path) -> None:
        revision = command(*prefix, "read")["revision"]
        command(*prefix, "validate", "--patch", path)
        command(*prefix, "diff", "--patch", path)
        command(*prefix, "apply", "--patch", path, "--expected-revision", revision)

    manifest = json.loads((ARTIFACTS / "replay.json").read_text(encoding="utf-8"))
    for name in manifest["patches"]:
        patch = json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))
        for operation in patch["operations"]:
            if operation["collection"] == "facts":
                operation.update(id=facts["id"], value=facts)
            elif operation["collection"] == "bindings":
                binding = operation["value"]
                old = binding["location"]
                key = f"{old['path']}|{old['symbol']}"
                binding.update(
                    snapshot_id=facts["id"], source_version=facts["source"]["digest"], location=facts["symbols"][key]
                )
            elif operation["collection"] == "verifications":
                verification = operation["value"]
                verification["source_version"] = facts["source"]["digest"]
                if verification["status"] == "executed":
                    arguments = manifest["verification_commands"][operation["id"]]
                    if arguments != ["validate"]:
                        raise ValueError("This replay supports only the recorded model-structure verification")
                    checked_model = command(*prefix, "read")
                    checked = command(*prefix, *arguments)
                    verification.update(
                        command=json.dumps([sys.executable, "-m", "architecture_model", *map(str, prefix), *arguments]),
                        environment=f"{platform.platform()}; Python {platform.python_version()}; replay venv",
                        inputs=f"Model {checked_model['model_id']}, revision {checked_model['revision']}; complete persisted JSON; structural validation only, not business execution.",
                        executor="replay-agent",
                        executed_at=datetime.now(timezone.utc).isoformat(),
                        exit_code=0,
                        result=json.dumps(checked),
                    )
        path = output / name
        write(path, patch)
        apply(path)
    write(output / "before-source-change.model.json", command(*prefix, "read")["model"])
    command(*prefix, "export-html", "--output", output / "before-source-change.html", "--source-root", source)

    change = manifest["source_change"]
    target = (source / change["path"]).resolve()
    if not target.is_relative_to(source.resolve()):
        raise ValueError("Controlled source change must stay inside the fresh source copy")
    original = target.read_bytes()
    if original.count(change["before"].encode()) != 1:
        raise ValueError("Source change marker no longer matches exactly once; inspect the new implementation")
    target.write_bytes(original.replace(change["before"].encode(), change["after"].encode()))
    after_path = output / "facts-after.json"
    command("facts", "export", "--repo", source, "--project-id", facts["project_id"], "--output", after_path, *tools)
    after = json.loads(after_path.read_text(encoding="utf-8"))
    preview = command(*prefix, "maintenance-preview", "--facts", after_path)
    write(output / "maintenance-preview.json", preview)
    command(
        *prefix,
        "maintenance-refresh",
        "--facts",
        after_path,
        "--token",
        preview["token"],
        "--author",
        "replay-agent",
        "--expected-revision",
        preview["revision"],
    )
    for index, action in enumerate(manifest["maintenance_actions"]):
        if action["command"] == "patch":
            apply(ARTIFACTS / action["file"])
            continue
        read = command(*prefix, "read")
        report = command(*prefix, "maintenance", "--binding", action["binding"])
        items = [
            item
            for item in report["observations"]
            if item["id"] in report["current_coverage_ids"] and item["target_snapshot_id"] == after["id"]
        ]
        if len(items) != 1:
            raise ValueError("Expected one current interpretation context for the selected source comparison")
        item = items[0]
        if action["command"] == "rebind":
            command(
                *prefix,
                "maintenance-rebind",
                "--item",
                item["id"],
                "--candidate",
                action["candidate"],
                "--author",
                "replay-agent",
                "--reason",
                action["reason"],
                "--expected-revision",
                read["revision"],
            )
        elif action["command"] == "resolve":
            review = dict(action["review"], source_version=after["source"]["digest"])
            review_path = output / f"review-{index}.json"
            write(review_path, review)
            command(
                *prefix,
                "maintenance-resolve",
                "--item",
                item["id"],
                "--review",
                review_path,
                "--expected-revision",
                read["revision"],
            )
        else:
            raise ValueError(f"Unknown maintenance action: {action['command']}")
    final = command(*prefix, "read")["model"]
    write(output / "final-read.json", final)
    write(output / "maintenance-final.json", command(*prefix, "maintenance"))
    command(*prefix, "validate")
    command(*prefix, "export-html", "--output", output / "index.html", "--source-root", source)
    if final["revision"] != manifest["expected_revision"]:
        raise ValueError("Replay revision differs from the recorded sequence")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "node", "pyright", "tokei"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.node.resolve(), args.pyright.resolve(), args.tokei.resolve())


if __name__ == "__main__":
    main()
