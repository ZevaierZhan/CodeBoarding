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
from architecture_model.viewer import projection
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


@pytest.mark.parametrize("surface", ["read", "maintenance"])
def test_legacy_derived_id_can_be_referenced_by_ordinary_patch(store: ModelStore, surface: str) -> None:
    record(store, changed(store.read().facts[0]))
    legacy = store.read().model_dump()
    for item in legacy["maintenance"]:
        item["id"] = "maintenance-" + digest(
            {"binding": item["binding_id"], "basis": item["basis"], "target": item["target_snapshot_id"]}
        )
        item.pop("coverage_version")
        item.pop("object_versions")
    store.path.write_text(json.dumps(legacy), encoding="utf-8")
    before = store.path.read_bytes()
    prefix = ("model", "--file", str(store.path))
    response = cli(*prefix, surface)
    observations = response["model"]["maintenance"] if surface == "read" else response["observations"]
    identity = next(item["id"] for item in observations if item["coverage_version"] == "objects-v1")
    assert store.path.read_bytes() == before
    revision = legacy["revision"]
    patch: dict = {
        "author": "agent",
        "summary": "Comment on visible review",
        "operations": [
            {
                "action": "create",
                "collection": "opinions",
                "id": "feedback",
                "value": {"author": "user", "text": "Please inspect", "stance": "question", "object_ids": [identity]},
            }
        ],
    }
    patch_path = write(store.path.parent / "opinion.json", patch)
    assert (
        cli(*prefix, "apply", "--patch", str(patch_path), "--expected-revision", str(revision - 1), success=False)[
            "code"
        ]
        == "REVISION_CONFLICT"
    )
    assert store.path.read_bytes() == before
    invalid = deepcopy(patch)
    invalid["operations"][0]["value"]["object_ids"].append("absent")
    with pytest.raises(ModelError) as failure:
        store.apply(revision, invalid)
    assert failure.value.code == "DANGLING_REFERENCE"
    assert store.path.read_bytes() == before
    cli(*prefix, "apply", "--patch", str(patch_path), "--expected-revision", str(revision))
    saved = cli(*prefix, "read")["model"]
    assert saved["revision"] == revision + 1
    assert saved["opinions"][0]["object_ids"] == [identity]
    assert saved["maintenance"][: len(legacy["maintenance"])] == validate_model(legacy).model_dump()["maintenance"]
    assert saved["facts"] == legacy["facts"]


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


def test_viewer_keeps_current_coverage_separate_from_latest_source_target(maintained: ModelStore) -> None:
    original = maintained.read().facts[-1]
    first_target = changed(original)
    first = record(maintained, first_target)["observations"][0]
    resolve(maintained, first["id"], _review(first_target), maintained.read().revision)
    value = first_target.model_dump()
    value["source"]["files"]["unrelated.py"] = digest("additional source")
    latest = snapshot(value)
    second = record(maintained, latest)["observations"][0]
    before = maintained.path.read_bytes()
    view = projection(maintained.read())
    report = view["maintenance"]
    assert report == query(maintained.read())
    assert report["latest_target_snapshot_id"] == latest.id
    assert first["id"] in report["current_coverage_ids"]
    assert first["id"] not in report["current_pending_ids"]
    assert second["id"] in report["current_pending_ids"]
    prior = next(o for o in view["model"]["maintenance"] if o["id"] == first["id"])
    assert prior["target_snapshot_id"] != report["latest_target_snapshot_id"]
    assert prior["resolution"]["source_version"] == first_target.source.digest
    assert maintained.path.read_bytes() == before


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


@pytest.mark.parametrize("confirmed", [False, True])
def test_shared_scenario_gets_current_review_scope(maintained: ModelStore, confirmed: bool) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    if confirmed:
        resolve(store, original["id"], _review(target), store.read().revision)
    historical = store.read().maintenance[0].model_dump()
    _add_business_b(store)
    scoped = query(store.read(), scenario_id="business-B")
    assert scoped["pending_ids"], "New shared scenario must have review coverage before refresh"
    assert set(scoped["current_pending_ids"]).issubset({item.id for item in store.read().maintenance})
    report = preview(store.read(), target)
    current = report["observations"][0]
    assert current["scenario_ids"] == ["business-B", "scenario"]
    assert current["resolution"] is None and current["id"] != original["id"]
    refresh(store, target, report["revision"], report["token"], "agent")
    assert next(item for item in store.read().maintenance if item.id == original["id"]).model_dump() == historical
    assert current["id"] in query(ModelStore(store.path).read(), scenario_id="business-B")["pending_ids"]


