import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.cli import main, run
from architecture_model.errors import ModelError
from architecture_model.facts import export_facts
from architecture_model.store import ModelStore


def test_cli_library_and_machine_output(store: ModelStore, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    prefix = ["model", "--file", str(store.path)]
    assert run([*prefix, "read"])["revision"] == 1
    assert run([*prefix, "validate"])["valid"] is True
    assert run([*prefix, "schema"])["additionalProperties"] is False
    patch_file = tmp_path / "patch.json"
    patch_file.write_text(
        json.dumps(
            {
                "author": "agent",
                "summary": "Rename",
                "operations": [
                    {"action": "update", "collection": "components", "id": "component", "value": {"name": "New"}}
                ],
            }
        )
    )
    for action in ("validate", "diff"):
        assert run([*prefix, action, "--patch", str(patch_file)])["committed"] is False
    assert run([*prefix, "apply", "--expected-revision", "1", "--patch", str(patch_file)])["revision"] == 2
    with patch.object(
        sys, "argv", ["codeboarding-model", *prefix, "apply", "--expected-revision", "1", "--patch", str(patch_file)]
    ):
        assert main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "REVISION_CONFLICT"
    with patch.object(sys, "argv", ["codeboarding-model", *prefix, "read"]):
        assert main() == 0
    assert json.loads(capsys.readouterr().out)["result"]["revision"] == 2


def test_cli_initialization(tmp_path: Path) -> None:
    project = tmp_path / "project.json"
    project.write_text(json.dumps({"id": "p", "name": "P", "boundary": "scope"}))
    assert (
        run(["model", "--file", str(tmp_path / "model.json"), "init", "--project", str(project), "--author", "agent"])[
            "revision"
        ]
        == 0
    )


@pytest.mark.parametrize("arguments", [[], ["model", "read", "--invalid"], ["model", "apply"], ["facts", "export"]])
def test_argument_errors_are_json(arguments: list[str], capsys: pytest.CaptureFixture) -> None:
    with patch.object(sys, "argv", ["codeboarding-model", *arguments]):
        assert main() == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "USAGE_ERROR"


def test_io_error_and_output_failure_report_commit_uncertainty(
    store: ModelStore, capsys: pytest.CaptureFixture
) -> None:
    with patch.object(sys, "argv", ["codeboarding-model", "model", "--file", str(store.path), "read"]):
        with patch("architecture_model.cli.run", side_effect=OSError("read failure")):
            assert main() == 1
        assert json.loads(capsys.readouterr().out)["error"]["code"] == "IO_ERROR"
        with patch.object(sys.stdout, "write", side_effect=OSError("broken pipe")):
            assert main() == 2
        assert "commit may have completed" in capsys.readouterr().err


def test_module_entrypoint(capsys: pytest.CaptureFixture) -> None:
    with patch.object(sys, "argv", ["codeboarding-model", "model", "schema"]):
        with pytest.raises(SystemExit) as raised:
            runpy.run_module("architecture_model", run_name="__main__")
    assert raised.value.code == 0
    assert json.loads(capsys.readouterr().out)["ok"]


def test_missing_tool_does_not_publish(tmp_path: Path) -> None:
    output = tmp_path / "facts.json"
    with pytest.raises(ModelError) as raised:
        export_facts(tmp_path, "p", output, tmp_path / "node", tmp_path / "pyright", tmp_path / "tokei")
    assert raised.value.code == "TOOL_MISSING"
    assert not output.exists()


def test_output_failure_after_commit_does_not_rollback(
    store: ModelStore, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    patch_file = tmp_path / "patch.json"
    patch_file.write_text(
        json.dumps(
            {
                "author": "agent",
                "summary": "Commit",
                "operations": [
                    {"action": "update", "collection": "components", "id": "component", "value": {"name": "Committed"}}
                ],
            }
        )
    )
    with patch.object(
        sys,
        "argv",
        [
            "codeboarding-model",
            "model",
            "--file",
            str(store.path),
            "apply",
            "--expected-revision",
            "1",
            "--patch",
            str(patch_file),
        ],
    ):
        with patch.object(sys.stdout, "write", side_effect=OSError("broken pipe")):
            assert main() == 2
    assert store.read().revision == 2
    assert store.read().components[0].name == "Committed"
    assert "commit may have completed" in capsys.readouterr().err
