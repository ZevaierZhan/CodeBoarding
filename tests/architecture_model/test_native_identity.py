from pathlib import Path

import pytest

from static_analyzer.config import NodeType
from static_analyzer.engine.adapters.java_adapter import JavaAdapter
from static_analyzer.engine.symbol_table import SymbolTable


def test_strict_export_accepts_repeated_packages_but_rejects_duplicate_types(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODEBOARDING_STRICT_SYMBOL_IDENTITY", "true")
    table = SymbolTable(JavaAdapter())
    declaration = {
        "name": "example",
        "kind": NodeType.PACKAGE,
        "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 16}},
    }
    for name in ("Controller.java", "Service.java"):
        table.register_symbols(tmp_path / name, [declaration], [], tmp_path)
    declaration = declaration | {"name": "Duplicate", "kind": NodeType.CLASS}
    table.register_symbols(tmp_path / "Controller.java", [declaration], [], tmp_path)
    with pytest.raises(ValueError, match="qualified-name collision"):
        table.register_symbols(tmp_path / "Service.java", [declaration], [], tmp_path)
