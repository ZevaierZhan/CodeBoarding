import json
from pathlib import Path
from unittest.mock import patch

import pytest
from filelock import Timeout

from architecture_model.errors import ModelError
from architecture_model.schema import Model
from architecture_model.store import ModelStore
from architecture_model.validation import validate_model


def change(value: dict, collection: str = "components", identity: str = "component", action: str = "update") -> dict:
    return {
        "author": "agent",
        "summary": "Revise",
        "operations": [{"action": action, "collection": collection, "id": identity, "value": value}],
    }


def test_read_preview_do_not_write_and_identity_survives_rename(store: ModelStore) -> None:
    before = store.path.read_bytes()
    proposed, difference = store.preview(change({"name": "Renamed"}))
    assert store.path.read_bytes() == before
    assert proposed.components[0].id == "component"
    assert difference["scenario_ids"] == ["scenario"]
    assert difference["changes"]["components"]["component"]["before"]["name"] == "Entry"
    assert store.read_scope(scenario_id="scenario")["complete"] is False
    assert store.read_scope(component_id="component")["revision"] == 1
    assert store.read_scope()["complete"] is True
    store.apply(1, change({"name": "Renamed"}))
    assert store.read().revision == 2
    assert store.read().components[0].binding_ids == ["binding"]
    assert store.read().scenarios[0].steps[0].component_ids == ["component"]


@pytest.mark.parametrize(
    "amendment,collection,identity,action,code",
    [
        ({"unknown": True}, "components", "component", "update", "SCHEMA_INVALID"),
        (
            {"claim": {"kind": "code_fact", "explanation": "x", "binding_ids": ["binding"], "unknown": True}},
            "components",
            "component",
            "update",
            "SCHEMA_INVALID",
        ),
        ({"binding_ids": ["absent"]}, "components", "component", "update", "DANGLING_REFERENCE"),
        ({"parent_id": "component"}, "components", "component", "update", "PARENT_CYCLE"),
        ({"id": "other"}, "components", "component", "update", "IMMUTABLE"),
        ({}, "components", "component", "create", "DUPLICATE_ID"),
        ({}, "components", "absent", "update", "NOT_FOUND"),
        ({}, "components", "absent", "delete", "NOT_FOUND"),
        ({}, "components", "component", "delete", "DANGLING_REFERENCE"),
        ({"name": "x"}, "components", "component", "delete", "SCHEMA_INVALID"),
        ({"source_version": "a" * 64}, "bindings", "binding", "update", "BINDING_MISMATCH"),
        (
            {"source_version": "a" * 64, "status": "changed", "reason": "Source changed"},
            "bindings",
            "binding",
            "update",
            "HISTORY_REQUIRED",
        ),
        ({"status": "missing"}, "bindings", "binding", "update", "SCHEMA_INVALID"),
        ({"order": ["step", "step"]}, "scenarios", "scenario", "update", "STEP_ORDER"),
        ({"entry_step_id": "absent"}, "scenarios", "scenario", "update", "DANGLING_REFERENCE"),
        (
            {"transitions": [{"source_id": "step", "target_id": "absent", "kind": "return", "condition": "x"}]},
            "scenarios",
            "scenario",
            "update",
            "DANGLING_REFERENCE",
        ),
        (
            {"claim": {"kind": "inference", "explanation": "x", "binding_ids": ["binding"]}},
            "components",
            "component",
            "update",
            "SCHEMA_INVALID",
        ),
        (
            {"claim": {"kind": "code_fact", "explanation": "x", "binding_ids": []}},
            "components",
            "component",
            "update",
            "SCHEMA_INVALID",
        ),
    ],
)
def test_invalid_candidate_keeps_bytes(
    store: ModelStore, amendment: dict, collection: str, identity: str, action: str, code: str
) -> None:
    before = store.path.read_bytes()
    with pytest.raises(ModelError) as raised:
        store.apply(1, change(amendment, collection, identity, action))
    assert raised.value.code == code
    assert raised.value.location.startswith("/")
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("schema_version", 2, "UNSUPPORTED_VERSION"),
        ("components", [{"id": "component"}], "SCHEMA_INVALID"),
        ("revision", 10, "REVISION_INVALID"),
        ("unexpected", {}, "SCHEMA_INVALID"),
    ],
)
def test_corrupt_models_are_not_reinitialized(store: ModelStore, field: str, value: object, code: str) -> None:
    model = store.read().model_dump()
    model[field] = value
    store.path.write_text(json.dumps(model))
    before = store.path.read_bytes()
    with pytest.raises(ModelError, match=".") as raised:
        store.read()
    assert raised.value.code == code
    with pytest.raises(ModelError) as raised:
        store.initialize({"id": "x", "name": "X", "boundary": "x"}, "test")
    assert raised.value.code == "ALREADY_EXISTS"
    assert store.path.read_bytes() == before


