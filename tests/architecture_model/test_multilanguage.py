from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from architecture_model.errors import ModelError
from architecture_model.maintenance import preview, refresh, rebind, query
from architecture_model.schema import Facts
from architecture_model.validation import digest, parse, validate_facts, validate_model
from architecture_model.viewer import projection


def rooted(value: dict, root: str, language: str = "python") -> dict:
    snapshot = deepcopy(value)
    snapshot.update(
        schema_version=2,
        source_root_id=root,
        file_languages={path: language for path in value["source"]["files"]},
        file_projects={path: "." for path in value["source"]["files"]},
    )
    snapshot["id"] = digest({key: item for key, item in snapshot.items() if key != "id"})
    return snapshot


def create(collection: str, value: dict) -> dict:
    return {"action": "create", "collection": collection, "id": value["id"], "value": value}


def attach_roots(store, facts):
    snapshots = [rooted(facts, root) for root in ("frontend", "backend")]
    operations = []
    for root, snapshot in zip(("frontend", "backend"), snapshots):
        operations.append(create("facts", snapshot))
        location = snapshot["symbols"]["app.py|app.run"]
        operations.append(
            create(
                "bindings",
                {
                    "id": root + "-binding",
                    "snapshot_id": snapshot["id"],
                    "source_version": snapshot["source"]["digest"],
                    "location": location,
                    "status": "current",
                },
            )
        )
        operations.append(
            create(
                "components",
                {
                    "id": root,
                    "name": root,
                    "responsibility": "same path separate root",
                    "rationale": "separate repositories",
                    "binding_ids": [root + "-binding"],
                    "claim": {
                        "kind": "code_fact",
                        "explanation": "Root-specific evidence",
                        "binding_ids": [root + "-binding"],
                    },
                },
            )
        )
    store.apply(store.read().revision, {"author": "test", "summary": "Independent roots", "operations": operations})
    return snapshots


def test_legacy_snapshot_roundtrip_preserves_digest_and_payload(facts, store):
    assert parse(Facts, facts).model_dump() == facts
    assert store.read().facts[0].model_dump() == facts
    validate_facts(parse(Facts, facts))
    assert "maintenance_targets" not in store.read().model_dump()
    assert "relation_ids" not in store.read().scenarios[0].model_dump()


def test_root_identity_and_call_endpoints_are_snapshot_scoped(facts):
    first, second = rooted(facts, "a"), rooted(facts, "b")
    assert first["id"] != second["id"]
    first["calls"] = [{"source": "app.py|app.run", "target": "app.py|app.run", "sites": []}]
    first["id"] = digest({key: value for key, value in first.items() if key != "id"})
    validate_facts(parse(Facts, first))
    first["calls"][0]["target"] = "app.run"
    first["id"] = digest({key: value for key, value in first.items() if key != "id"})
    with pytest.raises(ModelError, match="Call endpoint"):
        validate_facts(parse(Facts, first))


@pytest.mark.parametrize(
    "change",
    [{"source_root_id": ""}, {"file_languages": {}}, {"file_projects": {}}, {"surprise": True}, {"schema_version": 3}],
)
def test_new_snapshot_rejects_invalid_identity(facts, change):
    value = rooted(facts, "root") | change
    with pytest.raises(ModelError):
        parse(Facts, value)


def test_one_root_refresh_retains_other_roots_and_history(store, facts):
    frontend, backend = attach_roots(store, facts)
    target = deepcopy(frontend)
    target["source"]["files"]["app.py"] = "a" * 64
    target["source"]["digest"] = digest(target["source"]["files"])
    target["symbols"]["app.py|app.run"]["content_hash"] = "a" * 64
    target["id"] = digest({key: item for key, item in target.items() if key != "id"})
    target_model = parse(Facts, target)
    report = preview(store.read(), target_model)
    assert [item["binding_id"] for item in report["observations"]] == ["frontend-binding"]
    refresh(store, target_model, store.read().revision, report["token"], "test")
    current = store.read()
    assert current.maintenance_targets == {"frontend": target["id"]}
    assert next(item for item in current.facts if item.id == backend["id"]).model_dump() == backend
    observation = report["observations"][0]
    assert observation["disposition"] == "indeterminate"  # old fixture has no extraction descriptor
    rebind(store, observation["id"], "app.py|app.run", current.revision, "test", "Read edited frontend")
    bindings = {item.id: item for item in store.read().bindings}
    assert bindings["frontend-binding"].history[0].snapshot_id == frontend["id"]
    assert bindings["backend-binding"].snapshot_id == backend["id"]
    assert not bindings["backend-binding"].history


