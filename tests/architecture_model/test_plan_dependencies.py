import json
import subprocess
import sys
from pathlib import Path

import pytest

from architecture_model.cli import run
from architecture_model.errors import ModelError
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.maintenance_plan import LEGACY_PROTOCOL, check_plan, generate_plan
from architecture_model.maintenance_plan_states import evaluate_dependencies
from architecture_model.store import atomic_write
from architecture_model.validation import digest
from tests.architecture_model.test_maintenance_plan import dual
from tests.architecture_model.test_source_coverage import source, native_fixture, snapshot


def indexed(plan: dict, root: str = "all-files") -> dict[str, dict]:
    return {item["action"]: item for item in plan["items"] if item["root_id"] == root}


def assert_consistent(plan: dict) -> None:
    index = {item["id"]: item for item in plan["items"]}
    for item in plan["items"]:
        if item["status"] in ("ready", "requires-confirmation", "satisfied"):
            assert not item["unmet_hard_prerequisites"], item
            assert all(index[key]["prerequisite_satisfied"] for key in item["hard_prerequisites"]), item
        if item["status"] == "ready":
            assert item["can_execute_without_confirmation"] and not item["can_request_confirmation"]
            assert item["kind"] in ("read-only", "agent-decision")
        if item["status"] == "completed":
            assert item["evidence"]["kind"] == "recorded-model-state"
            assert item["evidence"]["root_id"] == item["root_id"]
            assert item["evidence"]["target_snapshot_id"] == item["basis"]["snapshot_id"]
            assert item["evidence"]["operation"] == item["action"]


def change_and_refresh_native(dual, source: Path, tmp_path: Path):
    store, mapping = dual
    (source / "src/rules.ts").write_text("export function rules() { return 2; }\n")
    target = native_fixture(source, tmp_path / "new-native.json")
    compared = preview(store.read(), target)
    refresh(store, target, store.read().revision, compared["token"], "test")
    return store, mapping


