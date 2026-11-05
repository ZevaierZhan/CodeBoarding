import os
from pathlib import Path

import pytest
import tree_sitter_language_pack as language_pack


# The unit suite must not report to the product's PostHog project. Its runs are
# not usage, and — because ``track_analysis`` captures in a ``finally`` before
# the caller sees the exception — every test that asserts a raise ships a
# ``$exception``. Three of the four most frequent exceptions on the project were
# a single such test each, which is how a deliberate assertion comes to outrank
# the errors real users hit.
#
# ``setdefault``, not assignment: exporting ``DO_NOT_TRACK=0`` still turns the
# reporting back on for a run that means to exercise it. ``CODEBOARDING_SOURCE``
# stays set so anything that does report from here is still labelled internal.
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ["CODEBOARDING_SOURCE"] = "tests"


@pytest.fixture(autouse=True)
def label_test_telemetry(monkeypatch):
    monkeypatch.setenv("CODEBOARDING_SOURCE", "tests")
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)


@pytest.fixture(autouse=True)
def local_kotlin_grammar_only(monkeypatch, request):
    """Skip only tests that actually request an absent optional grammar, without downloading it."""
    load = language_pack.get_language

    def local_language(name):
        if name == "kotlin":
            request.node.add_marker("requires_kotlin_grammar")
            if name not in language_pack.downloaded_languages():
                pytest.skip(
                    "Kotlin grammar is not installed in the configured local cache; test downloads are disabled"
                )
        return load(name)

    monkeypatch.setattr(language_pack, "get_language", local_language)