@pytest.mark.parametrize(
    "collection,identity,value",
    [
        ("components", "component", {"responsibility": "Changed interpretation with stable identity"}),
        (
            "scenarios",
            "scenario",
            {
                "claim": {
                    "kind": "code_fact",
                    "explanation": "Changed business interpretation",
                    "binding_ids": ["binding"],
                }
            },
        ),
    ],
)
def test_edited_explanation_does_not_inherit_confirmation(
    maintained: ModelStore, collection: str, identity: str, value: dict
) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    resolve(store, original["id"], _review(target), store.read().revision)
    historical = store.read().maintenance[0].model_dump()
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Edit continuing interpretation",
            "operations": [
                {"action": "update", "collection": collection, "id": identity, "value": value},
            ],
        },
    )
    assert query(store.read(), scenario_id="scenario")["pending_ids"]
    current = record(store, target)["observations"][0]
    assert current["id"] != original["id"] and current["resolution"] is None
    assert store.read().maintenance[0].model_dump() == historical
    assert store.read().components[0].id == "component" and store.read().scenarios[0].steps[0].id == "step"


def test_unrelated_object_and_noop_keep_review_closed(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    resolve(store, original["id"], _review(target), store.read().revision)
    initial = store.read()
    other_binding = initial.bindings[0].model_dump() | {
        "id": "other-binding",
        "snapshot_id": target.id,
        "source_version": target.source.digest,
        "location": target.symbols["app.py|app.run"].model_dump(),
        "history": [],
    }
    other = initial.components[0].model_dump() | {
        "id": "other",
        "binding_ids": ["other-binding"],
        "claim": initial.components[0].claim.model_dump() | {"binding_ids": ["other-binding"]},
    }
    store.apply(
        initial.revision,
        {
            "author": "agent",
            "summary": "Independent interpretation",
            "operations": [
                {"action": "create", "collection": "bindings", "id": "other-binding", "value": other_binding},
                {"action": "create", "collection": "components", "id": "other", "value": other},
            ],
        },
    )
    before = store.read().maintenance[0].model_dump()
    for _ in range(2):
        record(store, target)
    assert not query(store.read(), component_id="component")["pending_ids"]
    assert store.read().maintenance[0].model_dump() == before
    assert len([item for item in store.read().maintenance if item.binding_id == "binding"]) == 1


def test_rebind_recovers_version_only_m1_state(maintained: ModelStore) -> None:
    store = maintained
    original = store.read().bindings[0]
    target = store.read().facts[-1]
    historical = {
        "snapshot_id": original.snapshot_id,
        "source_version": original.source_version,
        "location": original.location.model_dump(),
        "reason": "Record previous valid evidence",
    }
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Declare changed source version",
            "operations": [
                {
                    "action": "update",
                    "collection": "bindings",
                    "id": original.id,
                    "value": {
                        "status": "changed",
                        "source_version": "b" * 64,
                        "reason": "Agent observed a new version",
                        "history": [*[item.model_dump() for item in original.history], historical],
                    },
                },
            ],
        },
    )
    before = store.read().bindings[0]
    item = record(store, target)["observations"][0]
    assert item["disposition"] == "indeterminate"
    intact = store.path.read_bytes()
    with pytest.raises(ModelError):
        rebind(store, item["id"], "absent", store.read().revision, "agent", "Invalid selection")
    assert store.path.read_bytes() == intact
    with patch("architecture_model.store.os.replace", side_effect=OSError("Injected recovery save failure")):
        with pytest.raises(ModelError) as failure:
            rebind(store, item["id"], "app.py|app.run", store.read().revision, "agent", "Discard failed recovery")
    assert failure.value.code == "SAVE_FAILED" and store.path.read_bytes() == intact
    rebind(store, item["id"], "app.py|app.run", store.read().revision, "agent", "Restore declared target version")
    restored = ModelStore(store.path).read().bindings[0]
    assert restored.id == original.id and restored.status == "current" and restored.snapshot_id == target.id
    assert restored.source_version == target.source.digest and restored.location == target.symbols["app.py|app.run"]
    assert restored.history[:-1] == before.history
    assert restored.history[-1].source_version == "b" * 64
    assert restored.history[-1].snapshot_id == before.snapshot_id and restored.history[-1].location == before.location
    assert restored.history[-1].reason == "Restore declared target version"
    assert item["id"] in query(store.read())["pending_ids"]
    rebind(store, item["id"], "app.py|app.run", store.read().revision, "agent", "Same target evidence")
    assert store.read().bindings[0].history == restored.history