def test_changed_source_keeps_investigation_and_export_actionable(dual, source: Path, tmp_path: Path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    model_bytes = store.path.read_bytes()
    plan = generate_plan(store.read(), mapping, [], [])
    items = {item["action"]: item for item in plan["items"] if item["root_id"] == "all-files"}
    assert items["inspect-source"]["status"] == "ready"
    assert items["reexport"]["status"] == "requires-confirmation"
    assert items["maintenance-preview"]["status"] == "waiting"
    assert items["inspect-candidates"]["status"] != "ready"
    assert items["maintenance-rebind"]["status"] != "ready"
    assert items["maintenance-resolve"]["status"] != "ready"
    assert "facts_matching_observed_source_required" in items["maintenance-preview"]["reasons"]
    native = indexed(plan, "native")
    assert native["maintenance-refresh"]["status"] == "completed"
    assert native["inspect-candidates"]["status"] == "ready"
    assert native["maintenance-rebind"]["status"] == "requires-confirmation"
    assert native["maintenance-resolve"]["status"] == "requires-confirmation"
    assert_consistent(plan)
    assert store.path.read_bytes() == model_bytes


def test_missing_mapping_still_allows_mapping_investigation(dual):
    store, _ = dual
    plan = generate_plan(store.read(), None, [], [])
    for root in ("all-files", "native"):
        items = indexed(plan, root)
        assert items["inspect-mapping"]["status"] == "ready"
        assert items["inspect-source"]["status"] == "blocked"
        assert items["reexport"]["status"] == "blocked"
        for action in ("maintenance-refresh", "inspect-candidates", "maintenance-rebind", "maintenance-resolve"):
            assert items[action]["status"] == "blocked"
            assert items[action]["reasons"]
    assert_consistent(plan)


@pytest.mark.parametrize("scope", ["missing", "unsupported"])
def test_untrusted_scope_does_not_block_reading_source(dual, scope):
    store, mapping = dual
    model = store.read()
    facts = model.facts[0]
    old_id = facts.id
    if scope == "missing":
        facts.tools.pop("maintenance_scope")
    else:
        facts.tools["maintenance_scope"] = '{"protocol":"future"}'
    facts.id = digest(facts.model_dump(exclude={"id"}))
    for binding in model.bindings:
        if binding.snapshot_id == old_id:
            binding.snapshot_id = facts.id
    atomic_write(store.path, model.model_dump())
    plan = generate_plan(store.read(), mapping, [], [])
    items = indexed(plan)
    assert items["inspect-source"]["status"] == "ready"
    assert items["establish-baseline"]["status"] == "requires-confirmation"
    assert items["reexport"]["status"] == "blocked"
    assert "untrusted_extraction_scope" in items["reexport"]["reasons"]
    assert items["maintenance-preview"]["status"] == "blocked"
    assert_consistent(plan)


def test_new_facts_and_verified_preview_enable_confirmation_not_execution(dual, source, tmp_path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    facts_path = tmp_path / "new-all.json"
    facts = snapshot(source, facts_path)
    plan = generate_plan(store.read(), mapping, [facts_path], [])
    items = indexed(plan)
    assert items["reexport"]["status"] == "satisfied"
    assert not items["reexport"]["external_execution_observed"]
    assert items["maintenance-preview"]["status"] == "ready"
    assert items["maintenance-refresh"]["status"] == "waiting"
    assert "fresh_preview_response_required" in items["maintenance-refresh"]["reasons"]
    report = preview(store.read(), facts)
    response = tmp_path / "preview.json"
    atomic_write(response, {"ok": True, "result": report})
    before = store.path.read_bytes()
    output = tmp_path / "plan.json"
    args = [
        "model",
        "--file",
        str(store.path),
        "maintenance-plan",
        "--source-map",
        str(mapping),
        "--facts",
        str(facts_path),
        "--preview",
        str(response),
        "--output",
        str(output),
    ]
    run(args)
    plan = json.loads(output.read_text())
    items = indexed(plan)
    assert items["maintenance-preview"]["status"] == "satisfied"
    assert items["maintenance-refresh"]["status"] == "requires-confirmation"
    assert items["maintenance-refresh"]["can_request_confirmation"]
    assert items["maintenance-refresh"]["requires_user_confirmation"]
    for action in ("inspect-candidates", "maintenance-rebind", "maintenance-resolve"):
        assert items[action]["status"] == "waiting"
    assert report["token"] not in json.dumps(plan)
    assert check_plan(store.read(), plan)["requires_replan"] is False
    assert store.path.read_bytes() == before
    assert_consistent(plan)


@pytest.mark.parametrize("change", ["token", "revision", "target", "source"])
def test_old_or_incorrect_preview_never_enables_refresh(dual, source, tmp_path, change):
    store, mapping = dual
    facts_path = tmp_path / "proposed.json"
    facts = snapshot(source, facts_path)
    report = preview(store.read(), facts)
    receipt = tmp_path / "preview.json"
    if change == "token":
        report["token"] = "invalid"
    elif change == "revision":
        report["revision"] += 1
    elif change == "target":
        report["target_snapshot_id"] = store.read().facts[1].id
    elif change == "source":
        (source / "src/rules.ts").write_text("newer source")
    atomic_write(receipt, report)
    plan = generate_plan(store.read(), mapping, [facts_path], [], preview_paths=[receipt])
    assert indexed(plan)["maintenance-refresh"]["status"] != "requires-confirmation"
    assert indexed(plan)["maintenance-preview"]["status"] != "satisfied"
    assert_consistent(plan)


def test_extractor_change_requires_baseline_decision_with_indeterminate_preview(dual, source, tmp_path):
    store, mapping = dual
    path = tmp_path / "upgrade.json"
    target = snapshot(source, path)
    descriptor = json.loads(target.tools["maintenance_scope"])
    descriptor["implementation"] = "explicit-upgrade"
    target.tools["maintenance_scope"] = json.dumps(descriptor)
    target.id = digest(target.model_dump(exclude={"id"}))
    atomic_write(path, target.model_dump())
    report = preview(store.read(), target)
    assert report["observations"][0]["disposition"] == "indeterminate"
    response = tmp_path / "preview.json"
    atomic_write(response, report)
    plan = generate_plan(store.read(), mapping, [path], [], preview_paths=[response])
    assert indexed(plan)["establish-baseline"]["status"] == "requires-confirmation"
    assert indexed(plan)["maintenance-refresh"]["status"] == "requires-confirmation"
    assert "extraction_baseline_selection_required" in indexed(plan)["maintenance-refresh"]["reasons"]
    assert_consistent(plan)


def test_recorded_refresh_does_not_assert_later_workspace_synchronization(dual, source, tmp_path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    (source / "src/rules.ts").write_text("export function rules() { return 3; }\n")
    plan = generate_plan(store.read(), mapping, [], [])
    items = indexed(plan, "native")
    assert items["maintenance-refresh"]["status"] == "completed"
    assert not items["maintenance-refresh"]["workspace_matches_selected_manifest"]
    assert items["inspect-source"]["status"] == "ready"
    assert items["reexport"]["status"] == "requires-confirmation"
    assert items["maintenance-rebind"]["status"] == "waiting"
    assert items["maintenance-resolve"]["status"] == "waiting"
    assert_consistent(plan)


def test_no_pending_does_not_complete_unestablished_review_coverage(dual):
    store, mapping = dual
    model = store.read()
    for facts in model.facts:
        model.maintenance_targets[facts.source_root_id] = facts.id
    atomic_write(store.path, model.model_dump())
    plan = generate_plan(store.read(), mapping, [], [])
    assert plan["pending"]["total"] == 0
    item = indexed(plan)["maintenance-resolve"]
    assert item["status"] == "waiting"
    assert "interpretation_coverage_not_established" in item["reasons"]
    assert_consistent(plan)


def test_current_and_historical_pending_preserved_with_explicit_review_scope(dual, source, tmp_path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    old = store.read().maintenance
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Clarify changed interpretation",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": "Updated explanation scope"},
                }
            ],
        },
    )
    plan = generate_plan(store.read(), mapping, [], [])
    assert plan["pending"]["current_ids"] and plan["pending"]["historical_ids"]
    item = indexed(plan, "native")["maintenance-resolve"]
    assert item["status"] == "requires-confirmation"
    assert item["review_observation_ids"] and item["historical_pending_ids"]
    assert store.read().maintenance[: len(old)] == old
    assert_consistent(plan)


