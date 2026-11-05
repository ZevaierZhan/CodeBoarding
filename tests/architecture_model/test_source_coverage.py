import json
import os
import shutil
import subprocess
import sys
import runpy
from pathlib import Path

import pytest

from architecture_model import file_inventory
from architecture_model.cli import run
from architecture_model.coverage import coverage_report
from architecture_model.errors import ModelError
from architecture_model.file_inventory import export_inventory
from architecture_model.maintenance import extraction_differences, preview, query, rebind, refresh, resolve
from architecture_model.schema import Facts
from architecture_model.store import ModelStore
from architecture_model.validation import digest, validate_facts


@pytest.fixture
def source(tmp_path: Path) -> Path:
    root = tmp_path / "sample-system"
    (root / "src").mkdir(parents=True)
    (root / "docs").mkdir()
    for name in ("rules", "gateway", "helpers"):
        (root / f"src/{name}.ts").write_text(f"export function {name}() {{ return 1; }}\n", encoding="utf-8")
    (root / "docs/policy.md").write_text("# Policy\n", encoding="utf-8")
    return root


def snapshot(source: Path, output: Path, root: str = "all-files") -> Facts:
    return export_inventory(source, "sample", output, root, [], [])


def native_fixture(source: Path, output: Path) -> Facts:
    value = export_inventory(source, "sample", output, "native", ["src/*.ts"], []).model_dump()
    descriptor = json.loads(value["tools"]["maintenance_scope"])
    descriptor["protocol"] = "multilanguage-file-v2"
    descriptor["configuration"] = {"test": "synthetic native catalog; not a real analyzer execution"}
    value["tools"]["maintenance_scope"] = json.dumps(descriptor)
    value["symbols"] = {
        f"{path}|{Path(path).stem}": location | {"symbol": Path(path).stem, "kind": "FUNCTION"}
        for path, location in value["file_locations"].items()
    }
    value["id"] = digest({key: entry for key, entry in value.items() if key != "id"})
    return Facts.model_validate(value)