@pytest.mark.parametrize("confirmed", [False, True])
def test_cli_new_scenario_review_survives_process_boundaries(
    maintained: ModelStore, tmp_path: Path, confirmed: bool
) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    if confirmed:
        resolve(store, original["id"], _review(target), store.read().revision)
    prefix = ("model", "--file", str(store.path))
    b = _business_b(store)
    patch_path = write(
        tmp_path / "new-business.json",
        {
            "author": "agent",
            "summary": "Share existing component",
            "operations": [
                {"action": "create", "collection": "scenarios", "id": b["id"], "value": b},
            ],
        },
    )
    cli(*prefix, "apply", "--patch", str(patch_path), "--expected-revision", str(store.read().revision))
    assert cli(*prefix, "maintenance", "--scenario", "business-B")["pending_ids"]
    target_path = write(tmp_path / "target-current.json", target.model_dump())
    report = cli(*prefix, "maintenance-preview", "--facts", str(target_path))
    cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(target_path),
        "--token",
        report["token"],
        "--expected-revision",
        str(report["revision"]),
        "--author",
        "agent",
    )
    latest = report["observations"][0]
    review_path = write(tmp_path / "current-review.json", _review(target))
    cli(
        *prefix,
        "maintenance-resolve",
        "--item",
        latest["id"],
        "--review",
        str(review_path),
        "--expected-revision",
        str(store.read().revision),
    )
    persisted = cli(*prefix, "maintenance", "--scenario", "business-B")
    assert latest["id"] not in persisted["pending_ids"]
    resolved = next(item for item in persisted["observations"] if item["id"] == latest["id"])
    assert "business-B" in resolved["resolution"]["object_ids"]
    if confirmed:
        old = next(item for item in store.read().maintenance if item.id == original["id"])
        assert old.resolution is not None and "business-B" not in old.resolution.object_ids


def test_historical_confirmation_does_not_close_new_context(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    _add_business_b(store)
    current_id = query(store.read(), scenario_id="business-B")["current_pending_ids"][0]
    before = store.path.read_bytes()
    stale_edit = _review(target) | {
        "outcome": "revised",
        "operations": [
            {
                "action": "update",
                "collection": "components",
                "id": "component",
                "value": {"responsibility": "Patch prepared against an obsolete interpretation scope"},
            }
        ],
    }
    with pytest.raises(ModelError) as error:
        resolve(store, original["id"], stale_edit, store.read().revision)
    assert error.value.code == "REVIEW_INVALID" and store.path.read_bytes() == before
    resolve(store, original["id"], _review(target), store.read().revision)
    old = next(item for item in store.read().maintenance if item.id == original["id"])
    assert old.resolution is not None
    assert old.resolution.object_versions == original["object_versions"]
    assert "business-B" not in old.resolution.object_ids
    assert current_id in query(store.read(), scenario_id="business-B")["current_pending_ids"]
    resolve(store, current_id, _review(target), store.read().revision)
    current = next(item for item in store.read().maintenance if item.id == current_id)
    assert current.resolution is not None and "business-B" in current.resolution.object_versions
    assert current.object_versions != old.object_versions
    assert not query(store.read())["pending_ids"]


def test_revised_review_covers_result_without_overwriting_earlier_confirmation(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    initial = record(store, target)["observations"][0]
    resolve(store, initial["id"], _review(target), store.read().revision)
    historical = store.read().maintenance[0].model_dump()
    original_responsibility = store.read().components[0].responsibility
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Change responsibility",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": "New explanation"},
                }
            ],
        },
    )
    current_id = query(store.read())["current_pending_ids"][0]
    resolve(
        store,
        current_id,
        _review(target)
        | {
            "author": "second-agent",
            "outcome": "revised",
            "reason": "Restore the previously reviewed responsibility",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": original_responsibility},
                }
            ],
        },
        store.read().revision,
    )
    assert store.read().maintenance[0].model_dump() == historical
    assert not query(store.read())["current_pending_ids"]
    assert not query(store.read())["pending_ids"]
    revised = next(item for item in store.read().maintenance if item.id == current_id)
    assert revised.resolution is not None and revised.resolution.author == "second-agent"


