import os
from pathlib import Path

import pytest

from architecture_model.facts import export_multilanguage


def test_real_callbacks_keep_both_call_paths(tmp_path):
    tools = os.environ.get("M5_TOOLS", "")
    if not tools:
        pytest.skip("Set M5_TOOLS for the real native TypeScript engine")
    source = Path("examples/architecture_model/callback_identity/source").resolve()
    facts = export_multilanguage(source, "callbacks", tmp_path / "facts.json", "frontend", Path(tools))
    locations = list(facts.symbols.values())
    callbacks = [item for item in locations if ") callback" in item.symbol.rsplit(".", 1)[-1]]
    assert len(callbacks) == 6
    assert len({item.symbol for item in callbacks}) == 6
    nested = [item for item in locations if item.symbol.endswith(".step")]
    assert len(nested) == 2
    assert len({item.symbol for item in nested}) == 2
    calls = {(facts.symbols[call.source].symbol, facts.symbols[call.target].symbol) for call in facts.calls}
    for name in ("settle", "siblings"):
        for target in ("success", "failure"):
            assert (f"app.{name}", f"app.{target}") in calls
    for child in nested:
        assert any(source == child.symbol and target in ("app.success", "app.failure") for source, target in calls)
