import json
import hashlib
import os
import runpy
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from architecture_model import maintenance_plan
from architecture_model import cli, file_inventory
from architecture_model.cli import run
from architecture_model.coverage import coverage_report
from architecture_model.errors import ModelError
from architecture_model.file_inventory import file_digest
from architecture_model.maintenance_plan import check_plan, generate_plan
from architecture_model.observation import ObservationContext, PathObservation
from architecture_model.store import atomic_write
from tests.architecture_model.test_maintenance_plan import dual
from tests.architecture_model.test_source_coverage import source


@pytest.mark.parametrize("change", ["size", "same_size", "restored_mtime", "restored_bytes", "add", "delete", "rename"])
def test_exact_cli_observes_bytes_and_membership(dual, source, tmp_path, change):
    store, mapping = dual
    plan_path = tmp_path / "plan.json"
    prefix = ["model", "--file", str(store.path)]
    run([*prefix, "maintenance-plan", "--source-map", str(mapping), "--output", str(plan_path)])
    model_bytes = store.path.read_bytes()
    path = source / "src/rules.ts"
    saved, info = path.read_bytes(), path.stat()
    if change == "size":
        path.write_bytes(b"changed size")
    elif change in ("same_size", "restored_mtime", "restored_bytes"):
        path.write_bytes(saved.replace(b"1", b"2"))
        if change == "restored_bytes":
            path.write_bytes(saved)
        if change != "same_size":
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    elif change == "add":
        (source / "untracked.ts").write_bytes(b"new")
    elif change == "delete":
        path.unlink()
    else:
        path.rename(path.with_name("renamed.ts"))
    checked = run([*prefix, "maintenance-plan-check", "--plan", str(plan_path)])
    assert checked["requires_replan"] == (change != "restored_bytes")
    assert checked["status"] == ("ready" if change == "restored_bytes" else "stale")
    if change in ("size", "same_size", "restored_mtime", "delete", "rename"):
        assert any(item["code"] == "file_observations_changed" for item in checked["reasons"])
    assert store.path.read_bytes() == model_bytes


def test_independent_processes_and_identical_copy_keep_physical_identity(dual, source, tmp_path):
    store, mapping = dual
    before = store.path.read_bytes()
    plan = generate_plan(store.read(), mapping, [], [])
    assert plan == generate_plan(store.read(), mapping, [], [])
    plan_path = tmp_path / "plan.json"
    atomic_write(plan_path, plan)
    command = [
        sys.executable,
        "-m",
        "architecture_model",
        "model",
        "--file",
        str(store.path),
        "maintenance-plan-check",
        "--plan",
        str(plan_path),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: subprocess.run(command, capture_output=True, text=True, check=True), range(2))
        )
    assert all(json.loads(result.stdout)["result"]["status"] == "ready" for result in results)
    other = tmp_path / "copy"
    shutil.copytree(source, other)
    atomic_write(mapping, {"all-files": str(other), "native": str(source)})
    assert check_plan(store.read(), plan)["status"] == "stale"
    copied = generate_plan(store.read(), mapping, [], [])
    assert copied["summary"]["confirmed_overlaps"] == 0
    assert all(row["workspace_content"] == "same" for row in copied["files"])
    assert store.path.read_bytes() == before


def test_change_after_coverage_with_restored_metadata_never_publishes(dual, source, monkeypatch):
    store, mapping = dual
    path = source / "src/rules.ts"
    info = path.stat()
    original = maintenance_plan.coverage_report

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_bytes(path.read_bytes().replace(b"1", b"2"))
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        return result

    monkeypatch.setattr(maintenance_plan, "coverage_report", changing)
    with pytest.raises(ModelError, match="changed"):
        generate_plan(store.read(), mapping, [], [])


def test_hash_read_replacement_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "file.ts"
    path.write_bytes(b"old")
    replacement = tmp_path / "replacement.ts"
    replacement.write_bytes(b"new")
    original = Path.open

    def replacing(self, *args, **kwargs):
        if self == path:
            os.replace(replacement, path)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", replacing)
    with pytest.raises(ModelError, match="changed"):
        file_digest(path)