def test_ambiguous_or_missing_candidates_never_report_ready(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").unlink()
    target = native_fixture(source, tmp_path / "ambiguous.json")
    target.symbols = {
        path + "|rules": location.model_copy(update={"symbol": "rules", "kind": "FUNCTION"})
        for path, location in target.file_locations.items()
    }
    target.id = digest(target.model_dump(exclude={"id"}))
    report = preview(store.read(), target)
    refresh(store, target, store.read().revision, report["token"], "test")
    plan = generate_plan(store.read(), mapping, [], [])
    item = indexed(plan, "native")["maintenance-rebind"]
    assert item["status"] == "requires-confirmation"
    assert "ambiguous_candidates_require_agent_selection" in item["reasons"]
    assert_consistent(plan)


def test_recorded_target_without_candidates_does_not_enable_rebind(dual, source, tmp_path):
    store, mapping = dual
    (source / "src/rules.ts").unlink()
    target = native_fixture(source, tmp_path / "removed.json")
    report = preview(store.read(), target)
    assert report["observations"][0]["candidates"] == []
    refresh(store, target, store.read().revision, report["token"], "test")
    plan = generate_plan(store.read(), mapping, [], [])
    items = indexed(plan, "native")
    assert items["maintenance-refresh"]["status"] == "completed"
    assert items["inspect-candidates"]["status"] == "ready"
    assert items["maintenance-rebind"]["status"] == "waiting"
    assert "candidate_evidence_required" in items["maintenance-rebind"]["reasons"]
    assert not items["maintenance-rebind"]["candidate_observation_ids"]
    assert_consistent(plan)


def test_review_with_only_old_pending_requires_explicit_historical_target(dual, source, tmp_path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Clarify interpretation",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": "Current explanation"},
                }
            ],
        },
    )
    current = query(store.read())
    for observation in current["observations"]:
        if observation["id"] in current["current_pending_ids"]:
            resolve(
                store,
                observation["id"],
                {
                    "author": "test",
                    "reason": "Read current explanation",
                    "outcome": "confirmed",
                    "source_version": observation["target_source_version"],
                },
                store.read().revision,
            )
    plan = generate_plan(store.read(), mapping, [], [])
    assert not plan["pending"]["current_ids"] and plan["pending"]["historical_ids"]
    item = indexed(plan, "native")["maintenance-resolve"]
    assert item["status"] == "waiting"
    assert "historical_review_requires_explicit_target_scope" in item["reasons"]
    assert_consistent(plan)


