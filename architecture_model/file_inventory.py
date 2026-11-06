"""Export reproducible file evidence without loading analysis providers."""

import fnmatch
import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath

from filelock import FileLock

from architecture_model.errors import ModelError
from architecture_model.schema import Facts, Location, SourceVersion
from architecture_model.store import atomic_write
from architecture_model.validation import digest, validate_facts

DEFAULT_EXCLUDES = (".git", ".venv", "node_modules", "__pycache__", ".codegraph", ".codeboarding")
MAX_FILES = 100_000
MAX_ENTRIES = 500_000
MAX_FILE_BYTES = 256 * 1024 * 1024


def safe_file(root: Path, relative: str) -> Path:
    """Resolve portable manifest paths, rejecting links and escapes."""
    parts = PurePosixPath(relative)
    if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative or ":" in relative:
        raise ModelError("UNSAFE_PATH", "/source/files", "Expected a repository-relative POSIX path")
    current = root
    for part in parts.parts:
        current = current / part
        if current.is_symlink() or current.is_junction():
            raise ModelError("UNSAFE_PATH", "/source/files", "Source links and junctions are outside this protocol")
    resolved = current.resolve()
    if not resolved.is_relative_to(root):
        raise ModelError("UNSAFE_PATH", "/source/files", "Source path escapes its explicit mapping")
    return resolved


def file_digest(path: Path, *, enforce_source_limit: bool = True) -> tuple[str, int, tuple[int, ...]]:
    """Hash bounded chunks and reject changes during a read."""
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or (enforce_source_limit and before.st_size > MAX_FILE_BYTES):
        raise ModelError("INVENTORY_LIMIT", "/source/files", "Expected a regular file within the 256 MiB limit")
    fingerprint = _fingerprint(before)
    hashed = hashlib.sha256()
    lines = 0
    size = 0
    last = b""
    block_size = min(1024 * 1024, max(8192, before.st_size + 1))
    with path.open("rb") as stream:
        if _fingerprint(os.fstat(stream.fileno())) != fingerprint:
            raise ModelError("SOURCE_CHANGED", "/source/files", "Source identity changed before reading")
        while block := stream.read(block_size):
            size += len(block)
            if enforce_source_limit and size > MAX_FILE_BYTES:
                raise ModelError("INVENTORY_LIMIT", "/source/files", "File grew beyond the 256 MiB limit")
            hashed.update(block)
            lines += block.count(b"\n") + block.count(b"\r") - block.count(b"\r\n")
            if last == b"\r" and block.startswith(b"\n"):
                lines -= 1
            last = block[-1:]
        if _fingerprint(os.fstat(stream.fileno())) != fingerprint:
            raise ModelError("SOURCE_CHANGED", "/source/files", "Source changed while reading")
    if _fingerprint(path.stat()) != fingerprint or size != before.st_size:
        raise ModelError("SOURCE_CHANGED", "/source/files", "Source changed while reading")
    return hashed.hexdigest(), max(1, lines + int(bool(last) and last not in (b"\n", b"\r"))), fingerprint


def export_inventory(
    repo: Path,
    project_id: str,
    output: Path,
    source_root_id: str,
    includes: list[str],
    excludes: list[str],
) -> Facts:
    if not repo.is_dir() or not source_root_id.strip() or not project_id.strip():
        raise ModelError("USAGE_ERROR", "/repo", "Existing repository, project and stable root ID are required")
    root = repo.resolve()
    output = output.resolve()
    if output.is_relative_to(root):
        raise ModelError("USAGE_ERROR", "/output", "Publish inventory outside the scanned source root")
    includes = sorted(set(includes or ["*"]))
    excludes = sorted(set(excludes))
    rules = {"include": includes, "exclude": excludes, "excluded_directory_names": list(DEFAULT_EXCLUDES)}
    descriptor = {
        "protocol": "file-inventory-v1",
        "complete": True,
        "implementation": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "patterns": includes,
        "tools": [],
        "configuration": {
            "rules": json.dumps(rules, sort_keys=True),
            "matching": "fnmatchcase over root-relative POSIX paths; star includes slash; exclude prunes directories",
            "links": "reject non-ignored symlinks and junctions",
            "hash": "sha256 raw bytes",
            "limits": f"files={MAX_FILES}; entries={MAX_ENTRIES}; bytes_per_file={MAX_FILE_BYTES}",
            "evidence": "file content only; no symbols, calls or runtime analysis",
        },
    }
    before = _scan(root, includes, excludes)
    manifest = {path: record[0] for path, record in before.items()}
    snapshot = Facts(
        schema_version=2,
        id="pending",
        project_id=project_id,
        source_root_id=source_root_id,
        source=SourceVersion(digest=digest(manifest), files=manifest, scope="Complete file-inventory-v1 selection"),
        symbols={},
        calls=[],
        file_locations={
            path: Location(path=path, kind="FILE", content_hash=record[0], start=1, end=record[1])
            for path, record in before.items()
        },
        file_languages={path: "unclassified" for path in before},
        file_projects={path: "." for path in before},
        tools={"engine": "file-inventory-v1", "maintenance_scope": json.dumps(descriptor, sort_keys=True)},
        limitations=[
            "Proves selected file bytes only; no symbols, calls or runtime behavior are analyzed.",
            "Absent symbols do not imply absent code. Inventory completeness is not symbol completeness.",
            "Excluded directories and patterns are outside scope; file languages are unclassified.",
            "Physical source range is root-relative and requires an explicit local root mapping.",
        ],
    )
    if _scan(root, includes, excludes) != before:
        raise ModelError("SOURCE_CHANGED", "/source/files", "Source inventory changed during export")
    snapshot.id = digest(snapshot.model_dump(exclude={"id"}))
    validate_facts(snapshot)
    output.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(output) + ".lock", timeout=30):
        if output.exists():
            raise ModelError("ALREADY_EXISTS", str(output), "Facts publication never overwrites an existing file")
        atomic_write(output, snapshot.model_dump())
    return snapshot


def _fingerprint(info: os.stat_result) -> tuple[int, ...]:
    # Windows Python 3.12 stat/fstat disagree on ctime (change time versus birth time).
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _scan(root: Path, includes: list[str], excludes: list[str]) -> dict[str, tuple[str, int, tuple[int, ...]]]:
    result: dict[str, tuple[str, int, tuple[int, ...]]] = {}
    pending = [root]
    entries = 0
    while pending:
        directory = safe_file(root, pending.pop().relative_to(root).as_posix())
        with os.scandir(directory) as children:
            for entry in children:
                entries += 1
                if entries > MAX_ENTRIES:
                    raise ModelError("INVENTORY_LIMIT", "/repo", "Inventory exceeds 500000 directory entries")
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if any(fnmatch.fnmatchcase(relative, pattern) for pattern in excludes):
                    continue
                if entry.name in DEFAULT_EXCLUDES and entry.is_dir():
                    continue
                path = safe_file(root, relative)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif any(fnmatch.fnmatchcase(relative, pattern) for pattern in includes):
                    if len(result) >= MAX_FILES:
                        raise ModelError("INVENTORY_LIMIT", "/repo", "Inventory exceeds 100000 selected files")
                    result[relative] = file_digest(path)
    return dict(sorted(result.items()))
