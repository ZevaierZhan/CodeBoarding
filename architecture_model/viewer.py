"""Export a validated architecture model as an offline, read-only document."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from architecture_model.errors import ModelError
from architecture_model.maintenance import query
from architecture_model.schema import Binding, HistoricalLocation, Location, Model
from architecture_model.validation import validate_model

ASSETS = Path(__file__).with_name("viewer_assets")
MAX_SOURCE_BYTES = 2_000_000


def projection(model: Model, source_root: Path | None = None) -> dict:
    """Freeze one complete validated revision and its maintenance view."""
    frozen = validate_model(model.model_dump())
    maintenance = query(frozen)
    value = frozen.model_dump()
    # Derived contexts belong to this frozen view, without saving the model.
    value["maintenance"] = maintenance["observations"]
    snippets = {}
    for binding in frozen.bindings:
        evidence: list[Binding | HistoricalLocation] = [binding, *binding.history]
        snippets[binding.id] = [
            {
                "snapshot_id": entry.snapshot_id,
                "source_version": entry.source_version,
                "location": entry.location.model_dump(),
                **_snippet(entry.location, source_root),
            }
            for entry in evidence
        ]
    return {
        "model": value,
        "maintenance": maintenance,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "snippets": snippets,
    }


def export_html(model: Model, output: Path, source_root: Path | None = None) -> dict:
    """Create a self-contained document, refusing to overwrite any existing file."""
    payload = projection(model, source_root)
    serialized = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    template = (ASSETS / "index.html").read_text(encoding="utf-8")
    document = template.replace("/*STYLE*/", (ASSETS / "style.css").read_text(encoding="utf-8"))
    scripts = "\n".join((ASSETS / name).read_text(encoding="utf-8") for name in ("engine.js", "viewer.js"))
    document = document.replace("/*SCRIPT*/", scripts)
    document = document.replace("/*MODEL*/", serialized)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(document.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        # Linking publishes complete bytes without replacing a competing export or model.
        os.link(temporary, output)
    except OSError as error:
        raise ModelError("EXPORT_FAILED", str(output), "Cannot publish document; choose a new output path") from error
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
    return {"output": str(output.resolve()), "model_id": model.id, "revision": model.revision, "committed": False}


def _snippet(location: Location, source_root: Path | None) -> dict:
    if source_root is None:
        return {"status": "unavailable", "reason": "No source root supplied; historical body is not stored."}
    root = source_root.resolve()
    path = (root / location.path).resolve()
    if not path.is_relative_to(root):
        return {"status": "unavailable", "reason": "Source path escapes the declared project root."}
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_SOURCE_BYTES + 1)
        if len(content) > MAX_SOURCE_BYTES:
            return {"status": "unavailable", "reason": "Source exceeds the 2 MB embedding limit."}
        if hashlib.sha256(content).hexdigest() != location.content_hash:
            return {"status": "mismatch", "reason": "Workspace bytes differ from this evidence version; body withheld."}
        lines = content.decode("utf-8").splitlines()
        if location.end > len(lines):
            return {"status": "unavailable", "reason": "Evidence line range exceeds the verified file."}
        return {
            "status": "verified",
            "text": "\n".join(f"{index + 1:>5}  {lines[index]}" for index in range(location.start - 1, location.end)),
        }
    except (OSError, UnicodeError) as error:
        return {
            "status": "unavailable",
            "reason": f"Source body unavailable ({type(error).__name__}); location retained.",
        }
