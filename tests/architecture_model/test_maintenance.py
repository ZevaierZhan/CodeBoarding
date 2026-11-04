from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.schema import Facts
from architecture_model.store import ModelStore
from architecture_model.validation import digest, parse, validate_model
from examples.architecture_model.demo import cli, write

SCOPE = json.dumps(
    {
        "protocol": "python-file-v1",
        "complete": True,
        "implementation": "engine",
        "patterns": [],
        "tools": ["explicit-tools"],
        "configuration": {},
    }
)


def snapshot(value: dict) -> Facts:
    value = deepcopy(value)
    value["source"]["digest"] = digest(value["source"]["files"])
    value["id"] = digest({key: item for key, item in value.items() if key != "id"})
    return parse(Facts, value)


def changed(facts: Facts, path: str = "app.py") -> Facts:
    value = facts.model_dump()
    content_hash = digest("changed implementation")
    value["source"]["files"][path] = content_hash
    for item in [*value["symbols"].values(), *value["file_locations"].values()]:
        if item["path"] == path:
            item["content_hash"] = content_hash
    return snapshot(value)


def record(store: ModelStore, facts: Facts) -> dict:
    report = preview(store.read(), facts)
    refresh(store, facts, report["revision"], report["token"], "agent")
    return report


@pytest.fixture
def maintained(store: ModelStore) -> ModelStore:
    current = store.read()
    value = current.facts[0].model_dump()
    value["tools"]["maintenance_scope"] = SCOPE
    scoped = snapshot(value)
    old = current.bindings[0]
    store.apply(
        current.revision,
        {
            "author": "agent",
            "summary": "Explicitly establish scoped baseline",
            "operations": [
                {"action": "create", "collection": "facts", "id": scoped.id, "value": scoped.model_dump()},
                {
                    "action": "update",
                    "collection": "bindings",
                    "id": old.id,
                    "value": {
                        "snapshot_id": scoped.id,
                        "history": [
                            {
                                "snapshot_id": old.snapshot_id,
                                "source_version": old.source_version,
                                "location": old.location.model_dump(),
                                "reason": "Scoped baseline",
                            }
                        ],
                    },
                },
            ],
        },
    )
    return store


def test_idempotent_refresh_and_legacy_read_preserve_original_facts(maintained: ModelStore) -> None:
    store = maintained
    original = store.read()
    raw = original.model_dump()
    raw.pop("maintenance")
    raw.pop("maintenance_target_snapshot_id")
    store.path.write_text(json.dumps(raw))
    before = store.path.read_bytes()
    report = preview(store.read(), original.facts[-1])
    assert store.path.read_bytes() == before
    assert report["observations"][0]["disposition"] == "unchanged"
    for _ in range(2):
        record(store, original.facts[-1])
    after = ModelStore(store.path).read()
    assert after.facts == original.facts
    assert after.bindings == original.bindings
    assert after.components == original.components and after.scenarios == original.scenarios
    assert len(after.maintenance) == 1 and not query(after)["pending_ids"]
    assert after.revision == original.revision + 2


def test_pending_survives_unrelated_refresh_rebind_and_explicit_resolution(maintained: ModelStore) -> None:
    store = maintained
    initial = store.read()
    shared = changed(initial.facts[-1])
    first = record(store, shared)["observations"][0]
    assert first["disposition"] == "changed" and first["scenario_ids"] == ["scenario"]
    value = shared.model_dump()
    value["source"]["files"]["unrelated.py"] = digest("unrelated")
    later = snapshot(value)
    record(store, later)
    assert len(query(store.read())["pending_ids"]) == 2
    rebind(store, first["id"], "app.py|app.run", store.read().revision, "agent", "Inspected target")
    assert len(query(store.read())["pending_ids"]) == 2
    rebound = store.read().bindings[0]
    assert rebound.id == initial.bindings[0].id
    assert rebound.history[-1].snapshot_id == initial.bindings[0].snapshot_id
    assert rebound.history[-1].location == initial.bindings[0].location
    resolve(
        store,
        first["id"],
        {
            "author": "business-agent",
            "reason": "Inspected changed file; responsibility still holds",
            "outcome": "confirmed",
            "source_version": shared.source.digest,
        },
        store.read().revision,
    )
    current = ModelStore(store.path).read()
    assert first["id"] not in query(current)["pending_ids"]
    assert len(query(current)["pending_ids"]) == 1
    assert current.components == initial.components and current.scenarios == initial.scenarios
    record(store, shared)
    assert next(item for item in store.read().maintenance if item.id == first["id"]).resolution is not None


def test_unrelated_digest_does_not_invalidate_explanations(maintained: ModelStore) -> None:
    old = maintained.read().facts[-1]
    target = changed(old, "unrelated.py")
    report = record(maintained, target)
    assert old.source.digest != target.source.digest
    assert report["observations"][0]["disposition"] == "unchanged"
    assert not query(maintained.read())["pending_ids"]


