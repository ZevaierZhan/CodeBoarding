from pathlib import Path, PureWindowsPath
from unittest.mock import patch

import pytest

from infra.repo_utils.path_utils import normalize_repo_path, to_absolute_path, to_relative_path
from static_analyzer.engine.lsp_client import LSPClient
from static_analyzer.engine.utils import uri_to_path


@pytest.mark.parametrize(
    "root,file,expected",
    [
        ("/repo", "/repo/src/a b.py", "src/a b.py"),
        ("/repo", "/elsewhere/a.py", "/elsewhere/a.py"),
        ("C:/repo", "C:/repo/src/a b.py", "src/a b.py"),
        ("C:/repo", "c:/REPO/src/a.py", "src/a.py"),
        ("C:/repo", "D:/repo/a.py", "D:/repo/a.py"),
        ("/repo", "src/a.py", "src/a.py"),
    ],
)
def test_portable_file_identity(root, file, expected):
    assert to_relative_path(file, Path(root)) == expected
    assert normalize_repo_path(file, root) == expected


def test_native_relative_roundtrip(tmp_path):
    file = tmp_path / "source root" / "a #%.py"
    assert Path(to_absolute_path(to_relative_path(file, tmp_path), tmp_path)) == file
    assert uri_to_path(file.as_uri()) == file


def test_foreign_windows_absolute_is_not_prefixed():
    assert PureWindowsPath(to_absolute_path("D:/src/a.py", Path("/repo"))) == PureWindowsPath("D:/src/a.py")


def test_relative_root_is_resolved_against_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    file = tmp_path / "repo" / "src" / "main.py"
    assert normalize_repo_path(file, Path("repo")) == "src/main.py"
    assert to_relative_path(file, Path("repo")) == "src/main.py"


def test_a_sibling_with_the_same_prefix_is_outside_the_root():
    assert to_relative_path("/repository/a.py", Path("/repo")) == "/repository/a.py"


def test_posix_absolute_names_keep_literal_backslashes():
    assert normalize_repo_path("/repo/a\\b.py", "/repo") == "a\\b.py"


def test_initialize_resolves_relative_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = LSPClient(["fake"], Path("project"), workspace_folders=[Path("sources with spaces")])
    captured = {}
    with (
        patch("subprocess.Popen"),
        patch("os.dup"),
        patch("threading.Thread"),
        patch.object(client, "_send_notification"),
        patch.object(client, "_send_request", side_effect=lambda method, params, **kw: captured.update(params) or {}),
    ):
        client.start()
    assert captured["rootUri"] == (tmp_path / "project").as_uri()
    assert captured["workspaceFolders"][0]["uri"] == (tmp_path / "sources with spaces").as_uri()


@pytest.mark.parametrize("uri", ["file:relative.py", "file:///tmp/a.py?query", "file:///tmp/a.py#fragment"])
def test_invalid_file_uri_is_not_a_local_identity(uri):
    assert uri_to_path(uri) is None


def test_unc_authority_is_preserved_on_windows():
    with patch("static_analyzer.engine.utils._IS_WINDOWS", True):
        assert uri_to_path("file://server/share/a%20b.py") == Path("//server/share/a b.py")
