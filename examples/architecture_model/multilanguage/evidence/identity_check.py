"""Validate real identical-path exports in one model candidate without writing it."""

import hashlib
import json
import sys
from pathlib import Path

from architecture_model.schema import Binding, Facts
from architecture_model.store import ModelStore, load_json
from architecture_model.validation import parse, validate_model


def main() -> None:
    model_path, facts_path, output = map(Path, sys.argv[1:])
    before = model_path.read_bytes()
    current = ModelStore(model_path).read()
    extra = parse(Facts, load_json(facts_path))
    original = next(item for item in current.facts if item.source_root_id == "frontend")
    assert extra.source.digest == original.source.digest
    assert set(extra.symbols) == set(original.symbols)
    assert extra.id != original.id and extra.source_root_id != original.source_root_id
    candidate = current.model_copy(deep=True)
    candidate.facts.append(extra)
    candidate.bindings.append(
        Binding(
            id="identity-collision-check",
            snapshot_id=extra.id,
            source_version=extra.source.digest,
            location=extra.symbols["src/utils.ts|src.utils.readDocument"],
            status="current",
        )
    )
    validate_model(candidate.model_dump())
    assert model_path.read_bytes() == before
    output.write_text(
        json.dumps(
            {
                "same_model_id": candidate.id,
                "canonical_revision_unchanged": current.revision,
                "original_root": original.source_root_id,
                "alternate_root": extra.source_root_id,
                "same_manifest_digest": extra.source.digest,
                "same_symbol_keys": sorted(extra.symbols),
                "different_snapshot_ids": [original.id, extra.id],
                "validated_together": True,
                "canonical_model_sha256_unchanged": hashlib.sha256(before).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
