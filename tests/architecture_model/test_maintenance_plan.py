import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from architecture_model.cli import run
from architecture_model import maintenance_plan
from architecture_model.errors import ModelError
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.maintenance_plan import check_plan, generate_plan
from architecture_model.store import ModelStore, atomic_write
from architecture_model.file_inventory import export_inventory
from architecture_model.schema import Facts
from architecture_model.validation import digest
from tests.architecture_model.test_schema_compat import extended
from tests.architecture_model.test_source_coverage import model_with_roots, native_fixture, snapshot, source


def mapping_file(tmp_path: Path, mapping: dict[str, Path]) -> Path:
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps({key: str(value) for key, value in mapping.items()}))
    return path


@pytest.fixture
def dual(source: Path, tmp_path: Path) -> tuple[ModelStore, Path]:
    store = model_with_roots(
        tmp_path, [snapshot(source, tmp_path / "all.json"), native_fixture(source, tmp_path / "native.json")]
    )
    return store, mapping_file(tmp_path, {"all-files": source, "native": source})


def test_dual_version_plan_is_read_only_and_scopes_independent(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").write_text("export function rules() { return 2; }\n")
    target = native_fixture(source, tmp_path / "new-native.json")
    report = preview(store.read(), target)
    refresh(store, target, store.read().revision, report["token"], "test")
    before = store.path.read_bytes()
    plan = generate_plan(store.read(), mapping, [], [])
    roots = {row["source_root_id"]: row for row in plan["roots"]}
    assert roots["native"]["latest_recorded_maintenance_target"] == target.id
    assert roots["all-files"]["reexport"] == "needed_workspace_differs"
    assert plan["summary"]["different_versions"] == 1
    assert plan["affected"] == {
        "binding_ids": ["all-files-binding", "native-binding"],
        "component_ids": ["component"],
        "relation_ids": [],
        "scenario_ids": ["scenario"],
        "step_ids": ["step"],
    }
    assert plan["status"] == "blocked"
    checked = check_plan(store.read(), plan)
    assert checked["status"] == "blocked" and not checked["requires_replan"]
    assert any(reason["code"] == "root_prerequisites_blocked" for reason in checked["reasons"])
    assert store.path.read_bytes() == before
    assert '"token":' not in json.dumps(plan)
    assert all(not row["recommended_after"] for row in plan["roots"])


@pytest.mark.parametrize(
    "change",
    ["revision", "content", "source", "addition", "mapping", "facts", "descriptor", "lost_facts", "lost_mapping"],
)
def test_check_invalidates_all_changed_prerequisites(dual, source, tmp_path, change):
    store, mapping = dual
    facts_path = tmp_path / "proposed.json"
    snapshot(source, facts_path)
    plan = generate_plan(store.read(), mapping, [facts_path], [])
    assert plan["status"] == "ready"
    if change == "revision":
        other = ModelStore(store.path)
        other.apply(
            other.read().revision,
            {
                "author": "other",
                "summary": "Concurrent edit",
                "operations": [
                    {
                        "action": "update",
                        "collection": "components",
                        "id": "component",
                        "value": {"responsibility": "Concurrent responsibility"},
                    }
                ],
            },
        )
    elif change == "content":
        model = store.read()
        model.components[0].responsibility = "Unversioned corruption"
        atomic_write(store.path, model.model_dump())
    elif change == "source":
        (source / "src/rules.ts").write_text("changed")
    elif change == "addition":
        (source / "new.ts").write_text("new file")
    elif change == "mapping":
        other_dir = tmp_path / "other"
        shutil.copytree(source, other_dir)
        mapping.write_text(json.dumps({"all-files": str(other_dir), "native": str(source)}))
    elif change == "facts":
        facts_path.write_text(facts_path.read_text() + "\n")
    elif change == "descriptor":
        value = json.loads(facts_path.read_text())
        descriptor = json.loads(value["tools"]["maintenance_scope"])
        descriptor["implementation"] = "new extractor"
        value["tools"]["maintenance_scope"] = json.dumps(descriptor)
        value["id"] = digest({key: entry for key, entry in value.items() if key != "id"})
        atomic_write(facts_path, value)
    elif change == "lost_facts":
        facts_path.unlink()
    else:
        mapping.unlink()
    before = store.path.read_bytes()
    checked = check_plan(store.read(), plan)
    assert checked["status"] == "stale", checked
    assert checked["requires_replan"] and checked["reasons"]
    if change == "source":
        assert any(reason.get("changed_files") for reason in checked["reasons"])
    assert store.path.read_bytes() == before


def test_staged_refresh_rebind_review_preserve_history(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").write_text("export function rules() { return 2; }\n")
    initial = store.read()
    plan = generate_plan(initial, mapping, [], [])
    targets = [snapshot(source, tmp_path / "new-all.json"), native_fixture(source, tmp_path / "new-native.json")]
    for target in targets:
        result = preview(store.read(), target)
        refresh(store, target, store.read().revision, result["token"], "test")
        if target.source_root_id == "all-files":
            store.apply(
                store.read().revision,
                {
                    "author": "test",
                    "summary": "Clarify affected interpretation",
                    "operations": [
                        {
                            "action": "update",
                            "collection": "components",
                            "id": "component",
                            "value": {"responsibility": "Reviewed rules boundary"},
                        }
                    ],
                },
            )
        assert check_plan(store.read(), plan)["status"] == "stale"
        plan = generate_plan(store.read(), mapping, [], [])
        observation = next(
            item for item in result["observations"] if item["binding_id"] == target.source_root_id + "-binding"
        )
        rebind(
            store,
            observation["id"],
            observation["candidates"][0]["key"],
            store.read().revision,
            "test",
            "Read target code",
        )
        current = query(store.read())
        for item in current["observations"]:
            if item["id"] not in current["current_pending_ids"] or item["target_snapshot_id"] != target.id:
                continue
            resolve(
                store,
                item["id"],
                {
                    "author": "test",
                    "reason": "Inspected affected explanations",
                    "outcome": "confirmed",
                    "source_version": item["target_source_version"],
                },
                store.read().revision,
            )
    model = store.read()
    assert len(model.maintenance_targets) == 2
    assert model.facts[:2] == initial.facts and model.verifications == initial.verifications
    assert all(binding.history for binding in model.bindings)
    final = generate_plan(model, mapping, [], [])
    assert final["pending"]["historical_ids"]
    assert not final["pending"]["current_ids"]
    assert check_plan(model, final)["status"] == "ready"
    assert any(item["status"] == "completed" for item in final["items"])
    assert all(item["status"] != "completed" for item in final["items"] if item["action"] == "runtime-verification")


@pytest.mark.parametrize(
    "problem", ["no_map", "no_scope", "unsupported", "deleted", "directory", "history", "distinct_files"]
)
def test_untrusted_sources_never_claim_completion(dual, source, tmp_path, problem):
    store, mapping = dual
    if problem == "no_map":
        mapping = None
    elif problem in ("no_scope", "unsupported"):
        model = store.read()
        facts = model.facts[0]
        if problem == "no_scope":
            facts.tools.pop("maintenance_scope")
        else:
            facts.tools["maintenance_scope"] = '{"protocol":"future"}'
        old_id = facts.id
        facts.id = digest(facts.model_dump(exclude={"id"}))
        for binding in model.bindings:
            if binding.snapshot_id == old_id:
                binding.snapshot_id = facts.id
        atomic_write(store.path, model.model_dump())
    elif problem == "deleted":
        (source / "src/rules.ts").unlink()
    elif problem == "directory":
        mapping.write_text(json.dumps({"all-files": str(tmp_path / "absent"), "native": str(source)}))
    elif problem == "history":
        model = store.read()
        binding = model.bindings[0].model_copy(deep=True)
        binding.id = "unattributed"
        binding.snapshot_id = "missing-snapshot"
        binding.status = "missing"
        binding.reason = "Historical snapshot unavailable"
        model.bindings.append(binding)
        atomic_write(store.path, model.model_dump())
    else:
        other = tmp_path / "other"
        shutil.copytree(source, other)
        mapping.write_text(json.dumps({"all-files": str(other), "native": str(source)}))
    before = store.path.read_bytes()
    plan = generate_plan(store.read(), mapping, [], [])
    if problem == "distinct_files":
        assert not plan["overlaps"]
        assert all(row["review_coverage_status"] == "unknown_target" for row in plan["roots"])
    else:
        assert plan["status"] == "blocked"
        assert check_plan(store.read(), plan)["status"] == "blocked"
    assert not any(item["status"] == "completed" for item in plan["items"])
    assert store.path.read_bytes() == before


def test_plan_preserves_complete_operation_comparison_model(extended, tmp_path):
    before = extended.path.read_bytes()
    plan = generate_plan(extended.read(), None, [], [])
    assert check_plan(extended.read(), plan)["status"] == "blocked"
    assert extended.path.read_bytes() == before
    assert extended.read().scenarios[1].analysis_kind == "comparison"


def test_cli_summary_paging_and_plan_integrity(dual, tmp_path):
    store, mapping = dual
    path = tmp_path / "plan.json"
    args = ["model", "--file", str(store.path)]
    before = store.path.read_bytes()
    summary = run([*args, "maintenance-plan", "--source-map", str(mapping), "--output", str(path)])
    assert len(json.dumps(summary)) < 2048
    assert run([*args, "maintenance-plan-check", "--plan", str(path)])["status"] == "ready"
    with pytest.raises(ModelError, match="new plan"):
        run([*args, "maintenance-plan", "--output", str(store.path)])
    script = Path("skills/codeboarding-modeling/scripts/model_context.py").resolve()
    for extra in ([], ["--collection", "roots"], ["--pointer", "/pending"]):
        result = subprocess.run(
            [sys.executable, str(script), "plan", "--report", str(path), *extra],
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stderr
        assert len(result.stdout) <= 4096
    plan = json.loads(path.read_text())
    unsafe_output = tmp_path / "sample-system/query.json"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "plan",
            "--report",
            str(path),
            "--pointer",
            "/pending",
            "--output",
            str(unsafe_output),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1 and not unsafe_output.exists()
    plan["items"][0]["status"] = "completed"
    with pytest.raises(ModelError, match="identity"):
        check_plan(store.read(), plan)
    assert store.path.read_bytes() == before


def test_root_selection_is_focus_not_hidden_cross_root_dependency(dual):
    store, mapping = dual
    plan = generate_plan(store.read(), mapping, [], ["native"])
    assert len(plan["roots"]) == 2
    assert [row["source_root_id"] for row in plan["roots"] if row["requested"]] == ["native"]
    assert all(not row["recommended_after"] for row in plan["roots"])


def test_wrong_project_root_and_ambiguous_selection_rejected(dual, source, tmp_path):
    store, mapping = dual
    wrong = snapshot(source, tmp_path / "wrong.json", "other")
    with pytest.raises(ModelError, match="existing root"):
        generate_plan(store.read(), mapping, [tmp_path / "wrong.json"], [])
    with pytest.raises(ModelError, match="one snapshot"):
        generate_plan(store.read(), mapping, [tmp_path / "all.json", tmp_path / "all.json"], [])
    with pytest.raises(ModelError, match="Unknown"):
        generate_plan(store.read(), mapping, [], ["unknown"])


def test_query_helper_normalizes_plan_path():
    helper = runpy.run_path("skills/codeboarding-modeling/scripts/model_context.py")
    args = helper["absolute_arguments"](
        ["model", "--file", "model.json", "maintenance-plan-check", "--plan", "plan.json"]
    )
    assert Path(args[-1]).is_absolute()


def test_cross_language_contract_keeps_one_sided_evidence_and_old_execution(tmp_path):
    source = tmp_path / "service"
    source.mkdir()
    (source / "caller.ts").write_text('export function call() { return "invoke:rules"; }\n')
    (source / "receiver.rs").write_text("pub fn rules() -> bool { true }\n")
    snapshots = []
    for root, path, language in (("caller", "caller.ts", "typescript"), ("receiver", "receiver.rs", "rust")):
        value = export_inventory(source, "sample", tmp_path / (root + ".json"), root, [path], []).model_dump()
        value["file_languages"][path] = language
        value["id"] = digest({key: entry for key, entry in value.items() if key != "id"})
        snapshots.append(Facts.model_validate(value))
    store = ModelStore(tmp_path / "model.json")
    store.initialize({"id": "sample", "name": "IPC sample", "boundary": "Synthetic Rust + TypeScript"}, "test")
    operations = []
    for snapshot_value in snapshots:
        root = snapshot_value.source_root_id
        claim = {"kind": "code_fact", "explanation": "Static source", "binding_ids": [root + "-binding"]}
        operations.extend(
            [
                {
                    "action": "create",
                    "collection": "facts",
                    "id": snapshot_value.id,
                    "value": snapshot_value.model_dump(),
                },
                {
                    "action": "create",
                    "collection": "bindings",
                    "id": root + "-binding",
                    "value": {
                        "id": root + "-binding",
                        "snapshot_id": snapshot_value.id,
                        "source_version": snapshot_value.source.digest,
                        "location": next(iter(snapshot_value.file_locations.values())).model_dump(),
                        "status": "current",
                    },
                },
                {
                    "action": "create",
                    "collection": "components",
                    "id": root,
                    "value": {
                        "id": root,
                        "name": root,
                        "responsibility": "IPC side",
                        "rationale": "Separate process",
                        "binding_ids": [root + "-binding"],
                        "claim": claim,
                    },
                },
            ]
        )
    claim = {
        "kind": "inference",
        "explanation": "Possible IPC contract",
        "binding_ids": ["caller-binding", "receiver-binding"],
        "issues": ["Runtime unverified"],
    }
    operations.append(
        {
            "action": "create",
            "collection": "relations",
            "id": "ipc",
            "value": {
                "id": "ipc",
                "source_id": "caller",
                "target_id": "receiver",
                "meaning": "Invoke rules",
                "claim": claim,
                "contract": {
                    "mechanism": "IPC",
                    "operation": "rules",
                    "caller_binding_ids": ["caller-binding"],
                    "receiver_binding_ids": ["receiver-binding"],
                    "rationale": "Synthetic candidate; static names alone are insufficient",
                    "uncertainties": ["Runtime mapping requires investigation"],
                    "status": "candidate",
                },
            },
        }
    )
    operations.append(
        {
            "action": "create",
            "collection": "verifications",
            "id": "historical-execution",
            "value": {
                "id": "historical-execution",
                "status": "executed",
                "object_ids": ["ipc"],
                "command": "synthetic recorded command",
                "environment": "synthetic fixture",
                "inputs": "fixture",
                "source_version": snapshots[0].source.digest,
                "executor": "fixture",
                "executed_at": "2026-01-01T00:00:00Z",
                "exit_code": 0,
                "result": "Synthetic historical result, not an actual acceptance run",
                "binding_snapshots": {
                    snapshot_value.source_root_id + "-binding": snapshot_value.id for snapshot_value in snapshots
                },
            },
        }
    )
    store.apply(0, {"author": "test", "summary": "Synthetic cross-language contract", "operations": operations})
    before = store.read()
    (source / "caller.ts").write_text('export function call() { return "invoke:rules-v2"; }\n')
    target = export_inventory(source, "sample", tmp_path / "updated.json", "caller", ["caller.ts"], [])
    report = preview(store.read(), target)
    refresh(store, target, store.read().revision, report["token"], "test")
    mapping = mapping_file(tmp_path, {"caller": source, "receiver": source})
    plan = generate_plan(store.read(), mapping, [], [])
    contract = plan["contracts"][0]
    assert contract["saved_status"] == "candidate"
    assert contract["caller"][0]["status"] == "older_binding"
    assert contract["caller"][0]["target_recorded"]
    assert contract["receiver"][0]["status"] == "at_target"
    assert not contract["receiver"][0]["target_recorded"]
    assert contract["review"] == "requires-review"
    assert contract["verification"][0]["older_target_evidence"]
    assert store.read().verifications == before.verifications
    assert store.read().relations == before.relations


def test_ambiguous_candidates_block_selection(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").unlink()
    target = native_fixture(source, tmp_path / "ambiguous.json")
    target.symbols = {
        path + "|rules": location.model_copy(update={"symbol": "rules", "kind": "FUNCTION"})
        for path, location in target.file_locations.items()
    }
    target.id = digest(target.model_dump(exclude={"id"}))
    atomic_write(tmp_path / "ambiguous-real.json", target.model_dump())
    plan = generate_plan(store.read(), mapping, [tmp_path / "ambiguous-real.json"], [])
    assert any(item["disposition"] == "ambiguous" for item in plan["observations"])
    assert plan["status"] == "blocked"
    assert all(item["status"] != "completed" for item in plan["items"] if item["action"] == "maintenance-rebind")


def test_engine_change_invalidates_plan(dual, monkeypatch):
    store, mapping = dual
    plan = generate_plan(store.read(), mapping, [], [])
    monkeypatch.setattr(maintenance_plan, "_engine_digest", lambda: "changed extractor implementation")
    result = check_plan(store.read(), plan)
    assert result["status"] == "stale"
    assert {"code": "engine_digest_changed"} in result["reasons"]


def test_source_read_failure_stays_explicitly_blocked(dual, monkeypatch):
    store, mapping = dual
    monkeypatch.setattr(maintenance_plan.os, "scandir", lambda path: (_ for _ in ()).throw(PermissionError("denied")))
    plan = generate_plan(store.read(), mapping, [], [])
    assert plan["status"] == "blocked"
    assert any(item["code"] == "mapping_unavailable" for item in plan["issues"])


def test_invalid_protocol_and_incomplete_envelope_fail_specifically(dual):
    store, mapping = dual
    with pytest.raises(ModelError, match="protocol"):
        check_plan(store.read(), {"protocol": "future"})
    body = {"protocol": maintenance_plan.PROTOCOL, "inputs": {}, "validity": {}}
    with pytest.raises(ModelError, match="locators"):
        check_plan(store.read(), {"plan_id": digest(body), **body})


def test_coverage_reuses_query_without_mutating_shared_objects(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").write_text("changed")
    target = native_fixture(source, tmp_path / "fresh.json")
    result = preview(store.read(), target)
    refresh(store, target, store.read().revision, result["token"], "test")
    model = store.read()
    before = model.model_dump()
    first = query(model)
    assert query(model) == first
    assert model.model_dump() == before
    assert generate_plan(model, mapping, [], [])["pending"]["current_ids"] == first["current_pending_ids"]