def test_revision_conflict_after_successful_preview(store: ModelStore) -> None:
    store.preview(change({"name": "Preview"}))
    store.apply(1, change({"name": "Winner"}))
    before = store.path.read_bytes()
    with pytest.raises(ModelError) as raised:
        store.apply(1, change({"name": "Loser"}))
    assert raised.value.code == "REVISION_CONFLICT"
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("target", ["tempfile.NamedTemporaryFile", "os.fsync", "os.replace"])
def test_io_failure_keeps_original_and_cleans_temporary(store: ModelStore, target: str) -> None:
    before = store.path.read_bytes()
    files = set(store.path.parent.iterdir())
    with patch(f"architecture_model.store.{target}", side_effect=OSError("injected failure")):
        with pytest.raises(ModelError) as raised:
            store.apply(1, change({"name": "Discarded"}))
    assert raised.value.code == "SAVE_FAILED"
    assert store.path.read_bytes() == before
    assert set(store.path.parent.iterdir()) == files
    assert store.read().revision == 1


def test_initialization_failure_leaves_no_model(tmp_path: Path) -> None:
    store = ModelStore(tmp_path / "architecture-model.json")
    with patch("architecture_model.store.os.replace", side_effect=OSError("injected")):
        with pytest.raises(ModelError):
            store.initialize({"id": "p", "name": "P", "boundary": "x"}, "agent")
    assert not store.path.exists()
    assert not [path for path in tmp_path.iterdir() if path.suffix != ".lock"]


def test_references_repaired_in_same_commit_and_business_loop_allowed(store: ModelStore) -> None:
    scenario = store.read().scenarios[0].model_dump()
    scenario["steps"][0]["component_ids"] = []
    scenario["transitions"] = [{"source_id": "step", "target_id": "step", "kind": "loop", "condition": "Repeat"}]
    operations = change({}, action="delete")["operations"] + change(scenario, "scenarios", "scenario")["operations"]
    store.apply(1, {"author": "agent", "summary": "Delete and repair", "operations": operations})
    assert not store.read().components
    assert len(store.read().scenarios[0].steps) == 1


def test_duplicate_global_and_step_ids_rejected(store: ModelStore) -> None:
    duplicate = store.read().scenarios[0].model_dump()
    duplicate["id"] = "duplicate"
    with pytest.raises(ModelError) as raised:
        store.apply(1, change(duplicate, "scenarios", "duplicate", "create"))
    assert raised.value.code == "DUPLICATE_ID"


def test_delete_then_create_cannot_disguise_an_update(store: ModelStore) -> None:
    before = store.path.read_bytes()
    original = store.read().components[0].model_dump()
    operations = change({}, action="delete")["operations"] + change(original, action="create")["operations"]
    with pytest.raises(ModelError) as raised:
        store.apply(1, {"author": "agent", "summary": "Replace", "operations": operations})
    assert raised.value.code == "DUPLICATE_ID"
    assert store.path.read_bytes() == before


def test_current_mismatch_stale_evidence_and_history(store: ModelStore) -> None:
    binding = store.read().bindings[0].model_dump()
    historical = {key: binding[key] for key in ("snapshot_id", "source_version", "location")}
    historical["reason"] = "Previously located here"
    update = {"source_version": "a" * 64, "history": [historical]}
    with pytest.raises(ModelError) as raised:
        store.apply(1, change(update, "bindings", "binding"))
    assert raised.value.code == "BINDING_MISMATCH"
    update.update(status="changed", reason="Agent observed different source")
    store.apply(1, change(update, "bindings", "binding"))
    assert store.read().bindings[0].history[0].location == store.read().bindings[0].location
    assert store.read().scenarios[0].claim.explanation
    with pytest.raises(ModelError) as raised:
        store.apply(2, change({"history": []}, "bindings", "binding"))
    assert raised.value.code == "HISTORY_REQUIRED"


def test_facts_are_immutable_and_project_scoped(store: ModelStore, facts: dict) -> None:
    with pytest.raises(ModelError) as raised:
        store.apply(1, change({}, "facts", facts["id"]))
    assert raised.value.code == "IMMUTABLE"
    model = store.read().model_dump()
    model["project"]["id"] = "other"
    with pytest.raises(ModelError) as raised:
        validate_model(model)
    assert raised.value.code == "FACTS_MISMATCH"


def test_partial_read_cannot_be_applied_as_complete_model(store: ModelStore) -> None:
    with pytest.raises(ModelError) as raised:
        store.apply(1, store.read_scope(scenario_id="scenario"))
    assert raised.value.code == "SCHEMA_INVALID"
    for kwargs in ({"scenario_id": "absent"}, {"component_id": "absent"}):
        with pytest.raises(ModelError) as raised:
            store.read_scope(**kwargs)
        assert raised.value.code == "NOT_FOUND"


