"""Exercise worker APIs only in a disposable Python process."""

import importlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts


def main() -> None:
    temporary, *required = sys.argv[1:]
    tmp_path = Path(temporary)
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


if __name__ == "__main__":
    main()
