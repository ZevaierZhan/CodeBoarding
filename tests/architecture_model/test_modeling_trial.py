import gzip
import json
import re
from pathlib import Path
from shutil import copyfile
from string import Template
from uuid import uuid4

from architecture_model.maintenance import query
from architecture_model.store import ModelStore, load_json
from architecture_model.validation import validate_model

ROOT = Path(__file__).resolve().parents[2]
TRIAL = ROOT / "examples/architecture_model/codeboarding"
TEMPLATES = ROOT / "skills/codeboarding-modeling/assets"


def test_trial_preserves_business_and_identity_across_sessions_and_feedback() -> None:
    stages = [
        validate_model(json.loads(gzip.decompress(path.read_bytes()))) for path in sorted(TRIAL.glob("*.model.json.gz"))
    ]
    final = validate_model(load_json(TRIAL / "model.json"))
    assert stages[-1] == final
    assert {stage.id for stage in stages} == {final.id}
    assert [record.revision for record in final.revisions] == list(range(final.revision + 1))
    previous = stages[0]
    for stage in stages[1:]:
        assert stage.revisions[: len(previous.revisions)] == previous.revisions
        assert {item.id for item in stage.components} >= {item.id for item in previous.components}
        assert {item.id: item for item in stage.scenarios}.items() >= {
            item.id: item for item in previous.scenarios
        }.items()
        previous = stage
    assert len(final.components) == 7
    shared = [
        set(identity for step in scenario.steps for identity in step.component_ids) for scenario in final.scenarios
    ]
    assert shared[0] & shared[1] >= {"cli", "store", "validation"}


def test_source_experiment_preserves_catalogs_bindings_and_version_specific_reviews() -> None:
    model = validate_model(load_json(TRIAL / "model.json"))
    before = json.loads((TRIAL / "facts-before.json").read_text(encoding="utf-8"))
    after = json.loads((TRIAL / "facts-after.json").read_text(encoding="utf-8"))
    assert [snapshot.model_dump() for snapshot in model.facts] == [before, after]
    assert set(before["source"]["files"]) == set(after["source"]["files"])
    assert {
        path for path, content in before["source"]["files"].items() if after["source"]["files"][path] != content
    } == {"architecture_model/viewer.py"}
    for binding in model.bindings:
        if binding.location.path == "architecture_model/viewer.py":
            assert binding.snapshot_id == after["id"]
            assert binding.history[0].snapshot_id == before["id"]
        else:
            assert binding.snapshot_id == before["id"]
            assert not binding.history
    report = query(model)
    assert len(report["current_pending_ids"]) == 2
    current = [item for item in report["observations"] if item["id"] in report["current_coverage_ids"]]
    export = [item for item in current if item["binding_id"] == "e-export-html"]
    assert len(export) == 1 and export[0]["resolution"] is not None
    old = [
        item
        for item in report["observations"]
        if item["binding_id"] == "e-export-html" and item["id"] != export[0]["id"]
    ]
    assert any(item["resolution"] and item["object_versions"] != export[0]["object_versions"] for item in old)
    assert all(check.source_version == before["source"]["digest"] for check in model.verifications)
    assert {check.status for check in model.verifications} == {"planned", "executed"}
    assert model.opinions[0].author == "preset-feedback-rehearsal"


def test_final_document_freezes_the_complete_model_and_real_evidence() -> None:
    model = validate_model(load_json(TRIAL / "model.json"))
    html = (TRIAL / "index.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="model-data">(.*?)</script>', html, re.DOTALL)
    assert match
    payload = json.loads(match[1])
    assert payload["model"] == model.model_dump()
    assert payload["maintenance"] == query(model)
    for binding in model.bindings:
        current, *history = payload["snippets"][binding.id]
        assert current["status"] == "verified"
        assert current["location"] == binding.location.model_dump()
        if history:
            assert history[0]["status"] == "mismatch"


def test_skill_templates_build_a_valid_increment_without_replacing_existing_objects(tmp_path: Path) -> None:
    path = tmp_path / "model.json"
    copyfile(TRIAL / "model.json", path)
    store = ModelStore(path)
    before = path.read_bytes()
    current = store.read()
    binding = current.bindings[0].id
    identity = str(uuid4())
    component = expand(
        "component",
        component_id=identity,
        name="Reviewed logical boundary",
        parent_id="modeling",
        responsibility="Inspect JSON command handling",
        rationale="Explicit exercise using real CLI evidence",
        binding_ids=[binding],
        explanation="A candidate boundary for reviewer discussion",
        assumptions=["Template exercise only; not accepted architecture"],
        issues=[],
    )
    scenario_id, step_id = str(uuid4()), str(uuid4())
    scenario = expand(
        "scenario",
        scenario_id=scenario_id,
        name="Template exercise",
        entry_step_id=step_id,
        steps=[
            {"id": step_id, "component_ids": [identity, "cli"], "binding_ids": [binding], "claim": component["claim"]}
        ],
        order=[step_id],
        transitions=[],
        explanation="Locally scoped template validation",
        binding_ids=[binding],
        assumptions=["No runtime execution implied"],
        issues=[],
    )
    patch = expand(
        "patch",
        author="template-check",
        summary="Exercise all distributed templates",
        operations=[
            {"action": "create", "collection": collection, "id": value["id"], "value": value}
            for collection, value in (("components", component), ("scenarios", scenario))
        ],
    )
    proposed, difference = store.preview(patch)
    assert path.read_bytes() == before
    assert proposed.scenarios[:-1] == current.scenarios
    assert proposed.components[:-1] == current.components
    assert scenario_id in difference["scenario_ids"]
    assert proposed.revision == current.revision + 1


def expand(template: str, **values: object) -> dict:
    content = (TEMPLATES / f"{template}.json.template").read_text(encoding="utf-8")
    return json.loads(Template(content).substitute({key: json.dumps(value) for key, value in values.items()}))