def model_with_roots(tmp_path: Path, snapshots: list[Facts]) -> ModelStore:
    store = ModelStore(tmp_path / "model.json")
    store.initialize({"id": "sample", "name": "Sample", "boundary": "Synthetic evidence"}, "test")
    operations: list[dict] = []
    binding_ids = []
    for facts in snapshots:
        operations.append({"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()})
        identity = facts.source_root_id + "-binding"
        binding_ids.append(identity)
        location = facts.symbols["src/rules.ts|rules"] if facts.symbols else facts.file_locations["src/rules.ts"]
        binding = {
            "id": identity,
            "snapshot_id": facts.id,
            "source_version": facts.source.digest,
            "location": location.model_dump(),
            "status": "current",
        }
        operations.append({"action": "create", "collection": "bindings", "id": identity, "value": binding})
    claim = {"kind": "code_fact", "explanation": "Evidence from independent roots", "binding_ids": binding_ids}
    component = {
        "id": "component",
        "name": "Rules",
        "responsibility": "Sample rules",
        "rationale": "Fixture",
        "binding_ids": binding_ids,
        "claim": claim,
    }
    scenario = {
        "id": "scenario",
        "name": "Policy",
        "entry_step_id": "step",
        "order": ["step"],
        "transitions": [],
        "steps": [{"id": "step", "component_ids": ["component"], "binding_ids": binding_ids, "claim": claim}],
        "claim": claim,
    }
    for collection, item in (("components", component), ("scenarios", scenario)):
        operations.append({"action": "create", "collection": collection, "id": item["id"], "value": item})
    store.apply(0, {"author": "test", "summary": "Attach independent evidence", "operations": operations})
    return store


@pytest.mark.parametrize("status", ["missing", "changed"])
def test_unavailable_historical_binding_is_unattributed(source: Path, tmp_path: Path, status: str) -> None:
    store = model_with_roots(
        tmp_path, [snapshot(source, tmp_path / "inventory.json"), native_fixture(source, tmp_path / "native.json")]
    )
    historical = store.read().bindings[0].model_dump() | {
        "id": "historical",
        "snapshot_id": "unavailable-snapshot",
        "status": status,
        "reason": "Historical source snapshot is no longer available",
    }
    store.apply(
        store.read().revision,
        {
            "author": "test",
            "summary": "Retain historical evidence",
            "operations": [{"action": "create", "collection": "bindings", "id": "historical", "value": historical}],
        },
    )
    before = store.path.read_bytes()
    model = store.read()
    assert run(["model", "--file", str(store.path), "validate"])["valid"]
    output = tmp_path / "coverage.json"
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"all-files": str(source), "native": str(source)}))
    result = run(
        ["model", "--file", str(store.path), "coverage-report", "--source-map", str(mapping), "--output", str(output)]
    )
    report = json.loads(output.read_text())
    assert result["summary"]["confirmed_overlaps"] == 3
    assert report["unattributed_bindings"] == [
        {
            "binding_id": "historical",
            "snapshot_id": "unavailable-snapshot",
            "status": status,
            "attribution": "unknown",
            "reason": "snapshot_unavailable",
        }
    ]
    assert "historical" not in report["affected"]["binding_ids"]
    assert all("historical" not in entry["binding_ids"] for entry in report["files"])
    assert store.path.read_bytes() == before and store.read() == model
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "from architecture_model.cli import main; raise SystemExit(main())",
            "model",
            "--file",
            str(store.path),
            "coverage-report",
            "--source-map",
            str(mapping),
            "--output",
            str(tmp_path / "cli.json"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0 and json.loads(completed.stdout)["ok"] is True
    assert not completed.stderr and store.path.read_bytes() == before
    with pytest.raises(ModelError, match="snapshot"):
        store.apply(
            model.revision,
            {
                "author": "test",
                "summary": "Invalid current evidence",
                "operations": [
                    {"action": "update", "collection": "bindings", "id": "historical", "value": {"status": "current"}}
                ],
            },
        )
    assert store.path.read_bytes() == before


def test_coverage_separates_latest_current_and_historical_reviews(source: Path, tmp_path: Path) -> None:
    initial = snapshot(source, tmp_path / "initial.json")
    store = model_with_roots(tmp_path, [initial])
    observations = []
    for number in (2, 3):
        (source / "src/rules.ts").write_text(f"export function rules() {{ return {number}; }}\n")
        target = snapshot(source, tmp_path / f"target-{number}.json")
        proposed = preview(store.read(), target)
        observations.append(proposed["observations"][0])
        refresh(store, target, store.read().revision, proposed["token"], "test")
    latest = observations[-1]
    rebind(store, latest["id"], "src/rules.ts", store.read().revision, "test", "Inspected latest source")
    resolve(
        store,
        latest["id"],
        {
            "author": "test",
            "reason": "Confirmed shared component",
            "outcome": "confirmed",
            "source_version": target.source.digest,
        },
        store.read().revision,
    )
    saved = store.read()
    before = store.path.read_bytes()
    report = coverage_report(saved, {}, [], [], [])
    row = report["roots"][0]
    assert row["latest_recorded_maintenance_target"] == target.id
    assert row["current_pending_ids"] == []
    assert observations[0]["id"] in row["historical_pending_ids"]
    assert latest["id"] in row["current_coverage_ids"]
    assert latest["id"] in row["resolved_ids"]
    assert row["review_coverage_status"] == "established"
    assert set(row["pending_ids"]) == set(query(saved)["pending_ids"])
    assert store.path.read_bytes() == before
    explicit = coverage_report(saved, {}, [initial.id], [], [])["roots"][0]
    assert explicit["selected_snapshot_id"] == initial.id
    assert explicit["current_coverage_ids"] == row["current_coverage_ids"]
    store.apply(
        saved.revision,
        {
            "author": "test",
            "summary": "Revise interpretation",
            "operations": [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "component",
                    "value": {"responsibility": "New rules"},
                }
            ],
        },
    )
    before = store.path.read_bytes()
    modified = store.read()
    row = coverage_report(modified, {}, [], [], [])["roots"][0]
    assert row["current_pending_ids"]
    assert set(row["current_pending_ids"]) <= set(query(modified)["current_pending_ids"])
    assert latest["id"] in row["historical_resolved_ids"]
    assert observations[0]["id"] in row["historical_pending_ids"]
    assert modified.maintenance[: len(saved.maintenance)] == saved.maintenance
    assert modified.facts == saved.facts and modified.bindings == saved.bindings
    assert modified.verifications == saved.verifications
    assert store.path.read_bytes() == before
    assert coverage_report(modified, {}, [], [], [])["roots"][0] == row


