from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.cli import run
from architecture_model.coverage import coverage_report
from architecture_model.errors import ModelError
from architecture_model.maintenance import query
from architecture_model.maintenance_coverage import capture_coverage
from architecture_model.schema import Model
from architecture_model.store import ModelStore, atomic_write, model_diff
from architecture_model.validation import digest, validate_model
from tests.architecture_model.test_maintenance import changed, record
from tests.architecture_model.test_multilanguage import attach_roots
from tests.architecture_model.test_source_coverage import model_with_roots, native_fixture, snapshot, source


def update(value: dict) -> dict:
    return {
        "author": "agent",
        "summary": "Clarify analysis",
        "operations": [{"action": "update", "collection": "scenarios", "id": "scenario", "value": value}],
    }


@pytest.fixture
def extended(store: ModelStore) -> ModelStore:
    scenario = store.read().scenarios[0].model_dump()
    scenario.update(analysis_kind="operation", facet_order=["Decision", "Lifetime"])
    scenario["steps"][0]["facet_checks"] = {"Decision": "The entry returns a constant."}
    topic = deepcopy(scenario)
    topic.update(id="topic", name="Compare mechanisms", analysis_kind="comparison", entry_step_id="topic-item")
    topic["steps"][0]["id"] = "topic-item"
    topic["order"] = ["topic-item"]
    proposal = update(scenario)
    proposal["operations"].append({"action": "create", "collection": "scenarios", "id": "topic", "value": topic})
    store.apply(1, proposal)
    return store


def test_old_shape_and_explicit_empty_values_round_trip(store: ModelStore) -> None:
    old = store.read().model_dump()
    scenario = old["scenarios"][0]
    assert "analysis_kind" not in scenario and "facet_order" not in scenario
    assert "facet_checks" not in scenario["steps"][0]
    assert validate_model(old).model_dump() == old
    scenario.update(analysis_kind="operation", facet_order=[])
    scenario["steps"][0]["facet_checks"] = {}
    assert validate_model(old).model_dump() == old
    assert Model.model_json_schema()["$defs"]["Step"]["additionalProperties"] is False


def test_complete_typed_fixture_round_trip(extended: ModelStore) -> None:
    original = extended.read().model_dump()
    assert validate_model(json.loads(json.dumps(original))).model_dump() == original
    assert Model.model_validate_json(json.dumps(original)).model_dump() == original
    assert original["scenarios"][0]["steps"][0]["facet_checks"]["Decision"]
    assert original["scenarios"][1]["analysis_kind"] == "comparison"


def test_public_complete_fixture_and_published_schema() -> None:
    root = Path(__file__).resolve().parents[2]
    fixture = json.loads((root / "examples/architecture_model/schema_compat/model.json").read_text())
    assert validate_model(fixture).model_dump() == fixture
    published = json.loads((root / "docs/architecture-model-v1.schema.json").read_text())
    assert published == Model.model_json_schema()


def test_facets_survive_independent_language_roots(extended: ModelStore, facts: dict) -> None:
    before = extended.read().scenarios
    attach_roots(extended, facts)
    assert extended.read().scenarios == before
    assert {item.source_root_id for item in extended.read().facts} >= {"frontend", "backend"}


def test_facets_and_file_only_coverage_share_full_model(source: Path, tmp_path: Path) -> None:
    store = model_with_roots(
        tmp_path, [snapshot(source, tmp_path / "files.json"), native_fixture(source, tmp_path / "native.json")]
    )
    scenario = store.read().scenarios[0].model_dump()
    scenario.update(analysis_kind="comparison", facet_order=["Decision"])
    scenario["steps"][0]["facet_checks"] = {"Decision": "Evidence across independent roots."}
    store.apply(1, update(scenario))
    before = store.path.read_bytes()
    report = coverage_report(store.read(), {"all-files": source, "native": source}, [], [], [])
    assert report["summary"]["confirmed_overlaps"] == 3
    assert store.path.read_bytes() == before


@pytest.mark.parametrize(
    "value,code",
    [
        ({"analysis_kind": "private-domain"}, "SCHEMA_INVALID"),
        ({"analysis_kind": None}, "SCHEMA_INVALID"),
        ({"facet_order": "Decision"}, "SCHEMA_INVALID"),
        ({"facet_order": [1]}, "SCHEMA_INVALID"),
        ({"facet_order": [""]}, "SCHEMA_INVALID"),
        ({"facet_order": ["Decision", "Decision"]}, "FACET_ORDER"),
        ({"facet_order": []}, "DANGLING_REFERENCE"),
        ({"facet_order": ["Renamed"]}, "DANGLING_REFERENCE"),
        ({"unexpected_extension": {}}, "SCHEMA_INVALID"),
    ],
)
def test_invalid_extensions_leave_bytes_unchanged(extended: ModelStore, value: dict, code: str) -> None:
    before = extended.path.read_bytes()
    with pytest.raises(ModelError) as failure:
        extended.apply(2, update(value))
    assert failure.value.code == code
    assert extended.path.read_bytes() == before


