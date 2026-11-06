"""Reproduce independent-root planning with real file inventory and Native TypeScript exports."""

import argparse
import json
from pathlib import Path

from architecture_model.cli import run
from architecture_model.store import ModelStore, atomic_write, load_json
from architecture_model.validation import parse
from architecture_model.schema import Facts


def demonstrate(output: Path, tools: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    source.mkdir()
    (source / "package.json").write_text('{"name":"maintenance-sample","private":true}', encoding="utf-8")
    (source / "tsconfig.json").write_text('{"compilerOptions":{"strict":true},"include":["*.ts"]}', encoding="utf-8")
    rules = source / "rules.ts"
    rules.write_text("export function rules(): number { return 1; }\n", encoding="utf-8")
    (source / "gateway.ts").write_text(
        'import { rules } from "./rules";\nexport function gateway() { return rules(); }\n', encoding="utf-8"
    )
    model_path = output / "model.json"
    store = ModelStore(model_path)
    store.initialize(
        {"id": "maintenance-sample", "name": "Sample", "boundary": "Synthetic two-root maintenance"}, "agent-a"
    )
    prefix = ["model", "--file", str(model_path)]
    mapping = output / "source-map.json"
    atomic_write(mapping, {"all-files": str(source), "native-typescript": str(source)})
    exports = []
    for root, options in (
        ("all-files", ["--file-inventory"]),
        ("native-typescript", ["--tools", str(tools.resolve())]),
    ):
        path = output / (root + ".json")
        run(
            [
                "facts",
                "export",
                "--repo",
                str(source),
                "--project-id",
                "maintenance-sample",
                "--source-root-id",
                root,
                "--output",
                str(path),
                *options,
            ]
        )
        exports.append(parse(Facts, load_json(path)))
    operations = []
    binding_ids = []
    for facts in exports:
        operations.append({"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()})
        identity = facts.source_root_id + "-rules"
        binding_ids.append(identity)
        location = next(
            (entry for entry in facts.symbols.values() if entry.path == "rules.ts" and entry.symbol.endswith("rules")),
            facts.file_locations["rules.ts"],
        )
        operations.append(
            {
                "action": "create",
                "collection": "bindings",
                "id": identity,
                "value": {
                    "id": identity,
                    "snapshot_id": facts.id,
                    "source_version": facts.source.digest,
                    "location": location.model_dump(),
                    "status": "current",
                },
            }
        )
    claim = {"kind": "code_fact", "explanation": "Independent views of sample rules", "binding_ids": binding_ids}
    operations.append(
        {
            "action": "create",
            "collection": "components",
            "id": "rules",
            "value": {
                "id": "rules",
                "name": "Rules",
                "responsibility": "Return the sample decision",
                "rationale": "Shared interpretation, independent evidence",
                "binding_ids": binding_ids,
                "claim": claim,
            },
        }
    )
    operations.append(
        {
            "action": "create",
            "collection": "scenarios",
            "id": "operation",
            "value": {
                "id": "operation",
                "name": "Evaluate rules",
                "entry_step_id": "decision",
                "order": ["decision"],
                "transitions": [],
                "claim": claim,
                "steps": [{"id": "decision", "component_ids": ["rules"], "binding_ids": binding_ids, "claim": claim}],
            },
        }
    )
    store.apply(
        store.read().revision,
        {"author": "agent-a", "summary": "Attach both real fact scopes", "operations": operations},
    )
    rules.write_text("export function rules(): number { return 2; }\n", encoding="utf-8")
    native = output / "native-new.json"
    run(
        [
            "facts",
            "export",
            "--repo",
            str(source),
            "--project-id",
            "maintenance-sample",
            "--source-root-id",
            "native-typescript",
            "--output",
            str(native),
            "--tools",
            str(tools.resolve()),
        ]
    )
    preview = run([*prefix, "maintenance-preview", "--facts", str(native)])
    run(
        [
            *prefix,
            "maintenance-refresh",
            "--facts",
            str(native),
            "--token",
            preview["token"],
            "--expected-revision",
            str(preview["revision"]),
            "--author",
            "agent-a",
        ]
    )
    before = model_path.read_bytes()
    plan_path = output / "plan.json"
    summary = run([*prefix, "maintenance-plan", "--source-map", str(mapping), "--output", str(plan_path)])
    check = run([*prefix, "maintenance-plan-check", "--plan", str(plan_path)])
    assert model_path.read_bytes() == before
    assert summary["summary"]["different_versions"] == 1
    assert check["status"] == "blocked"
    atomic_write(
        output / "handoff.json",
        {
            "model": str(model_path),
            "plan": str(plan_path),
            "source_map": str(mapping),
            "engine": str(Path(__file__).resolve().parents[3]),
            "task": "Continue this model's source maintenance plan; check current state first, without reanalyzing the whole repository. Read-only diagnosis; report next actions without writing the model.",
        },
    )
    result = {
        "summary": summary,
        "check": check,
        "model_bytes_unchanged_by_plan": True,
        "native_exports": "real TypeScript engine",
        "source_scope": "public synthetic project",
    }
    atomic_write(output / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(demonstrate(args.output, args.tools)))


if __name__ == "__main__":
    main()
