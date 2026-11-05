import os
import pickle
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from infra.repo_utils.path_utils import (
    _portable_path,
    restore_cached_path,
    serialize_cached_path,
    to_absolute_path,
    to_relative_path,
)
from static_analyzer.analysis_cache import StaticAnalysisCache
from static_analyzer.analysis_result import StaticAnalysisResults
from static_analyzer.cfg import CallGraph
from static_analyzer.config import Language, NodeType
from static_analyzer.node import Node
from static_analyzer.engine.utils import uri_to_path


@pytest.mark.skipif(os.name == "nt", reason="A literal backslash filename requires a POSIX filesystem")
@pytest.mark.parametrize(
    "literal_name,nested_name", [("a\\b.py", "a/b.py"), ("a\\b #%.py", "a/b #%.py"), ("C:\\b.py", "C:/b.py")]
)
def test_real_posix_backslash_and_nested_file_keep_distinct_cache_identities(tmp_path, literal_name, nested_name):
    literal = tmp_path / literal_name
    nested = tmp_path / nested_name
    nested.parent.mkdir()
    literal.write_text("literal", encoding="utf-8")
    nested.write_text("nested", encoding="utf-8")
    assert not literal.samefile(nested)
    assert "%5C" in literal.as_uri()
    assert uri_to_path(literal.as_uri()) == literal
    assert to_relative_path(literal, tmp_path) == literal_name
    assert Path(to_absolute_path(PurePosixPath(to_relative_path(literal, tmp_path)), tmp_path)).samefile(literal)
    results = StaticAnalysisResults()
    files = [str(literal), str(nested)]
    results.add_source_files(Language.PYTHON, files)
    graph = CallGraph(language="python")
    for name, path in zip(("literal", "nested"), files):
        graph.add_node(Node(name, NodeType.FUNCTION, path, 1, 1))
    results.add_cfg(Language.PYTHON, graph)
    results.diagnostics = {Language.PYTHON: {path: [] for path in files}}
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.save(results, source_sha="source")
    payload = pickle.loads(cache.pkl_path.read_bytes())
    assert payload["analysis"].get_source_files(Language.PYTHON) == [
        "relative:" + literal_name,
        "relative:" + nested_name,
    ]
    loaded = cache.get(expected_sha="source")
    assert loaded is not None
    restored = loaded.get_source_files(Language.PYTHON)
    assert restored == files
    assert len(set(restored)) == 2
    assert [Path(path).read_text(encoding="utf-8") for path in restored] == ["literal", "nested"]
    assert {node.file_path for node in loaded.get_cfg(Language.PYTHON).nodes.values()} == set(files)
    assert set(loaded.diagnostics[Language.PYTHON]) == set(files)


def test_pure_relative_path_dialects_are_explicit():
    literal = _portable_path(PurePosixPath("a\\b.py"))
    nested = _portable_path(PureWindowsPath("a\\b.py"))
    assert literal == PurePosixPath("a\\b.py")
    assert nested.as_posix() == "a/b.py"
    assert literal.parts != nested.parts


@pytest.mark.parametrize(
    "path", ["../escape.py", "a/../../escape.py", PureWindowsPath("..\\escape.py"), PureWindowsPath("C:escape.py")]
)
def test_relative_restore_rejects_root_escape(tmp_path, path):
    with pytest.raises(ValueError):
        to_absolute_path(path, tmp_path)
    with pytest.raises(ValueError):
        to_relative_path(path, tmp_path)


@pytest.mark.skipif(os.name == "nt", reason="Real symlink containment runs on the POSIX filesystem")
def test_relative_restore_rejects_symlink_escape(tmp_path):
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "a.py").touch()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside repository root"):
        to_absolute_path("link/a.py", root)


@pytest.mark.parametrize("legacy_path", ["a\\b.py", "C:\\b.py", "C:/b.py", "//server/share/b.py"])
def test_cache_rejects_ambiguous_untagged_legacy_relative_backslash(tmp_path, legacy_path):
    results = StaticAnalysisResults()
    results.add_source_files(Language.PYTHON, [legacy_path])
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.artifact_dir.mkdir()
    cache.pkl_path.write_bytes(pickle.dumps(results))
    assert cache.get() is None


def test_cache_reads_unambiguous_untagged_legacy_slash_path(tmp_path):
    results = StaticAnalysisResults()
    results.add_source_files(Language.PYTHON, ["a/b.py"])
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.artifact_dir.mkdir()
    cache.pkl_path.write_bytes(pickle.dumps(results))
    loaded = cache.get()
    assert loaded is not None
    assert loaded.get_source_files(Language.PYTHON) == [str(tmp_path / "a/b.py")]


