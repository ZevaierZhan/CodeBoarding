import json
import subprocess
import sys
from pathlib import Path

from architecture_model.store import ModelStore
from examples.architecture_model.demo import race


def test_competing_processes_share_revision_lock(store: ModelStore, tmp_path: Path) -> None:
    model = store.read().model_dump()
    model["components"][0]["id"] = "policy"
    model["scenarios"][0]["steps"][0]["component_ids"] = ["policy"]
    store.path.write_text(json.dumps(model))
    responses = race(store.path, tmp_path, 1)
    assert sum(response["ok"] for response in responses) == 1
    assert store.read().revision == 2
    winner = next(
        response["result"]["diff"]["changes"]["components"]["policy"]["after"]["name"]
        for response in responses
        if response["ok"]
    )
    assert store.read().components[0].name == winner


def test_separate_process_reads_missing_source_without_analysis(store: ModelStore) -> None:
    store.apply(
        1,
        {
            "author": "agent",
            "summary": "Mark missing",
            "operations": [
                {
                    "action": "update",
                    "collection": "bindings",
                    "id": "binding",
                    "value": {"status": "missing", "reason": "Source removed; keep evidence"},
                }
            ],
        },
    )
    before = store.path.read_bytes()
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "architecture_model",
            "model",
            "--file",
            str(store.path),
            "read",
            "--scenario",
            "scenario",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    result = json.loads(process.stdout)["result"]
    assert result["model"]["bindings"][0]["status"] == "missing"
    assert result["model"]["scenarios"][0]["steps"][0]["claim"]["explanation"]
    assert store.path.read_bytes() == before
