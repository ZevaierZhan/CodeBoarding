from copy import deepcopy
from pathlib import Path
import runpy

import pytest

from architecture_model.errors import ModelError
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.schema import Facts
from architecture_model.validation import digest, parse, validate_model
from architecture_model.viewer import projection


def add_roots(store, facts):
    operations = []
    snapshots = {}
    for root, checksum in (("frontend", "a" * 64), ("backend", "b" * 64)):
        snapshot = deepcopy(facts)
        snapshot.update(
            schema_version=2, source_root_id=root, file_languages={"app.py": "python"}, file_projects={"app.py": "."}
        )
        snapshot["source"]["files"]["app.py"] = checksum
        snapshot["source"]["digest"] = digest(snapshot["source"]["files"])
        snapshot["symbols"]["app.py|app.run"]["content_hash"] = checksum
        snapshot["id"] = digest({key: value for key, value in snapshot.items() if key != "id"})
        snapshots[root] = snapshot
        operations += [
            {"action": "create", "collection": "facts", "id": snapshot["id"], "value": snapshot},
            {
                "action": "create",
                "collection": "bindings",
                "id": root,
                "value": {
                    "id": root,
                    "snapshot_id": snapshot["id"],
                    "source_version": snapshot["source"]["digest"],
                    "location": snapshot["symbols"]["app.py|app.run"],
                    "status": "current",
                },
            },
        ]
        operations.append(
            {
                "action": "create",
                "collection": "components",
                "id": root + "-component",
                "value": {
                    "id": root + "-component",
                    "name": root,
                    "responsibility": "Root endpoint",
                    "rationale": "Independent repository",
                    "binding_ids": [root],
                    "claim": {"kind": "code_fact", "explanation": "Root evidence", "binding_ids": [root]},
                },
            }
        )
    relation = {
        "id": "ipc",
        "source_id": "frontend-component",
        "target_id": "backend-component",
        "meaning": "Two-root request",
        "claim": {
            "kind": "inference",
            "explanation": "Conditional dispatch",
            "binding_ids": ["frontend", "backend"],
            "issues": ["Runtime not exercised"],
        },
    }
    operations.append({"action": "create", "collection": "relations", "id": "ipc", "value": relation})
    store.apply(
        store.read().revision, {"author": "test", "summary": "Independent root evidence", "operations": operations}
    )
    return snapshots


def record(version, objects):
    return {
        "id": "check",
        "status": "planned",
        "object_ids": objects,
        "command": "check target",
        "environment": "fixture",
        "inputs": "Declared evidence",
        "source_version": version,
    }


def save_record(store, value):
    return store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Record a planned check",
            "operations": [{"action": "create", "collection": "verifications", "id": value["id"], "value": value}],
        },
    )


def test_wrong_root_verification_rejected_without_writing(store, facts):
    snapshots = add_roots(store, facts)
    before = store.path.read_bytes()
    with pytest.raises(ModelError, match="[Vv]erification"):
        save_record(store, record(snapshots["backend"]["source"]["digest"], ["frontend"]))
    assert store.path.read_bytes() == before


def test_new_cross_root_verification_requires_explicit_scope(store, facts):
    snapshots = add_roots(store, facts)
    before = store.path.read_bytes()
    with pytest.raises(ModelError, match="[Vv]erification"):
        save_record(store, record(snapshots["frontend"]["source"]["digest"], ["ipc"]))
    assert store.path.read_bytes() == before


def test_explicit_root_refresh_does_not_replace_legacy_target(store, facts):
    snapshots = add_roots(store, facts)
    legacy = parse(Facts, facts)
    report = preview(store.read(), legacy)
    refresh(store, legacy, store.read().revision, report["token"], "test")
    for root in ("frontend", "backend"):
        target = parse(Facts, snapshots[root])
        before = store.path.read_bytes()
        report = preview(store.read(), target)
        assert store.path.read_bytes() == before
        refresh(store, target, store.read().revision, report["token"], "test")
        assert store.read().maintenance_target_snapshot_id == legacy.id
        assert query(store.read())["latest_target_snapshot_id"] == legacy.id
    assert store.read().maintenance_targets == {root: value["id"] for root, value in snapshots.items()}


def test_single_root_v1_verification_roundtrip_keeps_legacy_shape(store, facts):
    value = record(facts["source"]["digest"], ["binding"])
    save_record(store, value)
    saved = store.read().verifications[0].model_dump()
    assert "binding_snapshots" not in saved
    assert all(saved[key] == item for key, item in value.items())