def test_coverage_does_not_infer_review_from_target_or_selection(source: Path, tmp_path: Path) -> None:
    facts = snapshot(source, tmp_path / "facts.json")
    store = model_with_roots(tmp_path, [facts])
    model = store.read()
    before = model.model_dump()
    row = coverage_report(model, {}, [facts.id], [], [])["roots"][0]
    assert row["review_coverage_status"] == "unknown_target"
    assert row["unassessed_binding_ids"] == ["all-files-binding"]
    model.maintenance_targets["all-files"] = facts.id
    row = coverage_report(model, {}, [], [], [])["roots"][0]
    assert row["review_coverage_status"] == "unknown_coverage"
    assert row["current_pending_ids"] == []
    assert store.read().model_dump() == before


@pytest.mark.parametrize("field,value", [("reason", ""), ("status", "current")])
def test_invalid_historical_binding_still_rejected(source: Path, tmp_path: Path, field: str, value: str) -> None:
    store = model_with_roots(tmp_path, [snapshot(source, tmp_path / "facts.json")])
    binding = store.read().bindings[0].model_dump() | {
        "id": "invalid",
        "snapshot_id": "unavailable",
        "status": "missing",
        "reason": "Historical evidence",
        field: value,
    }
    before = store.path.read_bytes()
    with pytest.raises(ModelError):
        store.apply(
            store.read().revision,
            {
                "author": "test",
                "summary": "Invalid evidence",
                "operations": [{"action": "create", "collection": "bindings", "id": "invalid", "value": binding}],
            },
        )
    assert store.path.read_bytes() == before


def test_inventory_is_reproducible_file_only_and_provider_free(source: Path, tmp_path: Path) -> None:
    first = snapshot(source, tmp_path / "first.json")
    second = snapshot(source, tmp_path / "second.json")
    validate_facts(first)
    assert first == second and len(first.source.files) == 4
    assert first.source_root_id == "all-files" and not first.symbols and not first.calls
    assert set(first.file_locations) == set(first.source.files)
    assert extraction_differences(first, second) == []
    command = [
        "facts",
        "export",
        "--file-inventory",
        "--repo",
        str(source),
        "--project-id",
        "sample",
        "--source-root-id",
        "inventory",
        "--output",
        str(tmp_path / "subprocess.json"),
    ]
    script = """
import sys
from architecture_model.cli import run
run(sys.argv[1:])
assert not any(name in sys.modules for name in ('static_analyzer', 'agents.llm_config', 'kotlin'))
"""
    subprocess.run([sys.executable, "-c", script, *command], check=True, capture_output=True, timeout=30)


def test_inventory_rules_and_no_clobber(source: Path, tmp_path: Path) -> None:
    (source / "node_modules").mkdir()
    (source / "node_modules/ignored.ts").write_text("ignored")
    output = tmp_path / "facts.json"
    facts = export_inventory(source, "sample", output, "all", ["src/*.ts"], ["src/helpers.ts"])
    assert set(facts.source.files) == {"src/rules.ts", "src/gateway.ts"}
    original = output.read_bytes()
    with pytest.raises(ModelError, match="overwrites"):
        export_inventory(source, "sample", output, "all", [], [])
    assert output.read_bytes() == original
    with pytest.raises(ModelError, match="outside"):
        snapshot(source, source / "facts.json")


