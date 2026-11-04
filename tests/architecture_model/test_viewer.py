import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from architecture_model.errors import ModelError
from architecture_model.store import ModelStore
from architecture_model.validation import digest
from architecture_model.viewer import MAX_SOURCE_BYTES, export_html, projection
from examples.architecture_model.demo import cli


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
