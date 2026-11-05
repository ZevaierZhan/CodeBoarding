"""Prepare a separated real-source fixture and explicitly labeled large-context drills."""

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path


def prepare(engine: Path, target: Path, cache: Path, tools: list[str]) -> None:
    target.mkdir(parents=True, exist_ok=False)
    cache.mkdir(parents=True, exist_ok=False)
    fixture = engine / "examples/architecture_model/fixture"
    for path in fixture.rglob("*.py.txt"):
        destination = target / path.relative_to(fixture).with_suffix("")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(path.read_bytes())
    spec = json.loads(Path(__file__).with_name("fixture.json").read_text(encoding="utf-8"))
    helper = engine / "skills/codeboarding-modeling/scripts/model_context.py"
    journal: list[dict] = []

    def cli(label: str, *arguments: str) -> dict:
        response = cache / f"{label}.json"
        argv = [
            sys.executable,
            str(helper),
            "--engine",
            str(engine),
            "cli",
            "--response",
            str(response),
            "--",
            *arguments,
        ]
        process = subprocess.run(argv, cwd=target, capture_output=True, text=True, encoding="utf-8", timeout=250)
        journal.append({"argv": argv, "cwd": str(target), "exit_code": process.returncode, "summary": process.stdout})
        write(cache / "preparation-commands.json", journal)
        if process.returncode:
            raise RuntimeError(process.stderr + process.stdout)
        return json.loads(response.read_text(encoding="utf-8"))["result"]

    facts_path = cache / "facts.json"
    cli(
        "export",
        "facts",
        "export",
        "--repo",
        str(target),
        "--project-id",
        spec["project"]["id"],
        "--output",
        str(facts_path),
        *tools,
    )
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    project_path = cache / "project.json"
    write(project_path, spec["project"])
    prefix = ["model", "--file", str(target / "architecture-model.json")]
    cli("init", *prefix, "init", "--project", str(project_path), "--author", "separated-trial-preparation")
    operations = [{"action": "create", "collection": "facts", "id": facts["id"], "value": facts}]
    for identity, symbol in spec["bindings"].items():
        locations = [location for location in facts["symbols"].values() if location["symbol"] == symbol]
        if len(locations) != 1:
            raise ValueError(f"Expected one real symbol location for {symbol}")
        operations.append(
            {
                "action": "create",
                "collection": "bindings",
                "id": identity,
                "value": {
                    "id": identity,
                    "snapshot_id": facts["id"],
                    "source_version": facts["source"]["digest"],
                    "location": locations[0],
                    "status": "current",
                },
            }
        )
    operations.extend(spec["operations"])
    seed = cache / "seed.patch.json"
    write(
        seed,
        {
            "author": "separated-trial-preparation",
            "summary": "Authored independent fixture foundation and purchase",
            "operations": operations,
        },
    )
    cli("seed-validate", *prefix, "validate", "--patch", str(seed))
    cli("seed-diff", *prefix, "diff", "--patch", str(seed))
    cli("seed-apply", *prefix, "apply", "--patch", str(seed), "--expected-revision", "0")
    extension = spec["extension"]
    base = next(operation["value"] for operation in spec["operations"] if operation["id"] == extension["base_scenario"])
    additions = []
    for number in range(extension["count"]):
        scenario = copy.deepcopy(base)
        identity = f"{extension['prefix']}-{number}"
        steps = {step["id"]: f"{identity}-{step['id']}" for step in scenario["steps"]}
        scenario.update(
            id=identity,
            name=f"Synthetic context drill {number}: repeated purchase",
            entry_step_id=steps[scenario["entry_step_id"]],
            order=[steps[step] for step in scenario["order"]],
        )
        scenario["claim"]["explanation"] = extension["explanation"] * extension["repeat"]
        for step in scenario["steps"]:
            step["id"] = steps[step["id"]]
        for transition in scenario["transitions"]:
            transition.update(source_id=steps[transition["source_id"]], target_id=steps[transition["target_id"]])
        additions.append({"action": "create", "collection": "scenarios", "id": identity, "value": scenario})
    expansion = cache / "extension.patch.json"
    write(
        expansion,
        {
            "author": "context-size-test-fixture",
            "summary": "Explicit synthetic repeats for context transport, not new real businesses",
            "operations": additions,
        },
    )
    cli("extension-validate", *prefix, "validate", "--patch", str(expansion))
    cli("extension-diff", *prefix, "diff", "--patch", str(expansion))
    cli("extension-apply", *prefix, "apply", "--patch", str(expansion), "--expected-revision", "1")


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("engine", "target", "cache", "node", "pyright", "tokei"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    tools = [
        "--node",
        str(args.node.resolve()),
        "--pyright",
        str(args.pyright.resolve()),
        "--tokei",
        str(args.tokei.resolve()),
    ]
    prepare(args.engine.resolve(), args.target.resolve(), args.cache.resolve(), tools)


if __name__ == "__main__":
    main()