@pytest.mark.parametrize("change", ["edit", "delete", "add"])
def test_scan_changes_never_publish(source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    original = file_inventory._scan
    calls = 0

    def changing(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 1:
            path = source / "src/rules.ts"
            if change == "edit":
                path.write_text("changed")
            elif change == "delete":
                path.unlink()
            else:
                (source / "new.ts").write_text("new")
        return result

    monkeypatch.setattr(file_inventory, "_scan", changing)
    with pytest.raises(ModelError, match="changed"):
        snapshot(source, tmp_path / "unpublished.json")
    assert not (tmp_path / "unpublished.json").exists()


def test_inventory_limits_fail_closed(source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("architecture_model.file_inventory.MAX_FILES", 1)
    with pytest.raises(ModelError, match="selected files"):
        snapshot(source, tmp_path / "unpublished.json")
    assert not (tmp_path / "unpublished.json").exists()


@pytest.mark.parametrize(
    "content",
    [b"", b"a\rb\r", b"a\r\nb\n", b"a" * (1024 * 1024 - 1) + b"\r\nb"],
    ids=["empty", "carriage_return", "mixed_newlines", "chunk_boundary"],
)
def test_streaming_file_ranges_handle_line_endings(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "data"
    path.write_bytes(content)
    assert file_inventory.file_digest(path)[1] == max(1, len(content.splitlines()))


def test_overlap_refresh_is_independent_and_report_is_read_only(source: Path, tmp_path: Path) -> None:
    inventory = snapshot(source, tmp_path / "inventory.json")
    native = native_fixture(source, tmp_path / "native.json")
    assert inventory.id != native.id
    store = model_with_roots(tmp_path, [inventory, native])
    mapping = {"all-files": source, "native": source}
    before = store.path.read_bytes()
    report = coverage_report(store.read(), mapping, [], [], [])
    assert report["summary"]["same_version"] == 3
    assert {row["evidence"] for row in report["roots"]} == {"file_only", "static_symbols_calls_bounded"}
    assert report["affected"]["component_ids"] == ["component"]
    assert report["affected"]["scenario_ids"] == ["scenario"]
    assert store.path.read_bytes() == before
    (source / "src/rules.ts").write_text("export function rules() { return 2; }\n")
    target = native_fixture(source, tmp_path / "native-new.json")
    proposed = preview(store.read(), target)
    refresh(store, target, store.read().revision, proposed["token"], "test")
    recorded = store.read().model_dump()
    report = coverage_report(store.read(), mapping, [], [], [])
    assert report["summary"]["different_versions"] == 1
    assert report["roots"][0]["reexport"] == "needed_workspace_differs"
    assert store.read().maintenance_targets == {"native": target.id}
    assert store.read().facts[0] == inventory
    new_inventory = snapshot(source, tmp_path / "inventory-new.json")
    report = coverage_report(store.read(), mapping, [], [new_inventory], [])
    assert report["summary"]["different_versions"] == 0
    assert all(row["architecture_review"] == "not_established_by_coverage" for row in report["roots"])
    assert store.read().model_dump() == recorded
    assert query(store.read())["pending_ids"]


def test_inventory_maintenance_and_descriptor_upgrade(source: Path, tmp_path: Path) -> None:
    old = snapshot(source, tmp_path / "old.json")
    store = model_with_roots(tmp_path, [old])
    (source / "src/rules.ts").write_text("changed\n")
    target = snapshot(source, tmp_path / "target.json")
    report = preview(store.read(), target)
    assert report["observations"][0]["disposition"] == "changed"
    refresh(store, target, store.read().revision, report["token"], "test")
    upgraded = target.model_copy(deep=True)
    descriptor = json.loads(upgraded.tools["maintenance_scope"])
    descriptor["implementation"] = "new-real-extractor-version"
    upgraded.tools["maintenance_scope"] = json.dumps(descriptor)
    upgraded.id = digest(upgraded.model_dump(exclude={"id"}))
    report = preview(store.read(), upgraded)
    observation = report["observations"][0]
    assert observation["disposition"] == "indeterminate"
    assert "implementation" in " ".join(observation["reasons"])
    assert "baseline explicitly" in " ".join(observation["reasons"])
    refresh(store, upgraded, store.read().revision, report["token"], "test")
    rebind(store, observation["id"], "src/rules.ts", store.read().revision, "test", "Inspected new baseline")
    current = store.read()
    assert preview(current, upgraded)["observations"][0]["disposition"] == "unchanged"
    assert current.bindings[0].history[0].snapshot_id == old.id
    assert old == current.facts[0] and query(current)["pending_ids"]


def test_missing_scope_does_not_infer_deletion(source: Path, tmp_path: Path) -> None:
    old = snapshot(source, tmp_path / "old.json")
    old.tools.pop("maintenance_scope")
    old.id = digest(old.model_dump(exclude={"id"}))
    store = model_with_roots(tmp_path, [old])
    (source / "src/rules.ts").unlink()
    target = snapshot(source, tmp_path / "target.json")
    assert preview(store.read(), target)["observations"][0]["disposition"] == "indeterminate"
    assert coverage_report(store.read(), {}, [], [], [])["roots"][0]["extraction"]["status"] == "missing"


def test_identical_bytes_and_names_in_separate_directories_do_not_overlap(source: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    shutil.copytree(source, other)
    first = snapshot(source, tmp_path / "first.json")
    second = snapshot(other, tmp_path / "second.json", "other")
    store = model_with_roots(tmp_path, [first, second])
    report = coverage_report(store.read(), {"all-files": source, "other": other}, [], [], [])
    assert report["summary"]["confirmed_overlaps"] == 0
    assert coverage_report(store.read(), {}, [], [], [])["summary"]["unknown_physical_identity"] == 8
    (other / "src/rules.ts").write_text("different")
    assert coverage_report(store.read(), {"all-files": source, "other": other}, [], [], [])["overlaps"] == []


@pytest.mark.parametrize("path", ["../outside", "C:/outside", "//server/share/file", "dir\\file", "/tmp/file"])
def test_report_rejects_manifest_escape(source: Path, tmp_path: Path, path: str) -> None:
    old = snapshot(source, tmp_path / "old.json")
    store = model_with_roots(tmp_path, [old])
    model = store.read()
    model.facts[0].source.files[path] = "a" * 64
    with pytest.raises(ModelError, match="POSIX"):
        coverage_report(model, {"all-files": source}, [], [], [])


def test_links_outside_root_rejected(source: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.ts"
    outside.write_text("secret")
    link = source / "src/link.ts"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Host does not permit creating symlinks")
    with pytest.raises(ModelError, match="links"):
        snapshot(source, tmp_path / "unpublished.json")
    link.unlink()
    old = snapshot(source, tmp_path / "old.json")
    store = model_with_roots(tmp_path, [old])
    (source / "src/rules.ts").unlink()
    (source / "src/rules.ts").symlink_to(outside)
    with pytest.raises(ModelError, match="links"):
        coverage_report(store.read(), {"all-files": source}, [], [], [])


def test_hardlinks_confirm_physical_identity(source: Path, tmp_path: Path) -> None:
    other = tmp_path / "hardlinks"
    shutil.copytree(source, other)
    (other / "src/rules.ts").unlink()
    os.link(source / "src/rules.ts", other / "src/rules.ts")
    store = model_with_roots(
        tmp_path, [snapshot(source, tmp_path / "a.json"), snapshot(other, tmp_path / "b.json", "b")]
    )
    assert (
        coverage_report(store.read(), {"all-files": source, "b": other}, [], [], [])["summary"]["confirmed_overlaps"]
        == 1
    )


def test_cli_outputs_bounded_summary_and_never_replaces_model(source: Path, tmp_path: Path) -> None:
    store = model_with_roots(tmp_path, [snapshot(source, tmp_path / "facts.json")])
    mapping = tmp_path / "mapping.json"
    mapping.write_text(json.dumps({"all-files": str(source)}))
    before = store.path.read_bytes()
    arguments = ["model", "--file", str(store.path), "coverage-report", "--source-map", str(mapping)]
    result = run([*arguments, "--output", str(tmp_path / "report.json")])
    assert len(json.dumps(result)) < 2048 and "files" not in result
    with pytest.raises(ModelError, match="new coverage output"):
        run([*arguments, "--output", str(store.path)])
    assert store.path.read_bytes() == before


def test_ambiguous_snapshot_selection_is_unknown(source: Path, tmp_path: Path) -> None:
    old = snapshot(source, tmp_path / "old.json")
    store = model_with_roots(tmp_path, [old])
    (source / "docs/policy.md").write_text("new")
    target = snapshot(source, tmp_path / "target.json")
    model = store.read()
    model.facts.append(target)
    report = coverage_report(model, {}, [], [], [])
    assert report["roots"][0]["selection"] == "unknown" and not report["files"]
    assert coverage_report(model, {}, [target.id], [], [])["roots"][0]["selection"] == "explicit"
    with pytest.raises(ModelError, match="one snapshot"):
        coverage_report(model, {}, [old.id, target.id], [], [])


@pytest.mark.parametrize("field", ["protocol", "complete", "configuration", "tools", "patterns"])
def test_descriptor_changes_never_establish_false_deletion(source: Path, tmp_path: Path, field: str) -> None:
    old = snapshot(source, tmp_path / "old.json")
    target = snapshot(source, tmp_path / "target.json")
    descriptor = json.loads(target.tools["maintenance_scope"])
    replacements = {
        "protocol": "future-v7",
        "complete": False,
        "configuration": {"different": "rules"},
        "tools": ["changed-tool"],
        "patterns": ["src/*"],
    }
    descriptor[field] = replacements[field]
    target.tools["maintenance_scope"] = json.dumps(descriptor)
    target.id = digest(target.model_dump(exclude={"id"}))
    store = model_with_roots(tmp_path, [old])
    differences = extraction_differences(old, target)
    assert differences
    report = coverage_report(store.read(), {}, [], [target], [])
    assert report["roots"][0]["descriptor_differences"]
    if field in ("complete", "protocol"):
        assert report["roots"][0]["extraction"]["status"] == "unsupported"
        with pytest.raises(ModelError, match="descriptor"):
            preview(store.read(), target)
    else:
        assert preview(store.read(), target)["observations"][0]["disposition"] == "indeterminate"


def test_missing_mapped_file_is_unknown_not_deleted(source: Path, tmp_path: Path) -> None:
    store = model_with_roots(tmp_path, [snapshot(source, tmp_path / "old.json")])
    (source / "src/rules.ts").unlink()
    report = coverage_report(store.read(), {"all-files": source}, [], [], [])
    missing = next(row for row in report["files"] if row["path"] == "src/rules.ts")
    assert missing["physical_identity"] == "unavailable_file" and missing["workspace_content"] == "unknown"
    assert report["roots"][0]["reexport"] == "unknown"


def test_inventory_permission_error_and_size_limit_never_publish(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(file_inventory, "MAX_FILE_BYTES", 1)
    with pytest.raises(ModelError, match="limit"):
        snapshot(source, tmp_path / "limited.json")
    monkeypatch.setattr(file_inventory, "MAX_FILE_BYTES", 256 * 1024 * 1024)
    monkeypatch.setattr(file_inventory, "file_digest", lambda path: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(PermissionError, match="denied"):
        snapshot(source, tmp_path / "denied.json")
    assert not (tmp_path / "limited.json").exists() and not (tmp_path / "denied.json").exists()


@pytest.mark.parametrize("collection", ["files", "unattributed_bindings"])
def test_coverage_helper_pages_large_results(source: Path, tmp_path: Path, collection: str) -> None:
    store = model_with_roots(tmp_path, [snapshot(source, tmp_path / "facts.json")])
    report = coverage_report(store.read(), {}, [], [], [])
    report[collection] = report["files"] * 1000
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    script = Path("skills/codeboarding-modeling/scripts/model_context.py").resolve()
    helper = runpy.run_path(str(script))
    first = helper["page"]({"inventory": report[collection]}, "", "rules.ts", 0, 100)
    assert first["total"] == 1000 and first["next_offset"] < 100
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "coverage",
            "--report",
            str(path),
            "--collection",
            collection,
            "--search",
            "rules.ts",
            "--limit",
            "100",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0 and len(result.stdout) <= 4096
    assert json.loads(result.stdout)["result"]["total"] == 1000


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction boundary")
def test_windows_junction_escape_rejected(source: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = source / "external"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, check=True, timeout=10
    )
    try:
        with pytest.raises(ModelError, match="junctions"):
            snapshot(source, tmp_path / "unpublished.json")
    finally:
        junction.rmdir()
