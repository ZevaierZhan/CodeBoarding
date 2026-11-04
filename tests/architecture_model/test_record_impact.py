import pytest

from architecture_model.store import ModelStore


@pytest.mark.parametrize("collection", ["opinions", "verifications"])
@pytest.mark.parametrize("reference", ["scenario", "step"])
def test_record_lifecycle_reports_scenario_impact(store: ModelStore, collection: str, reference: str) -> None:
    other = store.read().scenarios[0].model_dump()
    other.update(id="other-scenario", entry_step_id="other-step", order=["other-step"])
    other["steps"][0]["id"] = "other-step"
    store.apply(
        1,
        {
            "author": "test",
            "summary": "Second scene",
            "operations": [{"action": "create", "collection": "scenarios", "id": other["id"], "value": other}],
        },
    )
    old_target = "scenario" if reference == "scenario" else "step"
    new_target = "other-scenario" if reference == "scenario" else "other-step"
    record: dict
    body: dict
    if collection == "opinions":
        record = {
            "id": "record",
            "author": "reviewer",
            "text": "Please review",
            "stance": "question",
            "object_ids": [old_target],
        }
        body = {"text": "Updated review text"}
    else:
        record = {
            "id": "record",
            "status": "executed",
            "object_ids": [old_target],
            "command": "pytest",
            "environment": "fixture",
            "inputs": "fixture",
            "source_version": store.read().facts[0].source.digest,
            "executor": "test",
            "executed_at": "2026-11-04T12:00:00Z",
            "exit_code": 0,
            "result": "Passed",
        }
        body = {"result": "Updated result summary"}
    stages: list[tuple[str, dict, list[str]]] = [
        ("create", record, ["scenario"]),
        ("update", body, ["scenario"]),
        ("update", {"object_ids": [new_target]}, ["other-scenario", "scenario"]),
        ("update", {key: f"{item} after reassignment" for key, item in body.items()}, ["other-scenario"]),
        ("delete", {}, ["other-scenario"]),
    ]
    for action, value, expected in stages:
        current = store.read()
        before = store.path.read_bytes()
        patch = {
            "author": "test",
            "summary": f"{action} review record",
            "operations": [{"action": action, "collection": collection, "id": "record", "value": value}],
        }
        proposed, difference = store.preview(patch)
        assert store.path.read_bytes() == before
        assert difference["scenario_ids"] == expected
        assert proposed.revisions[-1].scenario_ids == expected
        committed = store.apply(current.revision, patch)
        saved = store.read()
        assert committed["diff"] == difference
        assert saved.revisions[-1].scenario_ids == expected
        assert saved.revision == current.revision + 1
        records = getattr(saved, collection)
        if action == "delete":
            assert records == []
        else:
            assert all(records[0].model_dump()[key] == item for key, item in value.items())