def test_immutable_refresh_proof_does_not_complete_a_different_target(dual, source, tmp_path):
    store, mapping = change_and_refresh_native(dual, source, tmp_path)
    (source / "src/rules.ts").write_text("export function rules() { return 3; }\n")
    newer = tmp_path / "next-native.json"
    native_fixture(source, newer)
    plan = generate_plan(store.read(), mapping, [newer], [])
    items = indexed(plan, "native")
    assert items["maintenance-refresh"]["status"] == "waiting"
    assert items["maintenance-rebind"]["status"] != "completed"
    assert items["maintenance-resolve"]["status"] != "completed"
    assert_consistent(plan)


def test_blocked_and_waiting_predecessors_propagate_to_every_strict_dependent(dual):
    store, mapping = dual
    plan = generate_plan(store.read(), mapping, [], [])
    root = indexed(plan)
    compare = root["maintenance-preview"]
    assert compare["status"] == "ready"
    compare["conditions"]["blocking"] = ["injected_untrusted_input"]
    evaluate_dependencies(plan["items"])
    for action in ("maintenance-refresh", "inspect-candidates", "maintenance-rebind", "maintenance-resolve"):
        assert root[action]["status"] == "blocked"
        assert root[action]["unmet_hard_prerequisites"]
    assert indexed(plan, "native")["maintenance-preview"]["status"] == "ready"
    assert_consistent(plan)


@pytest.mark.parametrize("invalid", ["missing", "cycle", "cross-root"])
def test_invalid_dependency_graph_fails_loudly(dual, invalid):
    store, mapping = dual
    plan = generate_plan(store.read(), mapping, [], [])
    items = indexed(plan)
    if invalid == "missing":
        items["inspect-source"]["hard_prerequisites"] = ["unavailable"]
    elif invalid == "cycle":
        items["inspect-source"]["hard_prerequisites"] = [items["maintenance-refresh"]["id"]]
        items["maintenance-preview"]["hard_prerequisites"] = [items["inspect-source"]["id"]]
    else:
        items["inspect-source"]["hard_prerequisites"] = [indexed(plan, "native")["inspect-source"]["id"]]
    with pytest.raises(ModelError, match="prerequisite"):
        evaluate_dependencies(plan["items"])


def test_legacy_v1_plan_is_a_read_only_stale_artifact(dual, tmp_path):
    store, mapping = dual
    plan = generate_plan(store.read(), mapping, [], [])
    plan["protocol"] = LEGACY_PROTOCOL
    plan["inputs"].pop("previews")
    plan["plan_id"] = digest({key: value for key, value in plan.items() if key != "plan_id"})
    before = store.path.read_bytes()
    report = check_plan(store.read(), plan)
    assert report["status"] == "stale" and report["requires_replan"]
    assert any(item["code"] == "legacy_item_states_require_replan" for item in report["reasons"])
    path = tmp_path / "old-plan.json"
    atomic_write(path, plan)
    result = subprocess.run(
        [sys.executable, "skills/codeboarding-modeling/scripts/model_context.py", "plan", "--report", str(path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1 and "regeneration" in result.stdout
    assert store.path.read_bytes() == before


def test_verified_preview_becomes_stale_after_other_store_write(dual, source, tmp_path):
    store, mapping = dual
    facts_path = tmp_path / "facts.json"
    facts = snapshot(source, facts_path)
    receipt = tmp_path / "preview.json"
    atomic_write(receipt, preview(store.read(), facts))
    plan = generate_plan(store.read(), mapping, [facts_path], [], preview_paths=[receipt])
    assert indexed(plan)["maintenance-refresh"]["status"] == "requires-confirmation"
    store.apply(
        store.read().revision,
        {
            "author": "other",
            "summary": "Concurrent explanation",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": "Concurrent update"},
                }
            ],
        },
    )
    assert check_plan(store.read(), plan)["status"] == "stale"
    new = generate_plan(store.read(), mapping, [facts_path], [], preview_paths=[receipt])
    assert indexed(new)["maintenance-refresh"]["status"] == "waiting"
    assert_consistent(new)