def test_cache_restore_stays_in_its_source_root(tmp_path):
    roots = [tmp_path / "frontend", tmp_path / "backend"]
    results = StaticAnalysisResults()
    for root in roots:
        root.mkdir()
        (root / "same #%.py").write_text(root.name, encoding="utf-8")
    paths = []
    for root in roots:
        results = StaticAnalysisResults()
        results.add_source_files(Language.PYTHON, [str(root / "same #%.py")])
        cache = StaticAnalysisCache(root / ".codeboarding", root)
        cache.save(results, source_sha=root.name)
        loaded = cache.get(expected_sha=root.name)
        assert loaded is not None
        paths.extend(loaded.get_source_files(Language.PYTHON))
    assert len(set(paths)) == 2
    assert [Path(path).read_text(encoding="utf-8") for path in paths] == ["frontend", "backend"]


def test_native_windows_relative_input_is_explicit_on_other_hosts(tmp_path):
    assert Path(to_absolute_path(PureWindowsPath("src\\a #%.py"), tmp_path)) == tmp_path / "src/a #%.py"


@pytest.mark.parametrize(
    "root,file",
    [
        (PureWindowsPath("C:/repo"), PureWindowsPath("C:/repo/a #%.py")),
        (PureWindowsPath("//server/share/repo"), PureWindowsPath("//server/share/repo/a #%.py")),
    ],
)
def test_windows_absolute_dialects_preserve_identity(root, file):
    assert _portable_path(file).relative_to(_portable_path(root)).as_posix() == "a #%.py"
    assert _portable_path(file).as_uri() == file.as_uri()


def test_uri_encoding_remains_separate_from_cache_path_serialization(tmp_path):
    file = tmp_path / "a #%.py"
    file.touch()
    uri = file.as_uri()
    assert "%20" in uri and "%23" in uri and "%25" in uri
    assert uri_to_path(uri) == file


def test_old_engine_tag_requires_reanalysis_even_without_sha_gate(tmp_path):
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.save(StaticAnalysisResults(), source_sha="source")
    cache.sha_path.write_text("v14\nsource\n", encoding="utf-8")
    assert cache.from_another_engine()
    assert cache.get() is None
    assert cache.get(expected_sha="source") is None
    assert cache.load_with_sha() is None


def test_versioned_cache_rejects_unknown_path_format(tmp_path):
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.save(StaticAnalysisResults(), source_sha="source")
    payload = pickle.loads(cache.pkl_path.read_bytes())
    assert payload["path_format"] == "repo-paths-v1"
    payload["path_format"] = "unknown"
    cache.pkl_path.write_bytes(pickle.dumps(payload))
    assert cache.get(expected_sha="source") is None


@pytest.mark.parametrize("relative", ["../escape.py", "a/../../escape.py"])
def test_versioned_cache_rejects_relative_root_escape(tmp_path, relative):
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.save(StaticAnalysisResults(), source_sha="source")
    payload = pickle.loads(cache.pkl_path.read_bytes())
    payload["analysis"].add_source_files(Language.PYTHON, ["relative:" + relative])
    cache.pkl_path.write_bytes(pickle.dumps(payload))
    assert cache.get(expected_sha="source") is None


@pytest.mark.skipif(os.name != "nt", reason="Only Windows cannot represent a literal POSIX backslash filename")
def test_windows_rejects_posix_cache_instead_of_aliasing_a_nested_file(tmp_path):
    nested = tmp_path / "a/b.py"
    nested.parent.mkdir()
    nested.write_text("nested", encoding="utf-8")
    cache = StaticAnalysisCache(tmp_path / ".codeboarding", tmp_path)
    cache.save(StaticAnalysisResults(), source_sha="source")
    payload = pickle.loads(cache.pkl_path.read_bytes())
    payload["analysis"].add_source_files(Language.PYTHON, ["relative:a\\b.py"])
    cache.pkl_path.write_bytes(pickle.dumps(payload))
    assert cache.get(expected_sha="source") is None


def test_native_absolute_cache_path_keeps_its_external_identity(tmp_path):
    root = tmp_path / "repo"
    external = tmp_path / "outside #%.py"
    encoded = serialize_cached_path(str(external), root)
    assert encoded.startswith("windows:" if os.name == "nt" else "posix:")
    assert Path(restore_cached_path(encoded, root)) == external


def test_foreign_absolute_cache_path_is_not_reinterpreted_locally(tmp_path):
    foreign = "posix:/repo/outside.py" if os.name == "nt" else "windows:C:/repo/outside.py"
    with pytest.raises(ValueError, match="foreign absolute cache path"):
        restore_cached_path(foreign, tmp_path)


@pytest.mark.parametrize(
    "path", [PureWindowsPath("D:/external #%.py"), PureWindowsPath("//server/share/external #%.py")]
)
def test_windows_cross_drive_and_unc_cache_paths_keep_their_absolute_dialect(tmp_path, path):
    encoded = "windows:" + str(path)
    if os.name == "nt":
        assert PureWindowsPath(restore_cached_path(encoded, tmp_path)) == path
    else:
        with pytest.raises(ValueError, match="foreign absolute cache path"):
            restore_cached_path(encoded, tmp_path)


@pytest.mark.parametrize("value", ["relative:/outside.py", "unknown:src/a.py", "src/a.py"])
def test_invalid_cache_path_labels_are_rejected(tmp_path, value):
    with pytest.raises(ValueError):
        restore_cached_path(value, tmp_path)
