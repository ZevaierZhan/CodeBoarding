import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts
from architecture_model.schema import Location
from architecture_model.store import ModelStore
from architecture_model.validation import digest
from architecture_model.viewer import MAX_SOURCE_BYTES, _snippet, export_html, projection
from examples.architecture_model.demo import cli


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_file_evidence_can_include_terminal_empty_line(tmp_path: Path, newline: str) -> None:
    content = ("value = 1" + newline).encode()
    (tmp_path / "app.py").write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    location = Location(path="app.py", kind="FILE", content_hash=checksum, start=1, end=2)
    snippet = _snippet(location, tmp_path)
    assert snippet["status"] == "verified" and snippet["text"] == "    1  value = 1\n    2  "
    assert _snippet(location.model_copy(update={"end": 3}), tmp_path)["status"] == "unavailable"
    assert _snippet(location.model_copy(update={"kind": "FUNCTION"}), tmp_path)["status"] == "unavailable"
    (tmp_path / "app.py").write_bytes(b"value = 1")
    without_newline = location.model_copy(update={"content_hash": hashlib.sha256(b"value = 1").hexdigest()})
    assert _snippet(without_newline, tmp_path)["status"] == "unavailable"


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("separator", ["\u2028", "\u2029", "\u0085"])
@pytest.mark.parametrize("final_newline", [False, True])
def test_snippets_follow_source_document_lines(
    tmp_path: Path, newline: str, separator: str, final_newline: bool
) -> None:
    lines = [f'label = "A{separator}B"', "", "def target():", "    return 42"]
    content = (newline.join(lines) + (newline if final_newline else "")).encode("utf-8")
    (tmp_path / "app.py").write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    for start, end, kind in [(3, 4, "FUNCTION"), (1, 4, "FILE")]:
        location = Location(path="app.py", symbol="", kind=kind, content_hash=checksum, start=start, end=end)
        snippet = _snippet(location, tmp_path)
        assert snippet["status"] == "verified"
        assert snippet["text"] == "\n".join(f"{index + 1:>5}  {lines[index]}" for index in range(start - 1, end))
    assert (tmp_path / "app.py").read_bytes() == content


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_native_unicode_facts_bindings_and_projection_agree(tmp_path: Path, newline: str) -> None:
    names = ("M1_NODE", "M1_PYRIGHT", "M1_TOKEI")
    if not all(os.environ.get(name) for name in names):
        pytest.skip("Set M1_NODE, M1_PYRIGHT and M1_TOKEI to run the real native engine")
    source = tmp_path / "source"
    source.mkdir()
    content = newline.join(
        [
            'label = "A\u2028B\u2029C</script><script>window.injected=true</script>"',
            "",
            "def target():",
            "    return 42",
            "",
        ]
    ).encode("utf-8")
    (source / "app.py").write_bytes(content)
    facts = export_facts(source, "positions", tmp_path / "facts.json", *(Path(os.environ[name]) for name in names))
    function = facts.symbols["app.py|app.target"]
    file = facts.file_locations["app.py"]
    assert (function.start, function.end, file.start, file.end) == (3, 4, 1, 4)
    assert function.content_hash == file.content_hash == hashlib.sha256(content).hexdigest()
    store = ModelStore(tmp_path / "model.json")
    store.initialize({"id": "positions", "name": "Positions", "boundary": "Real Unicode source"}, "test")
    store.apply(
        0,
        {
            "author": "test",
            "summary": "Bind real exported positions",
            "operations": [
                {"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()},
                *[
                    {
                        "action": "create",
                        "collection": "bindings",
                        "id": identity,
                        "value": {
                            "snapshot_id": facts.id,
                            "source_version": facts.source.digest,
                            "location": location.model_dump(),
                            "status": "current",
                        },
                    }
                    for identity, location in [("function", function), ("file", file)]
                ],
                {
                    "action": "create",
                    "collection": "components",
                    "id": "source-position",
                    "value": {
                        "name": "Physical source lines",
                        "responsibility": "Inspect target and its file",
                        "rationale": "Real exported evidence for source-position regression",
                        "binding_ids": ["function", "file"],
                        "claim": {
                            "kind": "code_fact",
                            "explanation": "target returns the literal 42",
                            "binding_ids": ["function"],
                        },
                    },
                },
            ],
        },
    )
    before = store.path.read_bytes()
    snippets = projection(store.read(), source)["snippets"]
    assert snippets["function"][0]["text"] == "    3  def target():\n    4      return 42"
    assert snippets["file"][0]["text"].endswith("    3  def target():\n    4      return 42")
    assert "\u2028" in snippets["file"][0]["text"] and "\u2029" in snippets["file"][0]["text"]
    export_html(store.read(), tmp_path / "unicode.html", source)
    assert store.path.read_bytes() == before


def test_frozen_projection_and_offline_cli_are_read_only(store: ModelStore, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "app.py").write_bytes(b"def run(): return 1\n")
    before = store.path.read_bytes()
    frozen = store.read()
    original = frozen.model_dump()
    payload = projection(frozen, root)
    assert payload["model"]["revision"] == payload["maintenance"]["revision"] == frozen.revision
    assert payload["snippets"]["binding"][0]["status"] == "verified"
    assert "def run()" in payload["snippets"]["binding"][0]["text"]
    assert frozen.model_dump() == original
    output = tmp_path / "view.html"
    result = cli("model", "--file", str(store.path), "export-html", "--output", str(output), "--source-root", str(root))
    assert result["committed"] is False
    assert store.path.read_bytes() == before
    with pytest.raises(ModelError) as failure:
        export_html(frozen, store.path)
    assert failure.value.code == "EXPORT_FAILED"
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("mode", ["none", "missing", "changed", "large", "unicode", "range", "outside"])
def test_source_is_never_misrepresented(store: ModelStore, tmp_path: Path, mode: str) -> None:
    root = tmp_path / "source"
    root.mkdir()
    content = b"def run(): return 1\n"
    model = store.read()
    if mode == "changed":
        content = b"def run(): return 2\n"
    if mode == "large":
        content = b"x" * (MAX_SOURCE_BYTES + 1)
    if mode == "unicode":
        content = b"\xff\xfe"
    if mode != "missing":
        (root / "app.py").write_bytes(content)
    if mode in ("unicode", "range"):
        # Keep the catalog and binding consistent while exercising the source boundary.
        checksum = hashlib.sha256(content).hexdigest()
        model.bindings[0].location.content_hash = checksum
        model.facts[0].symbols["app.py|app.run"].content_hash = checksum
        model.facts[0].source.files["app.py"] = checksum
        if mode == "range":
            model.bindings[0].location.end = 200
            model.facts[0].symbols["app.py|app.run"].end = 200
        from_value = model.facts[0].model_dump(exclude={"id"})
        from_value["source"]["digest"] = digest(from_value["source"]["files"])
        checksum_id = digest(from_value)
        model.facts[0].source.digest = from_value["source"]["digest"]
        model.facts[0].id = checksum_id
        model.bindings[0].snapshot_id = checksum_id
        model.bindings[0].source_version = model.facts[0].source.digest
    if mode == "outside":
        with patch("architecture_model.viewer.Path.resolve", side_effect=[root, tmp_path / "outside.py"]):
            snippet = projection(model, root)["snippets"]["binding"][0]
    else:
        snippet = projection(model, None if mode == "none" else root)["snippets"]["binding"][0]
    assert snippet["status"] == ("mismatch" if mode == "changed" else "unavailable")
    assert "text" not in snippet
    assert snippet["location"]["path"] == "app.py"


def test_failed_publication_leaves_no_partial_artifact(store: ModelStore, tmp_path: Path) -> None:
    output = tmp_path / "view.html"
    before = set(tmp_path.iterdir())
    with patch("architecture_model.viewer.os.link", side_effect=OSError("disk failure")):
        with pytest.raises(ModelError) as failure:
            export_html(store.read(), output)
    assert failure.value.code == "EXPORT_FAILED"
    assert not output.exists()
    assert set(tmp_path.iterdir()) == before


def test_untrusted_model_text_cannot_close_data_script(store: ModelStore, tmp_path: Path) -> None:
    model = store.read()
    hostile = '</script><script>window.injected=true</script><a href="javascript:alert(1)">payload</a>'
    model.components[0].name = hostile
    output = tmp_path / "untrusted.html"
    export_html(model, output)
    html = output.read_text(encoding="utf-8")
    data = html.split('<script type="application/json" id="model-data">', 1)[1].split("</script>", 1)[0]
    assert "<" not in data
    assert json.loads(data)["model"]["components"][0]["name"] == hostile


def test_export_does_not_import_provider_or_telemetry() -> None:
    probe = """
import sys
import architecture_model.cli
assert not any(name.split('.')[0] in {'agents', 'posthog', 'langchain', 'config'} for name in sys.modules)
"""
    subprocess.run([sys.executable, "-c", probe], check=True, capture_output=True, timeout=20)