def test_v2_direct_binding_infers_only_its_root(store, facts):
    snapshots = add_roots(store, facts)
    save_record(store, record(snapshots["frontend"]["source"]["digest"], ["frontend"]))
    scope = projection(store.read())["verification_scopes"]["check"]
    assert scope["scope_kind"] == "implicit_direct_bindings"
    assert {item["source_root_id"] for item in scope["evidence"]} == {"frontend"}


def test_v2_single_root_component_has_explicit_valid_scope(store, facts):
    snapshots = add_roots(store, facts)
    value = record(snapshots["frontend"]["source"]["digest"], ["frontend-component"])
    value["binding_snapshots"] = {"frontend": snapshots["frontend"]["id"]}
    save_record(store, value)
    scope = projection(store.read())["verification_scopes"]["check"]
    assert scope["scope_kind"] == "declared_referenced_evidence"
    assert scope["uncovered_binding_ids"] == []


def test_new_binding_check_cannot_guess_an_unavailable_root(store, facts):
    snapshots = add_roots(store, facts)
    orphan = {
        "id": "orphan",
        "snapshot_id": "unavailable",
        "source_version": snapshots["frontend"]["source"]["digest"],
        "location": snapshots["frontend"]["symbols"]["app.py|app.run"],
        "status": "changed",
        "reason": "Original root catalog unavailable",
    }
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Retain historical location",
            "operations": [{"action": "create", "collection": "bindings", "id": "orphan", "value": orphan}],
        },
    )
    before = store.path.read_bytes()
    with pytest.raises(ModelError, match="Verification root cannot"):
        save_record(store, record(snapshots["backend"]["source"]["digest"], ["orphan"]))
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("roots", [("frontend",), ("frontend", "backend")])
def test_explicit_cross_root_scope_distinguishes_partial_and_full_evidence(store, facts, roots):
    snapshots = add_roots(store, facts)
    value = record(snapshots["frontend"]["source"]["digest"], ["ipc"])
    value["binding_snapshots"] = {root: snapshots[root]["id"] for root in roots}
    save_record(store, value)
    payload = projection(store.read())
    scope = payload["verification_scopes"]["check"]
    assert scope["scope_kind"] == ("declared_partial" if len(roots) == 1 else "declared_referenced_evidence")
    assert scope["uncovered_binding_ids"] == (["backend"] if len(roots) == 1 else [])
    assert {item["source_root_id"]: item["source_version"] for item in scope["evidence"]} == {
        root: snapshots[root]["source"]["digest"] for root in roots
    }
    assert payload["model"]["verifications"][0]["status"] == "planned"
    assert "not runtime proof" in scope["notice"]


def test_old_unscoped_cross_root_record_reads_without_inventing_coverage(store, facts):
    snapshots = add_roots(store, facts)
    raw = store.read().model_dump()
    raw["verifications"] = [record(snapshots["backend"]["source"]["digest"], ["ipc"])]
    model = validate_model(raw)
    assert model.verifications[0].model_dump()["source_version"] == snapshots["backend"]["source"]["digest"]
    assert projection(model)["verification_scopes"]["check"]["scope_kind"] == "legacy_unscoped"


def test_old_v2_scalar_is_an_explicit_root_alias_not_a_legacy_target(store, facts):
    snapshots = add_roots(store, facts)
    target = parse(Facts, facts)
    report = preview(store.read(), target)
    refresh(store, target, store.read().revision, report["token"], "test")
    model = store.read()
    model.maintenance_target_snapshot_id = snapshots["frontend"]["id"]
    before = model.model_dump()
    report = query(model)
    assert report["latest_target_snapshot_id"] == ""
    assert report["source_root_targets"] == {"frontend": snapshots["frontend"]["id"]}
    assert report["unknown_target_observation_ids"] == [item.id for item in model.maintenance]
    assert not set(report["unknown_target_observation_ids"]).intersection(report["latest_observation_ids"])
    assert model.model_dump() == before


@pytest.mark.parametrize("problem", ["foreign_snapshot", "unknown_binding", "wrong_anchor", "omit_direct"])
def test_bad_explicit_scope_rolls_back(store, facts, problem):
    snapshots = add_roots(store, facts)
    value = record(snapshots["frontend"]["source"]["digest"], ["ipc"])
    value["binding_snapshots"] = {"frontend": snapshots["frontend"]["id"]}
    if problem == "foreign_snapshot":
        value["binding_snapshots"]["frontend"] = snapshots["backend"]["id"]
    elif problem == "unknown_binding":
        value["binding_snapshots"] = {"unknown": snapshots["frontend"]["id"]}
    elif problem == "wrong_anchor":
        value["source_version"] = snapshots["backend"]["source"]["digest"]
    else:
        value["object_ids"] = ["ipc", "backend"]
    before = store.path.read_bytes()
    with pytest.raises(ModelError, match="[Vv]erification"):
        save_record(store, value)
    assert store.path.read_bytes() == before


