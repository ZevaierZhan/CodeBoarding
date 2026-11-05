"""Exercise real TypeScript exports and inventory against shared physical files."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from architecture_model.cli import run
from architecture_model.facts import export_multilanguage
from architecture_model.file_inventory import export_inventory
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.schema import Facts
from architecture_model.store import ModelStore, atomic_write


def accept(output: Path, tools: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    source = output / "sample-system"
    shutil.copytree(Path(__file__).with_name("sample-system"), source)
    inventory = export_inventory(source, "sample", output / "inventory.json", "all-files", [], [])
    native = export_multilanguage(source, "sample", output / "native.json", "native-typescript", tools)
    assert native.symbols and native.calls and inventory.id != native.id
    store = ModelStore(output / "model.json")
    store.initialize({"id": "sample", "name": "Policy", "boundary": "Public synthetic project"}, "acceptance")
    operations: list[dict] = []
    for facts in (inventory, native):
        operations.append({"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()})
        location = facts.file_locations["src/rules.ts"]
        if facts.symbols:
            location = next(value for value in facts.symbols.values() if value.path == "src/rules.ts")
        binding = {
            "id": facts.source_root_id,
            "snapshot_id": facts.id,
            "source_version": facts.source.digest,
            "location": location.model_dump(),
            "status": "current",
        }
        operations.append({"action": "create", "collection": "bindings", "id": binding["id"], "value": binding})
    ids = [inventory.source_root_id, native.source_root_id]
    claim = {
        "kind": "inference",
        "explanation": "Policy inferred from independent evidence",
        "binding_ids": ids,
        "assumptions": ["Static analysis alone does not execute authorization"],
    }
    component = {
        "id": "policy",
        "name": "Policy",
        "responsibility": "Authorize roles",
        "rationale": "Sample",
        "binding_ids": ids,
        "claim": claim,
    }
    scenario = {
        "id": "authorize",
        "name": "Authorization",
        "entry_step_id": "check",
        "order": ["check"],
        "transitions": [],
        "claim": claim,
        "steps": [{"id": "check", "component_ids": ["policy"], "binding_ids": ids, "claim": claim}],
    }
    for collection, value in (("components", component), ("scenarios", scenario)):
        operations.append({"action": "create", "collection": collection, "id": value["id"], "value": value})
    verification = {
        "id": "policy-verification",
        "status": "planned",
        "object_ids": ["policy"],
        "command": "Review authorization policy against recorded source",
        "environment": "Public synthetic fixture",
        "inputs": "Independent inventory and TypeScript evidence",
        "source_version": inventory.source.digest,
        "binding_snapshots": {inventory.source_root_id: inventory.id, native.source_root_id: native.id},
    }
    operations.append(
        {"action": "create", "collection": "verifications", "id": verification["id"], "value": verification}
    )
    store.apply(0, {"author": "acceptance", "summary": "Attach two independent roots", "operations": operations})
    mapping = output / "mapping.json"
    atomic_write(mapping, {root: str(source.resolve()) for root in ids})
    reports = []
    read_only_checks = []

    def report(name: str) -> dict:
        before = store.path.read_bytes()
        original = store.read()
        result = run(
            [
                "model",
                "--file",
                str(store.path),
                "coverage-report",
                "--source-map",
                str(mapping),
                "--output",
                str(output / f"{name}.json"),
            ]
        )
        assert store.path.read_bytes() == before and len(json.dumps(result)) < 2048
        assert store.read() == original
        read_only_checks.append(
            {
                "phase": name,
                "revision_before": original.revision,
                "revision_after": store.read().revision,
                "sha256_before": hashlib.sha256(before).hexdigest(),
                "sha256_after": hashlib.sha256(store.path.read_bytes()).hexdigest(),
            }
        )
        reports.append(result["summary"])
        return json.loads((output / f"{name}.json").read_text(encoding="utf-8"))

    first = report("baseline")
    assert first["summary"]["same_version"] == 3
    (source / "src/rules.ts").write_text(
        'export function allowed(role: string): boolean { return role !== "blocked"; }\n'
    )
    changed = export_multilanguage(source, "sample", output / "native-new.json", native.source_root_id, tools)
    update(store, changed)
    after_native = store.read().model_dump()
    second = report("native-refreshed")
    assert second["summary"]["different_versions"] == 1
    assert store.read().maintenance_targets == {native.source_root_id: changed.id}
    assert store.read().facts[0] == inventory
    next_inventory = export_inventory(source, "sample", output / "inventory-new.json", "all-files", [], [])
    update(store, next_inventory)
    third = report("both-exported")
    assert third["summary"]["same_version"] == 3
    assert query(store.read())["pending_ids"]
    assert all(root["architecture_review"] == "not_established_by_coverage" for root in third["roots"])
    upgraded = export_inventory(
        source, "sample", output / "inventory-new-rules.json", "all-files", ["src/*", "docs/*"], []
    )
    assert upgraded.source.files == next_inventory.source.files
    observation = preview(store.read(), upgraded)["observations"][0]
    assert observation["disposition"] == "indeterminate"
    update(store, upgraded)
    rebind(store, observation["id"], "src/rules.ts", store.read().revision, "acceptance", "Inspected new rule baseline")
    resolve(
        store,
        observation["id"],
        {
            "author": "acceptance",
            "reason": "Reviewed sample interpretation",
            "outcome": "confirmed",
            "source_version": upgraded.source.digest,
        },
        store.read().revision,
    )
    assert preview(store.read(), upgraded)["observations"][0]["disposition"] == "unchanged"
    assert store.read().facts[0] == inventory and store.read().facts[1] == native
    reviewed = report("latest-reviewed")
    root = next(row for row in reviewed["roots"] if row["source_root_id"] == "all-files")
    assert root["current_pending_ids"] == [] and root["historical_pending_ids"]
    assert observation["id"] in root["resolved_ids"]
    saved = store.read()
    store.apply(
        saved.revision,
        {
            "author": "acceptance",
            "summary": "Revise policy interpretation",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "policy",
                    "value": {"responsibility": "Authorize roles under revised business policy"},
                }
            ],
        },
    )
    edited = report("interpretation-edited")
    root = next(row for row in edited["roots"] if row["source_root_id"] == "all-files")
    assert root["current_pending_ids"] and root["historical_pending_ids"]
    assert observation["id"] in root["historical_resolved_ids"]
    assert store.read().maintenance[: len(saved.maintenance)] == saved.maintenance
    assert store.read().facts == saved.facts and store.read().bindings == saved.bindings
    assert store.read().verifications == saved.verifications
    assert saved.verifications and saved.verifications[0].binding_snapshots == verification["binding_snapshots"]
    summary = {
        "real_native_typescript": True,
        "native_symbols": len(native.symbols),
        "native_calls": len(native.calls),
        "inventory_files": len(inventory.source.files),
        "reports": reports,
        "read_only_bytes_preserved": True,
        "read_only_checks": read_only_checks,
        "root_isolation": after_native["maintenance_targets"] == {native.source_root_id: changed.id},
        "descriptor_upgrade": observation["disposition"],
        "explicit_baseline_reestablished": True,
        "historical_pending_retained": bool(query(store.read())["pending_ids"]),
        "historical_snapshots_preserved": True,
        "latest_review_separated_from_historical_pending": True,
        "interpretation_edit_requires_new_review": True,
        "historical_reviews_preserved": True,
        "original_verification_scope_preserved": True,
    }
    atomic_write(output / "summary.json", summary)
    return summary


def update(store: ModelStore, target: Facts) -> None:
    proposed = preview(store.read(), target)
    refresh(store, target, store.read().revision, proposed["token"], "acceptance")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tools", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(accept(args.output.resolve(), args.tools.resolve())))
