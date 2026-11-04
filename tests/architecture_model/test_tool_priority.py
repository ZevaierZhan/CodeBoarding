import json
import os
import platform
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts
from architecture_model.store import ModelStore
from infra.tool_registry import manifest
from infra.tool_registry.paths import exe_suffix, platform_bin_dir
from infra.utils import get_config
from infra.vscode_constants import VSCODE_CONFIG


@pytest.fixture
def installed_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    servers = tmp_path / "installed"
    binary = platform_bin_dir(servers) / f"tokei{exe_suffix()}"
    binary.parent.mkdir(parents=True)
    binary.write_text("installed tokei")
    binary.chmod(0o755)
    wrapper = (
        servers
        / "node_modules/.bin"
        / ("pyright-langserver.cmd" if platform.system() == "Windows" else "pyright-langserver")
    )
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("installed wrapper")
    entry = servers / "node_modules/pyright/langserver.index.js"
    entry.parent.mkdir(parents=True)
    entry.write_text("installed entry")
    monkeypatch.setattr(manifest, "get_servers_dir", lambda: servers)
    monkeypatch.setattr(manifest, "preferred_node_path", lambda base: str(servers / "node"))
    monkeypatch.setattr(manifest.shutil, "which", lambda name: str(tmp_path / "path" / name))
    return servers


@pytest.mark.parametrize("resolver", ["installed", "path", "build", "get"])
def test_explicit_complete_commands_survive_discovery(installed_tools: Path, tmp_path: Path, resolver: str) -> None:
    python = [str(tmp_path / "requested-node"), str(tmp_path / "requested-pyright.js"), "--stdio"]
    tokei = [str(tmp_path / "requested-tokei"), "-o", "json"]
    with (
        patch.dict(VSCODE_CONFIG["lsp_servers"]["python"], command=python),
        patch.dict(VSCODE_CONFIG["tools"]["tokei"], command=tokei),
    ):
        if resolver == "installed":
            config = manifest.resolve_config(installed_tools)
        elif resolver == "path":
            config = manifest.resolve_config_from_path()
        elif resolver == "build":
            config = manifest.build_config()
        else:
            config = {"lsp_servers": get_config("lsp_servers"), "tools": get_config("tools")}
        assert config["lsp_servers"]["python"]["command"] == python
        assert config["tools"]["tokei"]["command"] == tokei


def test_default_commands_still_discover_installed_tools(installed_tools: Path) -> None:
    config = manifest.build_config()
    assert config["lsp_servers"]["python"]["command"] == [
        str(installed_tools / "node"),
        str(installed_tools / "node_modules/pyright/langserver.index.js"),
        "--stdio",
    ]
    assert config["tools"]["tokei"]["command"] == [
        str(platform_bin_dir(installed_tools) / f"tokei{exe_suffix()}"),
        "-o",
        "json",
    ]


@pytest.mark.parametrize("failure", ["", "tokei", "pyright"])
def test_real_export_uses_explicit_tools_over_isolated_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    required = [os.environ.get(f"M1_{name}", "") for name in ("NODE", "PYRIGHT", "TOKEI")]
    if not all(required):
        pytest.skip("Set M1_NODE, M1_PYRIGHT and M1_TOKEI to run real explicit-tool probes")
    real_node, real_pyright, real_tokei = map(Path, required)
    home = tmp_path / "home"
    servers = home / ".codeboarding/servers"
    installed_tokei = platform_bin_dir(servers) / f"tokei{exe_suffix()}"
    installed_tokei.parent.mkdir(parents=True)
    shutil.copy2(real_tokei, installed_tokei)
    installed_entry = servers / "node_modules/pyright/langserver.index.js"
    installed_entry.parent.mkdir(parents=True)
    installed_marker = tmp_path / "installed-pyright-used"
    installed_entry.write_text(
        f"require('fs').writeFileSync({json.dumps(str(installed_marker))}, 'wrong tool'); process.exit(42);"
    )
    wrapper = (
        servers / "node_modules/.bin" / ("pyright-langserver.cmd" if sys.platform == "win32" else "pyright-langserver")
    )
    wrapper.parent.mkdir(parents=True)
    wrapper.touch()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("CODEBOARDING_NODE_PATH", str(real_node))
    requested_node = tmp_path / f"requested-node{exe_suffix()}"
    shutil.copy2(real_node, requested_node)
    requested_pyright = tmp_path / "requested-pyright.js"
    pyright_marker = tmp_path / "requested-pyright-used.json"
    requested_pyright.write_text(
        f"require('fs').writeFileSync({json.dumps(str(pyright_marker))}, JSON.stringify({{node:process.execPath,argv:process.argv.slice(2)}}));\n"
        + ("process.exit(42);\n" if failure == "pyright" else f"require({json.dumps(str(real_pyright))});\n")
    )
    tokei_marker = tmp_path / "requested-tokei-used"
    requested_tokei = tmp_path / ("requested-tokei.cmd" if sys.platform == "win32" else "requested-tokei")
    if sys.platform == "win32":
        requested_tokei.write_text(
            f'@echo off\n> "{tokei_marker}" echo %*\n'
            + ("exit /b 42\n" if failure == "tokei" else f'"{real_tokei}" %*\nexit /b %errorlevel%\n')
        )
    else:
        requested_tokei.write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$*" > "{tokei_marker}"\n'
            + ("exit 42\n" if failure == "tokei" else f'exec "{real_tokei}" "$@"\n')
        )
        requested_tokei.chmod(0o755)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.py").write_text("def helper():\n    return 1\n\ndef run():\n    return helper()\n")
    store = ModelStore(tmp_path / "architecture-model.json")
    store.initialize({"id": "project", "name": "Fixture", "boundary": "Local fixture"}, "test")
    before = store.path.read_bytes()
    output = tmp_path / "facts.json"
    if failure:
        with pytest.raises(ModelError) as raised:
            export_facts(source, "project", output, requested_node, requested_pyright, requested_tokei)
        assert raised.value.code == "FACTS_FAILED"
        assert not output.exists()
    else:
        facts = export_facts(source, "project", output, requested_node, requested_pyright, requested_tokei)
        assert len(facts.symbols) == 2 and len(facts.calls) == 1
        assert facts.tools["node"] == str(requested_node.resolve())
        assert facts.tools["pyright_js"] == str(requested_pyright.resolve())
        assert facts.tools["tokei"] == str(requested_tokei.resolve())
        assert json.loads(facts.tools["python_command"]) == [
            str(requested_node.resolve()),
            str(requested_pyright.resolve()),
            "--stdio",
        ]
        assert json.loads(facts.tools["tokei_command"]) == [str(requested_tokei.resolve()), "-o", "json"]
    assert tokei_marker.read_text().strip() == "-o json"
    if failure != "tokei":
        recorded = json.loads(pyright_marker.read_text())
        assert Path(recorded["node"]).resolve() == requested_node.resolve()
        assert recorded["argv"] == ["--stdio"]
    assert not installed_marker.exists()
    assert store.path.read_bytes() == before