def test_verification_retains_exact_historical_binding_scope_after_rebind(store, facts):
    snapshots = add_roots(store, facts)
    value = record(snapshots["frontend"]["source"]["digest"], ["frontend"])
    value["binding_snapshots"] = {"frontend": snapshots["frontend"]["id"]}
    save_record(store, value)
    original = store.read().verifications[0].model_dump()
    target = deepcopy(snapshots["frontend"])
    target["source"]["files"]["app.py"] = "c" * 64
    target["source"]["digest"] = digest(target["source"]["files"])
    target["symbols"]["app.py|app.run"]["content_hash"] = "c" * 64
    target["id"] = digest({key: item for key, item in target.items() if key != "id"})
    report = preview(store.read(), parse(Facts, target))
    refresh(store, parse(Facts, target), store.read().revision, report["token"], "test")
    item = report["observations"][0]
    rebind(store, item["id"], item["candidates"][0]["key"], store.read().revision, "test", "Inspected changed file")
    assert store.read().verifications[0].model_dump() == original
    assert (
        projection(store.read())["verification_scopes"]["check"]["evidence"][0]["snapshot_id"]
        == snapshots["frontend"]["id"]
    )


def test_component_membership_edit_does_not_rewrite_historical_verification(store, facts):
    snapshots = add_roots(store, facts)
    value = record(snapshots["frontend"]["source"]["digest"], ["frontend-component"])
    value["binding_snapshots"] = {"frontend": snapshots["frontend"]["id"]}
    save_record(store, value)
    original = store.read().verifications[0].model_dump()
    claim = {
        "kind": "inference",
        "explanation": "Revised component boundary",
        "binding_ids": ["backend"],
        "issues": ["Interpretation changed"],
    }
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Revise component evidence",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "frontend-component",
                    "value": {"binding_ids": ["backend"], "claim": claim},
                }
            ],
        },
    )
    assert store.read().verifications[0].model_dump() == original
    scope = projection(store.read())["verification_scopes"]["check"]
    assert scope["scope_kind"] == "declared_historical"
    assert scope["historical_binding_ids"] == ["frontend"]
    assert scope["uncovered_binding_ids"] == ["backend"]


def test_latest_query_agrees_with_projection_and_preserves_legacy_review(store, facts):
    changed = deepcopy(facts)
    changed["source"]["files"]["app.py"] = "c" * 64
    changed["source"]["digest"] = digest(changed["source"]["files"])
    changed["symbols"]["app.py|app.run"]["content_hash"] = "c" * 64
    changed["id"] = digest({key: value for key, value in changed.items() if key != "id"})
    target = parse(Facts, changed)
    report = preview(store.read(), target)
    refresh(store, target, store.read().revision, report["token"], "test")
    observation = report["observations"][0]
    resolve(
        store,
        observation["id"],
        {
            "author": "test",
            "reason": "Reviewed legacy change",
            "outcome": "confirmed",
            "source_version": target.source.digest,
            "operations": [],
        },
        store.read().revision,
    )
    old = store.read().maintenance[0].model_dump()
    snapshots = add_roots(store, facts)
    for root in ("frontend", "backend", "frontend"):
        target = parse(Facts, snapshots[root])
        report = preview(store.read(), target)
        refresh(store, target, store.read().revision, report["token"], "test")
    model = store.read()
    assert model.maintenance[0].model_dump() == old
    report = query(model)
    assert report == projection(model)["maintenance"]
    assert report["latest_target_snapshot_id"] == changed["id"]
    assert observation["id"] in report["latest_observation_ids"]
    assert report["source_root_targets"] == {root: value["id"] for root, value in snapshots.items()}


def test_bounded_agent_summary_uses_legacy_target_semantics(store, facts, tmp_path):
    snapshots = add_roots(store, facts)
    api = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "skills/codeboarding-modeling/scripts/model_context.py")
    )
    for target in (facts["id"], snapshots["frontend"]["id"]):
        model = store.read()
        model.maintenance_target_snapshot_id = target
        report = query(model)
        summary = api["overview"](
            model.model_dump(),
            {"artifact_type": "temporary-complete-read-index", "model_path": str(store.path)},
            tmp_path,
        )
        assert summary["maintenance_target"] == report["latest_target_snapshot_id"]
        assert summary["named_maintenance_target_count"] == len(report.get("source_root_targets", {}))
        assert "legacy root only" in summary["maintenance_target_scope"]
