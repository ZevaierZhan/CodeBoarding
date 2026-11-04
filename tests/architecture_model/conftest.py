import hashlib
from pathlib import Path

import pytest

from architecture_model.store import ModelStore
from architecture_model.validation import digest


@pytest.fixture
def facts() -> dict:
    content_hash = hashlib.sha256(b"def run(): return 1\n").hexdigest()
    manifest = {"app.py": content_hash}
    snapshot = {
        "schema_version": 1,
        "project_id": "project",
        "source": {"digest": digest(manifest), "git_commit": "", "files": manifest, "scope": "unit fixture"},
        "symbols": {
            "app.py|app.run": {
                "path": "app.py",
                "symbol": "app.run",
                "kind": "FUNCTION",
                "content_hash": content_hash,
                "start": 1,
                "end": 1,
            }
        },
        "file_locations": {},
        "calls": [],
        "tools": {"engine": "unit fixture"},
        "limitations": ["Unit-test snapshot"],
    }
    return snapshot | {"id": digest(snapshot)}


@pytest.fixture
def store(tmp_path: Path, facts: dict) -> ModelStore:
    store = ModelStore(tmp_path / "architecture-model.json")
    store.initialize({"id": "project", "name": "Example", "boundary": "Fixture only"}, "test")
    claim = {"kind": "code_fact", "explanation": "app.run returns 1", "binding_ids": ["binding"]}
    values = {
        "facts": facts,
        "bindings": {
            "id": "binding",
            "snapshot_id": facts["id"],
            "source_version": facts["source"]["digest"],
            "location": facts["symbols"]["app.py|app.run"],
            "status": "current",
        },
        "components": {
            "id": "component",
            "name": "Entry",
            "responsibility": "Return one",
            "rationale": "Fixture boundary",
            "binding_ids": ["binding"],
            "claim": claim,
        },
        "scenarios": {
            "id": "scenario",
            "name": "Run",
            "entry_step_id": "step",
            "order": ["step"],
            "steps": [{"id": "step", "component_ids": ["component"], "binding_ids": ["binding"], "claim": claim}],
            "transitions": [],
            "claim": claim,
        },
    }
    store.apply(
        0,
        {
            "author": "test",
            "summary": "Initial explanation",
            "operations": [
                {"action": "create", "collection": collection, "id": value["id"], "value": value}
                for collection, value in values.items()
            ],
        },
    )
    return store
