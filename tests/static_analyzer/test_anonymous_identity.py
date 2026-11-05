from copy import deepcopy

import pytest

from static_analyzer.config import NodeType
from static_analyzer.engine.adapters.typescript_adapter import JavaScriptAdapter, TypeScriptAdapter
from static_analyzer.engine.symbol_table import SymbolTable


def declaration(name, line, column=0, children=()):
    return {
        "name": name,
        "kind": NodeType.FUNCTION,
        "range": {"start": {"line": line, "character": column}, "end": {"line": line, "character": column + 8}},
        "children": list(children),
    }


@pytest.mark.parametrize("adapter", [TypeScriptAdapter, JavaScriptAdapter])
@pytest.mark.parametrize("positions", [[(10, 4), (11, 4)], [(10, 4), (10, 24)]])
def test_repeated_callbacks_and_their_children_keep_distinct_identities(monkeypatch, tmp_path, adapter, positions):
    monkeypatch.setenv("CODEBOARDING_STRICT_SYMBOL_IDENTITY", "true")
    table = SymbolTable(adapter())
    file = tmp_path / "app.ts"
    callbacks = [
        declaration("run.then() callback", line, col, [declaration("nested", line, col + 1)]) for line, col in positions
    ]
    for callback in callbacks:
        callback["range"]["end"]["character"] += 10
    outer = declaration("run", 0, children=callbacks)
    outer["range"]["end"]["line"] = 20
    table.register_symbols(file, [outer], [], tmp_path)
    table.build_indices()
    primary = table.primary_file_symbols[str(file)]
    assert len(primary) == 5
    assert len({item.qualified_name for item in primary}) == 5
    scopes = [item for item in primary if item.name == "run.then() callback"]
    assert len(scopes) == 2
    for scope in scopes:
        contained = table.find_containing_symbol(file, scope.start_line, scope.start_char)
        assert contained is not None and contained.definition_location == scope.definition_location
        assert table.attribution_symbol(scope).qualified_name == "app.run"
        assert all(
            table.symbols[name].definition_location == scope.definition_location
            for name in table.get_equivalent_names(scope.qualified_name)
        )
    children = [item for item in primary if item.name == "nested"]
    assert {item.owner_qualified_name for item in children} == {item.qualified_name for item in scopes}
    for child in children:
        assert all(
            table.symbols[name].definition_location == child.definition_location
            for name in table.get_equivalent_names(child.qualified_name)
        )


def test_anonymous_identity_is_independent_of_registration_order_and_file_root(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEBOARDING_STRICT_SYMBOL_IDENTITY", "true")
    callbacks = [declaration("map() callback", 2), declaration("map() callback", 8)]
    identities = []
    for directory, entries in ((tmp_path / "one", callbacks), (tmp_path / "two", list(reversed(callbacks)))):
        table = SymbolTable(TypeScriptAdapter())
        file = directory / "app.ts"
        table.register_symbols(file, deepcopy(entries), [], directory)
        identities.append({item.start_line: item.qualified_name for item in table.primary_file_symbols[str(file)]})
    assert identities[0] == identities[1]


def test_named_collisions_are_still_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEBOARDING_STRICT_SYMBOL_IDENTITY", "true")
    table = SymbolTable(TypeScriptAdapter())
    with pytest.raises(ValueError, match="qualified-name collision"):
        table.register_symbols(tmp_path / "app.ts", [declaration("named", 1), declaration("named", 5)], [], tmp_path)