@pytest.mark.parametrize("checks", [[], None, {"Decision": {}}, {"Decision": 1}, {"Decision": ""}, {"Unknown": "x"}])
def test_invalid_check_values_and_labels(extended: ModelStore, checks: object) -> None:
    scenario = extended.read().scenarios[0].model_dump()
    scenario["steps"][0]["facet_checks"] = checks
    before = extended.path.read_bytes()
    with pytest.raises(ModelError):
        extended.apply(2, update({"steps": scenario["steps"]}))
    assert extended.path.read_bytes() == before


def test_comparison_rejects_execution_transitions(extended: ModelStore) -> None:
    with pytest.raises(ModelError) as failure:
        extended.preview(
            update(
                {
                    "analysis_kind": "comparison",
                    "transitions": [{"source_id": "step", "target_id": "step", "kind": "loop", "condition": "repeat"}],
                }
            )
        )
    assert failure.value.code == "SCENARIO_KIND"


def test_read_validate_diff_export_preserve_bytes(extended: ModelStore, tmp_path: Path) -> None:
    prefix = ["model", "--file", str(extended.path)]
    amendment = tmp_path / "patch.json"
    atomic_write(amendment, update({"name": "Clearer name"}))
    before = extended.path.read_bytes()
    assert run([*prefix, "validate"])["valid"]
    read = run([*prefix, "read"])
    assert read["model"]["scenarios"][0]["facet_order"] == ["Decision", "Lifetime"]
    assert run([*prefix, "diff", "--patch", str(amendment)])["candidate_revision"] == 3
    html = tmp_path / "view.html"
    run([*prefix, "export-html", "--output", str(html)])
    assert '"facet_checks"' in html.read_text(encoding="utf-8")
    assert extended.path.read_bytes() == before


def test_patch_preserves_extensions_and_records_content_change(extended: ModelStore) -> None:
    original = extended.read().model_dump()
    extended.apply(2, update({"name": "Renamed"}))
    after = extended.read().model_dump()
    expected = deepcopy(original["scenarios"])
    expected[0]["name"] = "Renamed"
    assert after["scenarios"] == expected
    scenario = after["scenarios"][0]
    scenario["steps"][0]["facet_checks"]["Lifetime"] = "Independent of browsing state."
    proposed, difference = extended.preview(update({"steps": scenario["steps"]}))
    assert difference["scenario_ids"] == ["scenario"]
    assert proposed.revision == 4
    extended.apply(3, update({"steps": scenario["steps"]}))
    saved = extended.read().model_dump()
    for collection in ("facts", "bindings", "components", "relations", "opinions", "verifications"):
        assert saved[collection] == original[collection]
    assert saved["scenarios"][1] == original["scenarios"][1]
    assert saved["scenarios"][0]["transitions"] == original["scenarios"][0]["transitions"]
    assert saved["revisions"][:3] == original["revisions"]
    assert saved["revisions"][-1]["scenario_ids"] == ["scenario"]


def test_extension_conflict_and_failed_write_are_atomic(extended: ModelStore) -> None:
    before = extended.path.read_bytes()
    with pytest.raises(ModelError) as conflict:
        extended.apply(1, update({"name": "stale"}))
    assert conflict.value.code == "REVISION_CONFLICT"
    with patch("architecture_model.store.os.replace", side_effect=OSError("blocked")):
        with pytest.raises(ModelError) as failure:
            extended.apply(2, update({"name": "unsaved"}))
    assert failure.value.code == "SAVE_FAILED"
    assert extended.path.read_bytes() == before


@pytest.mark.parametrize("field", ["checks", "order", "kind"])
def test_facet_edits_append_coverage_without_losing_old_reviews(extended: ModelStore, field: str) -> None:
    record(extended, changed(extended.read().facts[0]))
    before = extended.read()
    old_report = query(before)
    old_ids = set(old_report["current_coverage_ids"])
    scenario = before.scenarios[0].model_dump()
    if field == "checks":
        scenario["steps"][0]["facet_checks"]["Decision"] = "Revised interpretation requiring review."
        amendment = {"steps": scenario["steps"]}
    elif field == "order":
        amendment = {"facet_order": list(reversed(scenario["facet_order"]))}
    else:
        amendment = {"analysis_kind": "comparison"}
    extended.apply(before.revision, update(amendment))
    after = extended.read()
    new_report = query(after)
    assert old_ids - set(new_report["current_coverage_ids"])
    assert set(old_report["pending_ids"]) <= set(new_report["pending_ids"])
    assert after.maintenance[: len(before.maintenance)] == before.maintenance
    assert after.facts == before.facts and after.bindings == before.bindings


def test_explicit_defaults_do_not_invalidate_legacy_fingerprints(store: ModelStore) -> None:
    record(store, changed(store.read().facts[0]))
    before = store.read()
    scenario = before.scenarios[0].model_dump()
    scenario.update(analysis_kind="operation", facet_order=[])
    scenario["steps"][0]["facet_checks"] = {}
    raw = before.model_dump()
    raw["scenarios"][0] = scenario
    explicit = validate_model(raw)
    for item in before.maintenance:
        assert capture_coverage(before, item, model_diff).id == capture_coverage(explicit, item, model_diff).id
    # Match both the pre-extension and originating branch fingerprint conventions.
    covered = before.maintenance[0].object_versions
    assert covered["scenario"] == digest(before.scenarios[0].model_dump())
