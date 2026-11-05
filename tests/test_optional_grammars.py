"""Optional grammar detection must never invoke the downloading loader when absent."""

from unittest.mock import Mock

import pytest
import tree_sitter_language_pack as language_pack
from tree_sitter_language_pack.api import _rust

from static_analyzer.engine.source_inspector import SourceInspector


def test_absent_kotlin_never_enters_native_loader(monkeypatch):
    native = Mock(side_effect=AssertionError("Downloading loader must not be entered"))
    monkeypatch.setattr(language_pack, "downloaded_languages", lambda: [])
    monkeypatch.setattr(_rust, "get_language", native)
    with pytest.raises(pytest.skip.Exception, match="Kotlin grammar is not installed"):
        language_pack.get_language("kotlin")
    native.assert_not_called()


def test_cached_kotlin_runs_the_loader_and_propagates_errors(monkeypatch):
    native = Mock(side_effect=RuntimeError("Broken locally installed grammar"))
    monkeypatch.setattr(language_pack, "downloaded_languages", lambda: ["kotlin"])
    monkeypatch.setattr(_rust, "get_language", native)
    with pytest.raises(RuntimeError, match="Broken locally installed grammar"):
        language_pack.get_language("kotlin")
    native.assert_called_once_with(name="kotlin")


@pytest.mark.parametrize(
    "suffix,source",
    [(".py", "f()\n"), (".java", "class A { void f() { g(); } }"), (".rs", "fn main() { f(); }"), (".ts", "f();")],
)
def test_other_languages_parse_without_kotlin(monkeypatch, tmp_path, suffix, source):
    monkeypatch.setattr(language_pack, "downloaded_languages", lambda: [])
    native = Mock(side_effect=AssertionError("No optional grammar should be loaded"))
    monkeypatch.setattr(_rust, "get_language", native)
    file = tmp_path / ("main" + suffix)
    file.write_text(source)
    assert SourceInspector().find_call_sites(file)
    native.assert_not_called()