def test_coverage_preview_conflicts_after_model_evolution(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    record(store, target)
    old = preview(store.read(), target)
    _add_business_b(store)
    before = store.path.read_bytes()
    for revision, code in ((old["revision"], "REVISION_CONFLICT"), (store.read().revision, "PREVIEW_CONFLICT")):
        with pytest.raises(ModelError) as error:
            refresh(store, target, revision, old["token"], "agent")
        assert error.value.code == code and store.path.read_bytes() == before


def test_legacy_m2_resolution_is_preserved_without_invented_coverage(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    original = record(store, target)["observations"][0]
    resolve(store, original["id"], _review(target), store.read().revision)
    legacy = store.read().model_dump()
    old = legacy["maintenance"][0]
    old["id"] = "maintenance-" + digest(
        {"binding": old["binding_id"], "basis": old["basis"], "target": old["target_snapshot_id"]}
    )
    old.pop("coverage_version")
    old.pop("object_versions")
    old["resolution"].pop("object_versions")
    store.path.write_text(json.dumps(legacy))
    before = store.path.read_bytes()
    view = query(store.read())
    assert view["current_pending_ids"] and store.path.read_bytes() == before
    old_id = old["id"]
    current_id = view["current_pending_ids"][0]
    record(store, target)
    historical = next(item for item in store.read().maintenance if item.id == old_id)
    assert historical.coverage_version == "" and historical.object_versions == {}
    assert historical.resolution is not None and historical.resolution.author == "business-agent"
    assert (
        historical.resolution.object_versions == {}
        and historical.resolution.object_ids == old["resolution"]["object_ids"]
    )
    assert store.read().facts == validate_model(legacy).facts
    resolve(store, current_id, _review(target), store.read().revision)
    assert not query(store.read())["current_pending_ids"]
    assert next(item for item in store.read().maintenance if item.id == old_id) == historical


def test_cli_version_only_recovery_is_atomic_and_keeps_review_open(maintained: ModelStore, tmp_path: Path) -> None:
    store = maintained
    initial = store.read()
    binding = initial.bindings[0]
    history = [item.model_dump() for item in binding.history] + [
        {
            "snapshot_id": binding.snapshot_id,
            "source_version": binding.source_version,
            "location": binding.location.model_dump(),
            "reason": "Previous saved evidence",
        }
    ]
    prefix = ("model", "--file", str(store.path))
    patch_path = write(
        tmp_path / "version-only.json",
        {
            "author": "agent",
            "summary": "Declare changed version",
            "operations": [
                {
                    "action": "update",
                    "collection": "bindings",
                    "id": binding.id,
                    "value": {
                        "status": "changed",
                        "source_version": "c" * 64,
                        "reason": "Unmatched source version",
                        "history": history,
                    },
                }
            ],
        },
    )
    cli(*prefix, "apply", "--patch", str(patch_path), "--expected-revision", str(initial.revision))
    facts_path = write(tmp_path / "known-facts.json", initial.facts[-1].model_dump())
    report = cli(*prefix, "maintenance-preview", "--facts", str(facts_path))
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
    item = report["observations"][0]
    before = store.path.read_bytes()
    invalid = cli(
        *prefix,
        "maintenance-rebind",
        "--item",
        item["id"],
        "--candidate",
        "not-a-candidate",
        "--expected-revision",
        str(store.read().revision),
        "--author",
        "agent",
        "--reason",
        "Reject invalid location",
        success=False,
    )
    assert invalid["code"] == "CANDIDATE_INVALID" and store.path.read_bytes() == before
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
        "Restore known evidence",
    )
    cli(*prefix, "validate")
    restored = cli(*prefix, "read")["model"]["bindings"][0]
    assert restored["id"] == binding.id and restored["status"] == "current"
    assert restored["history"][:-1] == history and restored["history"][-1]["source_version"] == "c" * 64
    assert restored["history"][-1]["reason"] == "Restore known evidence"
    assert item["id"] in cli(*prefix, "maintenance", "--binding", binding.id)["pending_ids"]


def test_deleted_binding_keeps_historical_review_readable(maintained: ModelStore) -> None:
    store = maintained
    target = changed(store.read().facts[-1])
    item = record(store, target)["observations"][0]
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Explicitly remove continuing interpretation",
            "operations": [
                {"action": "delete", "collection": "scenarios", "id": "scenario"},
                {"action": "delete", "collection": "components", "id": "component"},
                {"action": "delete", "collection": "bindings", "id": "binding"},
            ],
        },
    )
    assert item["id"] in query(store.read())["pending_ids"]
    assert query(store.read())["current_coverage_ids"] == []
    before = store.path.read_bytes()
    with pytest.raises(ModelError) as error:
        resolve(
            store,
            item["id"],
            _review(target)
            | {
                "operations": [
                    {
                        "action": "update",
                        "collection": "components",
                        "id": "component",
                        "value": {"name": "Deleted"},
                    }
                ]
            },
            store.read().revision,
        )
    assert error.value.code == "REVIEW_INVALID" and store.path.read_bytes() == before
    resolve(store, item["id"], _review(target), store.read().revision)
    historical = store.read().maintenance[0]
    assert historical.resolution is not None and historical.resolution.object_versions == item["object_versions"]


def _review(target: Facts) -> dict:
    return {
        "author": "business-agent",
        "reason": "Inspected target and the listed interpretation state",
        "outcome": "confirmed",
        "source_version": target.source.digest,
    }


def _business_b(store: ModelStore) -> dict:
    value = store.read().scenarios[0].model_dump()
    value.update(id="business-B", name="New shared business", entry_step_id="step-B", order=["step-B"])
    value["steps"][0]["id"] = "step-B"
    return value


def _add_business_b(store: ModelStore) -> None:
    value = _business_b(store)
    store.apply(
        store.read().revision,
        {
            "author": "agent",
            "summary": "Add shared scenario B",
            "operations": [
                {"action": "create", "collection": "scenarios", "id": value["id"], "value": value},
            ],
        },
    )
