import json
import os
import runpy
import subprocess
import sys
from io import BufferedWriter
from pathlib import Path

import pytest

from architecture_model.store import ModelStore

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills/codeboarding-modeling/scripts/model_context.py"
API = runpy.run_path(str(SCRIPT))


def execute(directory: Path, *arguments: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--engine", str(ROOT), *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert len(result.stdout.strip()) <= 4096
    return result


def test_large_capture_queries_and_inventory_do_not_write_a_second_model(store: ModelStore, tmp_path: Path) -> None:
    current = store.read()
    component = current.components[0].model_dump()
    operations = [
        {
            "action": "create",
            "collection": "components",
            "id": f"extra-{number}",
            "value": component | {"id": f"extra-{number}"},
        }
        for number in range(120)
    ]
    operations.append(
        {"action": "update", "collection": "scenarios", "id": "scenario", "value": {"name": "Large context " * 4000}}
    )
    store.apply(
        current.revision,
        {"author": "test", "summary": "Extend context for transport exercise", "operations": operations},
    )
    original = store.path.read_bytes()
    caller = tmp_path / "Independent target with spaces"
    caller.mkdir()
    cache = tmp_path / "Session cache with spaces"
    capture = execute(caller, "capture", "--model", str(store.path), "--cache", str(cache))
    assert capture.returncode == 0, capture.stderr
    assert (cache / "read.json").stat().st_size > 50_000
    assert json.loads(capture.stdout)["result"]["artifact_type"] == "temporary-complete-read-index"
    found: list[str] = []
    offset = 0
    while True:
        response = execute(
            caller,
            "list",
            "--cache",
            str(cache),
            "--collection",
            "components",
            "--offset",
            str(offset),
            "--limit",
            "100",
        )
        page = json.loads(response.stdout)["result"]
        found.extend(row["id"] for row in page["items"])
        offset = page["next_offset"]
        if offset == page["total"]:
            break
    assert len(found) == len(set(found)) == 121
    binding = execute(caller, "get", "--cache", str(cache), "--id", "binding", "--pointer", "/location/path")
    assert json.loads(binding.stdout)["result"] == "app.py"
    large = execute(caller, "get", "--cache", str(cache), "--id", "scenario")
    assert large.returncode == 1 and "exceeds 4096" in large.stdout
    output = tmp_path / "Full object.json"
    saved = execute(caller, "get", "--cache", str(cache), "--id", "scenario", "--output", str(output))
    assert saved.returncode == 0 and json.loads(output.read_text())["id"] == "scenario"
    exact = execute(caller, "get", "--cache", str(cache), "--id", "scenario", "--pointer", "/steps/0/component_ids")
    assert json.loads(exact.stdout)["result"] == ["component"]
    invalid = subprocess.run(
        [sys.executable, "-m", "architecture_model", "model", "--file", str(cache / "read.json"), "validate"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert invalid.returncode == 1 and "SCHEMA_INVALID" in invalid.stdout
    assert store.path.read_bytes() == original
    repeated = execute(caller, "capture", "--model", str(store.path), "--cache", str(cache))
    assert repeated.returncode == 1


def test_stale_capture_and_expected_revision_fail_without_overwriting(store: ModelStore, tmp_path: Path) -> None:
    cache = tmp_path / "captured context"
    assert execute(tmp_path, "capture", "--model", str(store.path), "--cache", str(cache)).returncode == 0
    patch = {
        "author": "writer",
        "summary": "Concurrent change",
        "operations": [
            {"action": "update", "collection": "components", "id": "component", "value": {"name": "New explanation"}}
        ],
    }
    old_revision = store.read().revision
    store.apply(old_revision, patch)
    original = store.path.read_bytes()
    freshness = execute(tmp_path, "check", "--cache", str(cache))
    assert freshness.returncode == 1 and "STALE_CONTEXT" in freshness.stdout
    path = tmp_path / "old candidate.json"
    path.write_text(json.dumps(patch))
    result = execute(
        tmp_path,
        "cli",
        "--response",
        str(tmp_path / "conflict.json"),
        "--",
        "model",
        "--file",
        str(store.path),
        "apply",
        "--patch",
        str(path),
        "--expected-revision",
        str(old_revision),
    )
    assert result.returncode == 1 and "REVISION_CONFLICT" in result.stdout
    assert store.path.read_bytes() == original


def test_modified_or_scoped_capture_is_not_complete_context(
    store: ModelStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "full"
    assert execute(tmp_path, "capture", "--model", str(store.path), "--cache", str(cache)).returncode == 0
    original = store.path.read_bytes()
    (cache / "read.json").write_bytes((cache / "read.json").read_bytes()[:80])
    failed = execute(tmp_path, "summary", "--cache", str(cache))
    assert failed.returncode == 1 and "truncated" in failed.stdout
    capture = API["capture"]
    monkeypatch.setitem(capture.__globals__, "invoke", lambda *_: {"ok": True, "result": {"complete": False}})
    scoped = tmp_path / "scoped"
    with pytest.raises(ValueError, match="complete:true"):
        capture(str(ROOT), store.path, scoped)
    assert not (scoped / "index.json").exists()
    assert store.path.read_bytes() == original


def test_response_and_query_outputs_cannot_replace_model_or_context(store: ModelStore, tmp_path: Path) -> None:
    before = store.path.read_bytes()
    response = execute(tmp_path, "cli", "--response", str(store.path), "--", "model", "--file", str(store.path), "read")
    assert response.returncode == 1
    assert store.path.read_bytes() == before
    cache = tmp_path / "cache"
    assert execute(tmp_path, "capture", "--model", str(store.path), "--cache", str(cache)).returncode == 0
    for destination in (store.path, cache / "read.json", cache / "index.json"):
        result = execute(tmp_path, "get", "--cache", str(cache), "--id", "component", "--output", str(destination))
        assert result.returncode == 1
    assert store.path.read_bytes() == before


def test_engine_priority_and_paths_with_spaces(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    command = API["engine_command"]
    namespace = command.__globals__
    home = tmp_path / "Engine with spaces"
    (home / "architecture_model").mkdir(parents=True)
    (home / "architecture_model/cli.py").touch()
    (home / "pyproject.toml").touch()
    monkeypatch.setenv("CODEBOARDING_HOME", str(home))
    monkeypatch.setattr(
        namespace["shutil"], "which", lambda name: "installed-cli" if name == "codeboarding-model" else "uv"
    )
    explicit, directory = command(str(home))
    assert str(home) in explicit and directory == home
    assert command("")[0] == ["installed-cli"]
    with pytest.raises(ValueError, match="unavailable"):
        command(str(tmp_path / "Missing explicit engine"))
    monkeypatch.setattr(namespace["shutil"], "which", lambda name: "uv" if name == "uv" else None)
    assert command("")[1] == home
    monkeypatch.delenv("CODEBOARDING_HOME")
    with pytest.raises(ValueError, match="Supply --engine"):
        command("")
    monkeypatch.chdir(tmp_path)
    assert API["absolute_arguments"](
        ["model", "--file=model with spaces.json", "export-html", "--output", "new file.html"]
    )[1] == "--file=" + str(tmp_path / "model with spaces.json")
    for arguments in (["model", "read"], ["model", "read", "--scenario", "schema"]):
        with pytest.raises(ValueError, match="explicit --file"):
            API["absolute_arguments"](arguments)


def test_installed_cli_works_outside_engine(store: ModelStore, tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "capture",
            "--model",
            str(store.path),
            "--cache",
            str(tmp_path / "installed context"),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"]["model_id"] == store.read().id


def test_cli_paths_are_resolved_from_target_before_engine_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invoke = API["invoke"]
    namespace = invoke.__globals__
    target = tmp_path / "Target with spaces"
    target.mkdir()
    monkeypatch.chdir(target)
    monkeypatch.setitem(namespace, "engine_command", lambda _: (["engine CLI"], ROOT))
    calls = []

    def run(arguments: list[str], *, cwd: Path, stdout: BufferedWriter, timeout: int) -> subprocess.CompletedProcess:
        calls.append((arguments, cwd))
        stdout.write(b'{"ok":true,"result":{"valid":true}}')
        return subprocess.CompletedProcess(arguments, 0)

    monkeypatch.setattr(namespace["subprocess"], "run", run)
    invoke(
        "locator", ["model", "--file", "model.json", "validate", "--patch", "patch file.json"], target / "response.json"
    )
    assert calls == [
        (
            [
                "engine CLI",
                "model",
                "--file",
                str(target / "model.json"),
                "validate",
                "--patch",
                str(target / "patch file.json"),
            ],
            ROOT,
        )
    ]


@pytest.mark.parametrize(
    "exit_code,body", [(0, b'{"ok":true'), (1, b'{"ok":false,"error":{"code":"IO_ERROR"}}'), (2, b"")]
)
def test_incomplete_or_failed_cli_output_is_never_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, body: bytes
) -> None:
    invoke = API["invoke"]
    namespace = invoke.__globals__
    monkeypatch.setitem(namespace, "engine_command", lambda _: (["engine"], tmp_path))

    def run(arguments: list[str], *, cwd: Path, stdout: BufferedWriter, timeout: int) -> subprocess.CompletedProcess:
        stdout.write(body)
        return subprocess.CompletedProcess(arguments, exit_code)

    monkeypatch.setattr(namespace["subprocess"], "run", run)
    with pytest.raises(RuntimeError):
        invoke("engine", ["model", "schema"], tmp_path / "response.json")
