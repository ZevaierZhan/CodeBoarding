import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts, run_worker
from architecture_model.schema import Facts
from architecture_model.validation import digest, parse, validate_facts


@pytest.mark.parametrize("corruption", ["digest", "symbol", "call", "site", "file"])
def test_contradictory_facts_rejected(facts: dict, corruption: str) -> None:
    if corruption == "digest":
        facts["source"]["digest"] = "a" * 64
    elif corruption == "symbol":
        facts["symbols"]["app.py|app.run"]["content_hash"] = "a" * 64
    elif corruption in ("call", "site"):
        facts["calls"] = [
            {
                "source": "absent" if corruption == "call" else "app.run",
                "target": "app.run",
                "sites": [{"path": "absent.py", "line": 1, "column": 0}],
            }
        ]
    else:
        facts["file_locations"] = {"app.py": dict(facts["symbols"]["app.py|app.run"])}
    facts["id"] = digest({key: value for key, value in facts.items() if key != "id"})
    with pytest.raises(ModelError):
        validate_facts(parse(Facts, facts))


@pytest.mark.parametrize("location", [{"path": "../app.py"}, {"path": "C:/app.py"}, {"start": 2, "end": 1}])
def test_locations_reject_invalid_paths_or_ranges(facts: dict, location: dict) -> None:
    facts["symbols"]["app.py|app.run"].update(location)
    with pytest.raises(ModelError):
        parse(Facts, facts)


def test_worker_failure_cannot_publish(tmp_path: Path) -> None:
    tool = tmp_path / "tool"
    tool.write_text("placeholder")
    for process in (subprocess.CompletedProcess([], 1, "", "failure"), subprocess.CompletedProcess([], 0, "", "")):
        with patch("architecture_model.facts.run_worker", return_value=process):
            with pytest.raises(ModelError) as raised:
                export_facts(tmp_path, "p", tmp_path / "facts.json", tool, tool, tool)
        assert raised.value.code == "FACTS_FAILED"
    with patch("architecture_model.facts.run_worker", side_effect=subprocess.TimeoutExpired([], 180)):
        with pytest.raises(ModelError) as raised:
            export_facts(tmp_path, "p", tmp_path / "facts.json", tool, tool, tool)
    assert raised.value.code == "FACTS_FAILED"
    assert not (tmp_path / "facts.json").exists()


def test_model_imports_do_not_load_native_engine() -> None:
    script = """
import sys
from architecture_model.cli import run
run(['model', 'schema'])
assert 'static_analyzer' not in sys.modules
assert 'infra.monitoring.telemetry.service' not in sys.modules
assert 'agents.llm_config' not in sys.modules
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True, text=True, timeout=20)


def test_probe_rejects_swallowed_network_attempt_at_exit(tmp_path: Path) -> None:
    script = """
import atexit, pathlib, runpy, sys, threading
probe = runpy.run_path(sys.argv[1])
probe['STATE'].update(completed=True, telemetry_client_absent=True, baseline=set(threading.enumerate()), output=pathlib.Path(sys.argv[2]))
atexit.register(probe['finish'])
sys.addaudithook(probe['audit'])
try: sys.audit('socket.connect')
except AssertionError: pass
"""
    output = tmp_path / "negative.json"
    process = subprocess.run(
        [sys.executable, "-c", script, str(Path(__file__).with_name("native_probe.py")), str(output)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 1
    result = json.loads(output.read_text())
    assert result["status"] == "FAIL" and result["attempts"] == ["socket.connect"]


def test_worker_timeout_terminates_owned_process_group() -> None:
    with patch("architecture_model.facts.subprocess.Popen") as constructor:
        process = constructor.return_value
        process.pid = 123456
        process.communicate.side_effect = [subprocess.TimeoutExpired([], 180), ("", "")]
        with (
            patch("architecture_model.facts.subprocess.run") as terminate_tree,
            patch("architecture_model.facts.os.killpg", create=True) as terminate_group,
        ):
            with pytest.raises(subprocess.TimeoutExpired):
                run_worker(["worker"])
            if sys.platform == "win32":
                assert terminate_tree.call_args.args[0] == ["taskkill", "/PID", "123456", "/T", "/F"]
            else:
                assert terminate_group.called
        assert process.communicate.call_count == 2


def test_real_python_export_and_failure_paths(tmp_path: Path) -> None:
    required = [os.environ.get(f"M1_{name}", "") for name in ("NODE", "PYRIGHT", "TOKEI")]
    if not all(required):
        pytest.skip("Set M1_NODE, M1_PYRIGHT and M1_TOKEI to run the real native engine")
    worker = importlib.import_module("architecture_model.facts_worker")
    node, pyright, tokei = map(Path, required)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("def helper():\n    return 1\n\ndef run():\n    return helper()\n")
    facts = worker.extract(source.resolve(), "p", node, pyright, tokei)
    assert len(facts.symbols) == 2 and len(facts.calls) == 1
    assert facts.file_locations["app.py"].content_hash == facts.source.files["app.py"]
    assert worker.telemetry._client is None
    probe_result = tmp_path / "guard.json"
    probe = Path(__file__).with_name("native_probe.py")
    subprocess.run(
        [sys.executable, str(probe), str(source), *required, str(probe_result)],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert json.loads(probe_result.read_text())["status"] == "PASS"
    with (
        patch.object(sys, "argv", ["worker", str(source), "p", str(tmp_path / "worker.json"), *required]),
        patch.object(worker, "setup_logging"),
    ):
        assert worker.main() == 0
    output = tmp_path / "published.json"
    exported = export_facts(source, "p", output, node, pyright, tokei)
    assert exported.source.digest == facts.source.digest
    with pytest.raises(ModelError) as raised:
        export_facts(source, "p", output, node, pyright, tokei)
    assert raised.value.code == "ALREADY_EXISTS"
    (source / "app.py").write_text("def broken(:\n")
    with pytest.raises(SyntaxError):
        worker.extract(source, "p", node, pyright, tokei)
    with (
        patch.object(sys, "argv", ["worker", str(source), "p", str(tmp_path / "bad.json"), *required]),
        patch.object(worker, "setup_logging"),
    ):
        assert worker.main() == 1
    assert not (tmp_path / "bad.json").exists()
    (source / "app.py").unlink()
    with pytest.raises(ValueError, match="No Python"):
        worker.extract(source, "p", node, pyright, tokei)
    with patch.object(worker.telemetry, "_client", object()):
        with pytest.raises(RuntimeError, match="Telemetry"):
            worker.extract(source, "p", node, pyright, tokei)