@pytest.mark.parametrize("mode", ["lines", "same-file", "calls"])
def test_granularity_and_incident_call_changes(maintained: ModelStore, mode: str) -> None:
    old = maintained.read().facts[-1]
    value = changed(old).model_dump() if mode != "calls" else old.model_dump()
    if mode == "lines":
        value["symbols"]["app.py|app.run"].update(start=4, end=4)
    if mode == "calls":
        value["calls"] = [{"source": "app.run", "target": "app.run", "sites": []}]
    item = record(maintained, snapshot(value))["observations"][0]
    assert item["disposition"] == "changed"
    assert "Containing-file" in item["reasons"][0]
    assert maintained.read().bindings[0].location == old.symbols["app.py|app.run"]


@pytest.mark.parametrize(
    "mode,expected", [("move", "changed"), ("rename", "changed"), ("delete", "missing"), ("ambiguous", "ambiguous")]
)
def test_candidates_are_explicit_and_identity_history_survive(maintained: ModelStore, mode: str, expected: str) -> None:
    store = maintained
    original = store.read()
    value = original.facts[-1].model_dump()
    location = value["symbols"].pop("app.py|app.run")
    if mode in ("move", "ambiguous", "delete"):
        value["source"]["files"].pop("app.py")
    if mode != "delete":
        for path in (
            ["other.py", "third.py"] if mode == "ambiguous" else ["other.py"] if mode == "move" else ["app.py"]
        ):
            choice = location | {
                "path": path,
                "symbol": f"{Path(path).stem}.renamed" if mode == "rename" else f"{Path(path).stem}.run",
            }
            value["source"]["files"][path] = choice["content_hash"]
            value["symbols"][f"{path}|{choice['symbol']}"] = choice
    value["source"]["files"]["constant.py"] = digest("sentinel")
    item = record(store, snapshot(value))["observations"][0]
    assert item["disposition"] == expected
    assert store.read().bindings == original.bindings
    assert store.read_scope(scenario_id="scenario")["model"]["scenarios"]
    if mode != "delete":
        choice = item["candidates"][-1]
        rebind(store, item["id"], choice["key"], store.read().revision, "agent", "Inspected replacement")
        assert store.read().bindings[0].location.model_dump() == choice["location"]
        assert store.read().bindings[0].history[-1].snapshot_id == original.bindings[0].snapshot_id
        assert query(store.read())["pending_ids"] == [item["id"]]


@pytest.mark.parametrize("mode", ["legacy", "scope", "malformed", "project", "digest"])
def test_untrustworthy_exports_never_establish_deletion(maintained: ModelStore, mode: str) -> None:
    store = maintained
    value = changed(store.read().facts[-1]).model_dump()
    if mode == "legacy":
        value["tools"].pop("maintenance_scope")
    elif mode == "scope":
        descriptor = json.loads(SCOPE)
        descriptor["patterns"] = ["app.py"]
        value["tools"]["maintenance_scope"] = json.dumps(descriptor)
    elif mode == "malformed":
        value["tools"]["maintenance_scope"] = "{}"
    elif mode == "project":
        value["project_id"] = "other"
    target = snapshot(value)
    if mode == "digest":
        target.id = "bad"
    before = store.path.read_bytes()
    if mode in ("legacy", "scope"):
        report = preview(store.read(), target)
        assert report["observations"][0]["disposition"] == "indeterminate"
    else:
        with pytest.raises(ModelError):
            preview(store.read(), target)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("failure", ["revision", "token", "replace", "fsync", "author"])
def test_refresh_failure_is_atomic(maintained: ModelStore, failure: str) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    report = preview(store.read(), target)
    before = store.path.read_bytes()
    kwargs = {"expected_revision": report["revision"], "token": report["token"], "author": "agent"}
    if failure == "revision":
        kwargs["expected_revision"] -= 1
    elif failure == "token":
        kwargs["token"] = "invalid"
    elif failure == "author":
        kwargs["author"] = ""
    with patch(
        f"architecture_model.store.os.{failure if failure in ('replace', 'fsync') else 'getpid'}",
        side_effect=OSError("injected") if failure in ("replace", "fsync") else None,
    ):
        with pytest.raises(ModelError):
            refresh(store, target, **kwargs)
    assert store.path.read_bytes() == before


