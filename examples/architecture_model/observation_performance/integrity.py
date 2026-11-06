"""Record aggregate read-only model and source integrity outside mapped roots."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from architecture_model.file_inventory import DEFAULT_EXCLUDES, file_digest, safe_file
from architecture_model.store import ModelStore, atomic_write, load_json
from architecture_model.validation import digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    mapping = load_json(args.mapping)
    if not isinstance(mapping, dict):
        raise ValueError("Expected a local root mapping")
    roots = {Path(path).resolve() for path in mapping.values()}
    output = args.output.resolve()
    if any(output.is_relative_to(root) for root in roots) or output == args.model.resolve():
        raise ValueError("Save integrity reports outside mapped sources and models")
    hashes = {}
    total = 0
    for root in sorted(roots):
        for parent, children, names in os.walk(root):
            children[:] = [name for name in children if name not in DEFAULT_EXCLUDES]
            for name in names:
                if name in DEFAULT_EXCLUDES:
                    continue
                relative = (Path(parent) / name).relative_to(root).as_posix()
                path = safe_file(root, relative)
                key = os.path.normcase(str(path))
                if key not in hashes:
                    hashes[key] = file_digest(path)[0]
                    total += path.stat().st_size
    model = ModelStore(args.model).read()
    semantic = {
        "facts": [item.model_dump() for item in model.facts],
        "scenarios": [item.model_dump() for item in model.scenarios],
        "maintenance": [item.model_dump() for item in model.maintenance],
        "bindings": [item.model_dump() for item in model.bindings],
        "verifications": [item.model_dump() for item in model.verifications],
    }
    result = {
        "revision": model.revision,
        "roots": len(mapping),
        "source_files": len(hashes),
        "source_bytes": total,
        "source_tree_sha256": digest(hashes),
        "model_sha256": hashlib.sha256(args.model.read_bytes()).hexdigest(),
        "protected_semantics_sha256": digest(semantic),
        "comparison_count": sum(item.analysis_kind == "comparison" for item in model.scenarios),
        "operation_count": sum(item.analysis_kind == "operation" for item in model.scenarios),
        "history_locations": sum(len(item.history) for item in model.bindings),
    }
    if args.compare:
        assert load_json(args.compare) == result, "Read-only acceptance inputs changed"
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(output, result)
    print(json.dumps({key: value for key, value in result.items() if not key.endswith("sha256")}))


if __name__ == "__main__":
    main()
