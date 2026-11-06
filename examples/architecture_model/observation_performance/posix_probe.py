"""Exercise actual observation source on POSIX without importing project dependencies."""

import argparse
import ast
import hashlib
import json
import logging
import os
import platform
import stat
import tempfile
from pathlib import Path, PurePosixPath


def observation_namespace(root: Path) -> dict:
    namespace: dict = {
        "__name__": "observation_probe",
        "os": os,
        "stat": stat,
        "json": json,
        "hashlib": hashlib,
        "logging": logging,
        "Path": Path,
        "PurePosixPath": PurePosixPath,
    }
    selections = {
        "errors.py": {"ModelError"},
        "validation.py": {"digest"},
        "file_inventory.py": {
            "safe_file",
            "file_digest",
            "_fingerprint",
            "DEFAULT_EXCLUDES",
            "MAX_ENTRIES",
            "MAX_FILE_BYTES",
        },
        "observation.py": {"JUNCTION_TAG", "PathObservation", "ObservationContext"},
        "maintenance_plan.py": {"_workspace"},
    }
    for filename, names in selections.items():
        path = root / "architecture_model" / filename
        if not path.exists():
            continue
        selected: list[ast.stmt] = []
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in names for target in node.targets
            ):
                selected.append(node)
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "posix":
        raise ValueError("Run this supplemental probe on a POSIX filesystem")
    old = observation_namespace(args.reference)
    new = observation_namespace(args.candidate)
    logging.disable(logging.CRITICAL)
    cases = []
    with tempfile.TemporaryDirectory(prefix="m6c-observation-") as temporary:
        base = Path(temporary)
        for case in ("normal", "colon-file", "backslash-file", "colon-directory", "backslash-directory", "symlink"):
            root = base / case
            root.mkdir()
            (root / "ordinary.txt").write_bytes(b"unchanged\n")
            if case == "normal":
                (root / "with spaces").mkdir()
                (root / "with spaces/evidence-\u2603.txt").write_bytes(b"\x00\xff\r\n")
            elif case == "symlink":
                target = base / "outside.txt"
                target.write_bytes(b"outside")
                (root / "linked.txt").symlink_to(target)
            else:
                name = "unsupported:name" if case.startswith("colon") else "unsupported\\name"
                if case.endswith("directory"):
                    (root / name).mkdir()
                else:
                    (root / name).write_bytes(b"unmanifested bytes")
            before = old["_workspace"]({"root": root})
            after = new["_workspace"]({"root": root}, {})
            assert before == after, case
            assert bool(after[2]) == (case != "normal"), case
            cases.append({"case": case, "reference_equal": True, "rejected": bool(after[2])})
        root = base / "restored-mtime"
        root.mkdir()
        path = root / "file.txt"
        path.write_bytes(b"old")
        info = path.stat()
        observed = old["_workspace"]({"root": root})
        expected = {str(path): new["file_digest"](path)[0]}
        path.write_bytes(b"new")
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        assert old["_workspace"]({"root": root}) == observed
        try:
            new["_workspace"]({"root": root}, expected)
        except new["ModelError"] as error:
            assert error.code == "SOURCE_CHANGED"
        else:
            raise AssertionError("Closing content verification accepted changed bytes")
        cases.append({"case": "restored-mtime", "metadata_unchanged": True, "closing_content_rejected": True})
    result = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "scope": "Actual stdlib-only observation source; not the full project or ModelStore suite",
        "cases": cases,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": len(cases), "python": result["python"], "scope": result["scope"]}))


if __name__ == "__main__":
    main()