def test_review_validation_and_revision_history(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    item = record(store, target)["observations"][0]
    review = {
        "author": "agent",
        "reason": "Inspected changed behavior",
        "outcome": "revised",
        "source_version": target.source.digest,
    }
    for invalid in (
        review,
        review | {"source_version": "wrong"},
        review | {"operations": [{"collection": "bindings"}]},
    ):
        before = store.path.read_bytes()
        with pytest.raises(ModelError):
            resolve(store, item["id"], invalid, store.read().revision)
        assert store.path.read_bytes() == before
    review["operations"] = [
        {
            "action": "update",
            "collection": "components",
            "id": "component",
            "value": {"responsibility": "Revised responsibility"},
        }
    ]
    response = resolve(store, item["id"], review, store.read().revision)
    saved = ModelStore(store.path).read()
    resolution = saved.maintenance[0].resolution
    assert resolution is not None and resolution.outcome == "revised"
    assert saved.components[0].responsibility == "Revised responsibility"
    assert response["diff"]["scenario_ids"] == saved.revisions[-1].scenario_ids == ["scenario"]
    assert query(saved, component_id="component", scenario_id="scenario", binding_id="binding")["pending_ids"] == []
    with pytest.raises(ModelError):
        resolve(store, item["id"], review, saved.revision)
    for arguments in ({"component_id": "absent"}, {"scenario_id": "absent"}, {"binding_id": "absent"}):
        with pytest.raises(ModelError):
            query(saved, **arguments)
    with pytest.raises(ModelError):
        rebind(store, item["id"], "absent", saved.revision, "agent", "reason")
    with pytest.raises(ModelError):
        rebind(store, "absent", "absent", saved.revision, "agent", "reason")


def test_each_binding_uses_its_own_baseline(maintained: ModelStore) -> None:
    store = maintained
    initial = store.read()
    target = changed(initial.facts[-1])
    item = record(store, target)["observations"][0]
    rebind(store, item["id"], "app.py|app.run", store.read().revision, "agent", "Select version")
    old_binding = initial.bindings[0].model_dump() | {"id": "historical-binding"}
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Add historical view",
            "operations": [
                {"action": "create", "collection": "bindings", "id": old_binding["id"], "value": old_binding},
            ],
        },
    )
    results = {entry["binding_id"]: entry for entry in preview(store.read(), target)["observations"]}
    assert results["binding"]["disposition"] == "unchanged"
    assert results["historical-binding"]["disposition"] == "changed"


def test_maintenance_catalog_references_are_strict(maintained: ModelStore) -> None:
    target = changed(maintained.read().facts[-1])
    record(maintained, target)
    for field, value in (
        ("target_source_version", "a" * 64),
        ("compared_revision", 999),
        ("target_snapshot_id", "absent"),
    ):
        current = maintained.read().model_dump()
        current["maintenance"][0][field] = value
        with pytest.raises(ModelError):
            validate_model(current)


def test_maintenance_cli_independent_processes(maintained: ModelStore, tmp_path: Path) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    facts_path = write(tmp_path / "target.json", target.model_dump())
    prefix = ("model", "--file", str(store.path))
    before = store.path.read_bytes()
    report = cli(*prefix, "maintenance-preview", "--facts", str(facts_path))
    assert store.path.read_bytes() == before
    item = report["observations"][0]
    cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(facts_path),
        "--token",
        report["token"],
        "--expected-revision",
        str(report["revision"]),
        "--author",
        "agent",
    )
    before = store.path.read_bytes()
    conflict = cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(facts_path),
        "--token",
        report["token"],
        "--expected-revision",
        str(report["revision"]),
        "--author",
        "agent",
        success=False,
    )
    assert conflict["code"] == "REVISION_CONFLICT" and store.path.read_bytes() == before
    cli(
        *prefix,
        "maintenance-rebind",
        "--item",
        item["id"],
        "--candidate",
        "app.py|app.run",
        "--expected-revision",
        str(store.read().revision),
        "--author",
        "agent",
        "--reason",
        "Inspected candidate",
    )
    assert item["id"] in cli(*prefix, "maintenance", "--binding", "binding")["pending_ids"]
    review = write(
        tmp_path / "review.json",
        {
            "author": "agent",
            "reason": "Original interpretation still holds",
            "outcome": "confirmed",
            "source_version": target.source.digest,
        },
    )
    cli(
        *prefix,
        "maintenance-resolve",
        "--item",
        item["id"],
        "--review",
        str(review),
        "--expected-revision",
        str(store.read().revision),
    )
    saved = cli(*prefix, "maintenance", "--scenario", "scenario")
    assert saved["pending_ids"] == []
    assert saved["observations"][0]["resolution"]["reason"] == "Original interpretation still holds"


def test_legacy_baseline_is_not_silently_rewritten(store: ModelStore) -> None:
    original = store.read()
    value = changed(original.facts[0]).model_dump()
    value["tools"]["maintenance_scope"] = SCOPE
    target = snapshot(value)
    item = record(store, target)["observations"][0]
    assert item["disposition"] == "indeterminate"
    assert store.read().facts[0].model_dump() == original.facts[0].model_dump()
    assert store.read().bindings == original.bindings


def test_revert_retains_pending_and_repeat_preserves_resolution(maintained: ModelStore) -> None:
    store = maintained
    original = store.read().facts[-1]
    target = changed(original)
    item = record(store, target)["observations"][0]
    record(store, original)
    assert item["id"] in query(store.read())["pending_ids"]
    resolve(
        store,
        item["id"],
        {
            "author": "agent",
            "reason": "Inspected exact target; original explanation holds",
            "outcome": "confirmed",
            "source_version": target.source.digest,
        },
        store.read().revision,
    )
    repeated = preview(store.read(), target)
    assert repeated["observations"][0]["resolution"]["outcome"] == "confirmed"
    assert item["id"] not in repeated["pending_ids"]