@pytest.mark.parametrize("action", ["maintenance-plan", "maintenance-plan-check"])
def test_cli_rejects_concurrent_model_write(dual, tmp_path, monkeypatch, action):
    store, mapping = dual
    plan = tmp_path / "plan.json"
    atomic_write(plan, generate_plan(store.read(), mapping, [], []))
    original = cli.generate_plan if action == "maintenance-plan" else cli.check_plan

    def changing(*args, **kwargs):
        report = original(*args, **kwargs)
        store.apply(
            store.read().revision,
            {
                "author": "other",
                "summary": "Concurrent interpretation",
                "operations": [
                    {
                        "action": "update",
                        "collection": "components",
                        "id": "component",
                        "value": {"responsibility": "New interpretation"},
                    }
                ],
            },
        )
        return report

    monkeypatch.setattr(cli, "generate_plan" if action == "maintenance-plan" else "check_plan", changing)
    output = tmp_path / "new-plan.json"
    arguments = (
        ["--source-map", str(mapping), "--output", str(output)]
        if action == "maintenance-plan"
        else ["--plan", str(plan)]
    )
    with pytest.raises(ModelError, match="Model changed"):
        run(["model", "--file", str(store.path), action, *arguments])
    assert not output.exists()


def test_missing_manifest_directory_retains_unavailable_file_records(dual, source):
    store, mapping = dual
    shutil.rmtree(source / "src")
    plan = generate_plan(store.read(), mapping, [], [])
    assert plan["status"] == "blocked"
    missing = [row for row in plan["files"] if row["path"].startswith("src/")]
    assert len(missing) == 6
    assert all(row["physical_identity"] == "unavailable_file" for row in missing)


def test_shared_ancestor_replacement_is_rejected(dual, source, monkeypatch):
    store, mapping = dual
    original = PathObservation.finish

    def replacing(context):
        parent = source / "src"
        parent.rename(source / "previous")
        shutil.copytree(source / "previous", parent)
        original(context)

    monkeypatch.setattr(PathObservation, "finish", replacing)
    with pytest.raises(ModelError, match="changed"):
        coverage_report(store.read(), {"all-files": source, "native": source}, [], [], [])


@pytest.mark.parametrize("alias", [False, True])
def test_closing_verification_includes_manifest_files_outside_scan_names(tmp_path, alias):
    directory = tmp_path / ".codeboarding"
    directory.mkdir()
    path = directory / "file.ts"
    path.write_bytes(b"old")
    observed = Path(str(path) + ".") if alias and os.name == "nt" else path
    expected = {os.path.normcase(str(observed)): file_digest(path)[0]}
    context = ObservationContext(expected)
    context.workspace(tmp_path)
    path.write_bytes(b"new")
    with pytest.raises(ModelError, match="changed"):
        context.finish()