@pytest.mark.parametrize("raw", ['{"id":"x","id":"y"}', "{", "null"])
def test_unreadable_file_does_not_look_absent(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "model.json"
    path.write_text(raw)
    with pytest.raises(ModelError):
        ModelStore(path).read()
    assert path.read_text() == raw


def test_lock_timeout_is_structured(store: ModelStore) -> None:
    with patch.object(store.lock, "acquire", side_effect=Timeout("locked")):
        with pytest.raises(ModelError) as raised:
            store.apply(1, change({"name": "x"}))
    assert raised.value.code == "LOCK_TIMEOUT"


def test_verification_does_not_promote_inference_and_opinion_is_separate(store: ModelStore) -> None:
    version = store.read().facts[0].source.digest
    planned = {
        "id": "check",
        "status": "planned",
        "object_ids": ["component"],
        "command": "pytest",
        "environment": "Windows Python 3.12",
        "inputs": "fixture",
        "source_version": version,
    }
    explanation = change(planned, "verifications", "check", "create")
    explanation["operations"] += change(
        {
            "claim": {
                "kind": "inference",
                "explanation": "Proposed entry boundary",
                "binding_ids": ["binding"],
                "assumptions": ["Treat run as an entrypoint"],
            }
        }
    )["operations"]
    store.apply(1, explanation)
    with pytest.raises(ModelError):
        store.apply(2, change({"status": "executed"}, "verifications", "check"))
    store.apply(
        2,
        change(
            {
                "status": "executed",
                "executor": "agent",
                "executed_at": "2026-11-04T12:00:00Z",
                "exit_code": 0,
                "result": "one test passed",
            },
            "verifications",
            "check",
        ),
    )
    opinion = {
        "id": "opinion",
        "author": "reviewer",
        "text": "Accepted",
        "stance": "accept",
        "object_ids": ["component"],
    }
    store.apply(3, change(opinion, "opinions", "opinion", "create"))
    assert store.read().components[0].claim.kind == "inference"
    with pytest.raises(ModelError):
        store.apply(4, change({"status": "planned"}, "verifications", "check"))
    assert store.read().revision == 4


def test_schema_disallows_unknown_nested_fields() -> None:
    schema = Model.model_json_schema()
    assert schema["additionalProperties"] is False
    assert all(definition.get("additionalProperties") is False for definition in schema["$defs"].values())


@pytest.mark.parametrize("value", [None, {}, "bad"])
def test_malformed_history_is_a_structured_error(store: ModelStore, value: object) -> None:
    before = store.path.read_bytes()
    with pytest.raises(ModelError) as raised:
        store.apply(1, change({"history": value}, "bindings", "binding"))
    assert raised.value.code == "SCHEMA_INVALID"
    assert store.path.read_bytes() == before


def test_relations_and_binding_changes_report_real_impact(store: ModelStore) -> None:
    relation = {
        "id": "relation",
        "source_id": "component",
        "target_id": "component",
        "meaning": "Recursive use",
        "claim": {
            "kind": "inference",
            "explanation": "Possible recurrence",
            "binding_ids": ["binding"],
            "issues": ["Not present in static call graph"],
        },
    }
    store.apply(1, change(relation, "relations", "relation", "create"))
    _, difference = store.preview(change({"meaning": "Conditional recurrence"}, "relations", "relation"))
    assert difference["relation_ids"] == ["relation"]
    assert difference["scenario_ids"] == ["scenario"]
    _, difference = store.preview(
        change({"status": "ambiguous", "reason": "Two candidate source locations"}, "bindings", "binding")
    )
    assert difference["component_ids"] == ["component"]
    assert difference["scenario_ids"] == ["scenario"]


def test_incomplete_temp_write_keeps_bytes(store: ModelStore) -> None:
    before = store.path.read_bytes()
    with patch("architecture_model.store.json.dump", side_effect=ValueError("serialization failed")):
        with pytest.raises(ModelError) as raised:
            store.apply(1, change({"name": "Discarded"}))
    assert raised.value.code == "SAVE_FAILED"
    assert store.path.read_bytes() == before


def test_empty_author_cannot_initialize(tmp_path: Path) -> None:
    store = ModelStore(tmp_path / "model.json")
    with pytest.raises(ModelError) as raised:
        store.initialize({"id": "p", "name": "P", "boundary": "x"}, "")
    assert raised.value.code == "SCHEMA_INVALID"
    assert not store.path.exists()


def test_multiple_operations_validate_final_binding_candidate(store: ModelStore) -> None:
    operations = change({"status": "missing"}, "bindings", "binding")["operations"]
    operations += change({"reason": "Source is unavailable"}, "bindings", "binding")["operations"]
    store.apply(1, {"author": "agent", "summary": "Mark missing and explain", "operations": operations})
    assert store.read().bindings[0].status == "missing"
    assert store.read().revision == 2