def test_contract_persists_both_sides_and_impacts_shared_scenarios(store, facts):
    attach_roots(store, facts)
    claim = {
        "kind": "inference",
        "explanation": "Explicit cross-process candidate",
        "binding_ids": ["frontend-binding", "backend-binding"],
        "issues": ["Registration not established"],
    }
    relation: dict = {
        "id": "ipc",
        "source_id": "frontend",
        "target_id": "backend",
        "meaning": "invoke command",
        "claim": claim,
        "contract": {
            "mechanism": "tauri-ipc",
            "operation": "read_file",
            "caller_binding_ids": ["frontend-binding"],
            "receiver_binding_ids": ["backend-binding"],
            "rationale": "Inspected both sides",
            "uncertainties": ["Registration pending"],
        },
    }
    scenario = store.read().scenarios[0].model_dump()
    scenario["relation_ids"] = ["ipc"]
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Shared contract",
            "operations": [
                create("relations", relation),
                {
                    "action": "update",
                    "collection": "scenarios",
                    "id": scenario["id"],
                    "value": {"relation_ids": ["ipc"]},
                },
            ],
        },
    )
    assert store.read().relations[0].contract.operation == "read_file"
    bad = deepcopy(relation)
    bad["contract"]["status"] = "evidenced"
    original = store.path.read_bytes()
    with pytest.raises(ModelError, match="Evidenced contract"):
        store.apply(
            store.read().revision,
            {
                "author": "test",
                "summary": "Bad promotion",
                "operations": [
                    {"action": "update", "collection": "relations", "id": "ipc", "value": {"contract": bad["contract"]}}
                ],
            },
        )
    assert store.path.read_bytes() == original
    target = rooted(facts, "frontend")
    report = preview(store.read(), parse(Facts, target))
    item = report["observations"][0]
    assert "ipc" in item["relation_ids"] and "scenario" in item["scenario_ids"]
    assert "backend-binding" not in {entry["binding_id"] for entry in report["observations"]}


def test_source_mapping_is_root_specific_and_read_only(store, facts, tmp_path: Path):
    attach_roots(store, facts)
    front = tmp_path / "front"
    back = tmp_path / "back"
    front.mkdir()
    back.mkdir()
    (front / "app.py").write_bytes(b"def run(): return 1\n")
    (back / "app.py").write_bytes(b"different version\n")
    before = store.path.read_bytes()
    payload = projection(store.read(), source_map={"frontend": front, "backend": back})
    assert payload["snippets"]["frontend-binding"][0]["status"] == "verified"
    assert payload["snippets"]["backend-binding"][0]["status"] == "mismatch"
    assert projection(store.read(), source_root=front)["snippets"]["frontend-binding"][0]["status"] == "unavailable"
    assert store.path.read_bytes() == before


def test_bad_root_target_rolls_back(store, facts):
    attach_roots(store, facts)
    value = store.read().model_dump()
    value["maintenance_targets"] = {"frontend": value["facts"][-1]["id"]}
    with pytest.raises(ModelError, match="another source root"):
        validate_model(value)


def test_real_multilanguage_exports_and_failures(tmp_path: Path):
    tools = os.environ.get("M5_TOOLS", "")
    if not tools:
        pytest.skip("Set M5_TOOLS to explicit native language tool configuration")
    fixture = Path("examples/architecture_model/multilanguage/source").resolve()
    for name, repo in (("frontend", fixture / "frontend"), ("backend", fixture / "backend"), ("mixed", fixture)):
        destination = tmp_path / f"{name}.json"
        command = [
            sys.executable,
            "-m",
            "architecture_model",
            "facts",
            "export",
            "--repo",
            str(repo),
            "--project-id",
            "project",
            "--source-root-id",
            name,
            "--tools",
            tools,
            "--output",
            str(destination),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=210)
        assert result.returncode == 0, result.stderr
        facts = parse(Facts, json.loads(destination.read_text(encoding="utf-8")))
        validate_facts(facts)
        assert facts.symbols and facts.calls
        assert all("|" in call.source and "|" in call.target for call in facts.calls)
        if name == "mixed":
            assert set(facts.file_languages.values()) == {"typescript", "rust"}
        failure_output = tmp_path / f"{name}-failure.json"
        result = subprocess.run(
            command[:-1] + [str(failure_output), "--source-root-id", ""], capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 1 and not failure_output.exists()


def test_committed_trial_preserves_versions_and_reuses_architecture():
    folder = Path("examples/architecture_model/multilanguage/model")
    first = validate_model(json.loads((folder / "revision-1.json").read_text(encoding="utf-8")))
    final = validate_model(json.loads((folder / "model.json").read_text(encoding="utf-8")))
    assert final.scenarios[0] == first.scenarios[0]
    assert final.components == first.components and final.relations == first.relations
    assert len(final.scenarios) == 2
    assert all("read-file-ipc" in scenario.relation_ids for scenario in final.scenarios)
    assert len({snapshot.source.git_commit for snapshot in final.facts}) == 2
    assert [snapshot.model_dump() for snapshot in final.facts[:2]] == [
        snapshot.model_dump() for snapshot in first.facts
    ]
    assert {item.binding_id for item in final.maintenance} == {"open", "preview", "invoke"}
    assert all(item.resolution is not None for item in final.maintenance)
    assert query(final)["pending_ids"] == []
    source = Path("examples/architecture_model/multilanguage")
    payload = projection(
        final, source_map={"frontend": source / "source-current/frontend", "backend": source / "source/backend"}
    )
    assert all(entries[0]["status"] == "verified" for entries in payload["snippets"].values())
    assert all(
        entries[1]["status"] == "mismatch"
        for name, entries in payload["snippets"].items()
        if name in {"open", "preview", "invoke"}
    )