@pytest.mark.parametrize("size", [0, 1, 31, 4096, 1024 * 1024 - 1, 1024 * 1024 + 1])
def test_bounded_reads_preserve_binary_hash_and_line_count(tmp_path, size):
    content = (b"\x00\xff\r\n" * (size // 4 + 1))[:size]
    path = tmp_path / "binary"
    path.write_bytes(content)
    hashed, lines, fingerprint = file_digest(path)
    assert hashed == hashlib.sha256(content).hexdigest()
    assert lines == max(1, len(content.splitlines()))
    assert fingerprint == (path.stat().st_dev, path.stat().st_ino, size, path.stat().st_mtime_ns)


def test_cli_detects_actual_engine_source_change_in_separate_checkout(dual, tmp_path):
    store, mapping = dual
    original_model = store.path.read_bytes()
    engine = tmp_path / "engine"
    repository = Path(maintenance_plan.__file__).resolve().parent.parent
    for package in ("architecture_model", "static_analyzer", "infra"):
        shutil.copytree(
            repository / package,
            engine / package,
            ignore=shutil.ignore_patterns("servers", "node_modules", "__pycache__"),
        )
    environment = {**os.environ, "PYTHONPATH": str(engine)}
    prefix = [sys.executable, "-m", "architecture_model", "model", "--file", str(store.path)]
    plan = tmp_path / "engine-plan.json"
    subprocess.run(
        [*prefix, "maintenance-plan", "--source-map", str(mapping), "--output", str(plan)],
        cwd=engine,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    changed = engine / "architecture_model/maintenance_plan_states.py"
    changed.write_bytes(changed.read_bytes() + b"\n# Disposable engine upgrade.\n")
    checked = subprocess.run(
        [*prefix, "maintenance-plan-check", "--plan", str(plan)],
        cwd=engine,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(checked.stdout)["result"]
    assert result["status"] == "stale" and {"code": "engine_digest_changed"} in result["reasons"]
    assert store.path.read_bytes() == original_model


def test_model_integrity_hash_does_not_apply_source_file_size_policy(tmp_path, monkeypatch):
    path = tmp_path / "model.json"
    content = b'{"model": "larger than the source test limit"}'
    path.write_bytes(content)
    monkeypatch.setattr(file_inventory, "MAX_FILE_BYTES", 1)
    with pytest.raises(ModelError, match="256 MiB"):
        file_digest(path)
    assert file_digest(path, enforce_source_limit=False)[0] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("change", ["dirty", "untracked"])
def test_git_head_does_not_substitute_for_workspace_bytes(dual, source, tmp_path, change):
    store, mapping = dual
    for arguments in (
        ["init"],
        ["add", "."],
        ["-c", "user.name=M6C", "-c", "user.email=m6c@example.invalid", "commit", "-m", "Synthetic baseline"],
    ):
        subprocess.run(["git", "-C", str(source), *arguments], check=True, capture_output=True, text=True)
    command = ["git", "-C", str(source), "rev-parse", "HEAD"]
    head = subprocess.run(command, check=True, capture_output=True, text=True).stdout
    model_bytes = store.path.read_bytes()
    plan = tmp_path / "git-plan.json"
    prefix = ["model", "--file", str(store.path)]
    run([*prefix, "maintenance-plan", "--source-map", str(mapping), "--output", str(plan)])
    path = source / ("src/rules.ts" if change == "dirty" else "untracked.ts")
    path.write_bytes(b"changed workspace bytes\n")
    assert subprocess.run(command, check=True, capture_output=True, text=True).stdout == head
    status = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"], check=True, capture_output=True, text=True
    ).stdout
    assert path.name in status
    checked = run([*prefix, "maintenance-plan-check", "--plan", str(plan)])
    assert checked["status"] == "stale" and checked["requires_replan"]
    assert store.path.read_bytes() == model_bytes


@pytest.mark.parametrize(
    "destination", ["source", "plan.json", "measurements.json", "samples-in-progress.json", "worker-failure.json"]
)
def test_benchmark_rejects_input_overwrites_before_creating_outputs(dual, source, tmp_path, destination):
    store, mapping = dual
    model_bytes = store.path.read_bytes()
    model = store.path
    directory = source / "benchmark-output" if destination == "source" else tmp_path
    if destination != "source":
        model = directory / destination
        model.write_bytes(model_bytes)
    script = Path("examples/architecture_model/observation_performance/benchmark.py").resolve()
    result = subprocess.run(
        [sys.executable, str(script), "--directory", str(directory), "--model", str(model), "--mapping", str(mapping)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert model.read_bytes() == model_bytes and store.path.read_bytes() == model_bytes
    if destination == "source":
        assert not directory.exists()


@pytest.mark.parametrize("name", ["unsupported:name", "unsupported\\name"])
def test_workspace_retains_portable_entry_name_rejection(tmp_path, monkeypatch, name):
    if os.name == "nt":
        monkeypatch.setattr(os, "scandir", lambda path: nullcontext([SimpleNamespace(name=name)]))
    else:
        (tmp_path / name).write_bytes(b"unmanifested bytes")
    with pytest.raises(ModelError, match="repository-relative POSIX path"):
        ObservationContext({}).workspace(tmp_path)


def test_benchmark_preserves_failed_worker_trace(tmp_path):
    helper = runpy.run_path("examples/architecture_model/observation_performance/benchmark.py")["_run_worker"]
    with pytest.raises(RuntimeError, match="worker-failure.json") as failure:
        helper([sys.executable, "-c", "raise RuntimeError('intentional worker failure')"], tmp_path)
    assert isinstance(failure.value.__cause__, subprocess.CalledProcessError)
    saved = json.loads((tmp_path / "worker-failure.json").read_text())
    assert saved["exit_code"] != 0 and "intentional worker failure" in saved["stderr"]
