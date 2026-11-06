"""Share exact workspace observations within one scan boundary."""

import os
import stat
from pathlib import Path, PurePosixPath

from architecture_model.errors import ModelError
from architecture_model.file_inventory import DEFAULT_EXCLUDES, MAX_ENTRIES, file_digest, safe_file
from architecture_model.validation import digest

JUNCTION_TAG = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)


class PathObservation:
    """Validate shared ancestors once, with an independent closing identity check."""

    def __init__(self):
        self.parents: dict[tuple[Path, str], tuple[Path, int, int]] = {}

    def file(self, root: Path, relative: str) -> Path:
        parts = PurePosixPath(relative)
        if not relative or parts.is_absolute() or ".." in parts.parts or "\\" in relative or ":" in relative:
            raise ModelError("UNSAFE_PATH", "/source/files", "Expected a repository-relative POSIX path")
        parent_relative = parts.parent.as_posix()
        key = (root, parent_relative)
        if key not in self.parents:
            parent = safe_file(root, parent_relative)
            try:
                info = parent.stat()
            except FileNotFoundError:
                return safe_file(root, relative)
            self.parents[key] = (parent, info.st_dev, info.st_ino)
        parent = self.parents[key][0]
        path = parent / parts.name
        try:
            info = path.lstat()
        except FileNotFoundError:
            return path
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) == JUNCTION_TAG:
            raise ModelError("UNSAFE_PATH", "/source/files", "Source links and junctions are outside this protocol")
        return path

    def finish(self) -> None:
        for (root, relative), (parent, device, inode) in self.parents.items():
            checked = safe_file(root, relative)
            info = checked.stat()
            if checked != parent or (info.st_dev, info.st_ino) != (device, inode):
                raise ModelError("SOURCE_CHANGED", "/source-map", "Source directory changed during coverage")


class ObservationContext:
    """A single boundary; never retain this object across scans or commands."""

    def __init__(self, expected_hashes: dict[str, str]):
        self.expected_hashes = expected_hashes
        self.directories: dict[str, dict] = {}
        self.hashes: dict[tuple, tuple[str, tuple[int, ...]]] = {}
        self.verified: set[str] = set()
        self.roots: set[Path] = set()

    def workspace(self, directory: Path) -> dict:
        self.roots.add(directory)
        key = os.path.normcase(str(directory))
        if key in self.directories:
            return self.directories[key]
        entries: list[tuple] = []
        pending = [directory]
        while pending:
            parent = pending.pop()
            relative = parent.relative_to(directory).as_posix()
            checked = safe_file(directory, relative) if parent != directory else directory.resolve()
            if checked != parent:
                raise ModelError("SOURCE_CHANGED", "/source-map", "Source directory changed during observation")
            before = parent.stat()
            with os.scandir(parent) as children:
                for child in children:
                    if child.name in DEFAULT_EXCLUDES:
                        continue
                    if len(entries) >= MAX_ENTRIES:
                        raise ModelError("INVENTORY_LIMIT", "/source-map", "Workspace observation exceeds entry limit")
                    if "\\" in child.name or ":" in child.name:
                        raise ModelError("UNSAFE_PATH", "/source/files", "Expected a repository-relative POSIX path")
                    path = parent / child.name
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) == JUNCTION_TAG:
                        raise ModelError(
                            "UNSAFE_PATH", "/source/files", "Source links and junctions are outside this protocol"
                        )
                    entries.append(
                        (
                            path.relative_to(directory).as_posix(),
                            info.st_dev,
                            info.st_ino,
                            info.st_size,
                            info.st_mtime_ns,
                        )
                    )
                    if stat.S_ISDIR(info.st_mode):
                        pending.append(path)
                    self._verify(path, info)
            after = parent.stat()
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mtime_ns):
                raise ModelError("SOURCE_CHANGED", "/source-map", "Source directory changed during observation")
            if parent != directory and safe_file(directory, relative) != parent:
                raise ModelError("SOURCE_CHANGED", "/source-map", "Source directory changed during observation")
        info = directory.stat()
        value = {
            "identity": [info.st_dev, info.st_ino, key],
            "entries_digest": digest(sorted(entries)),
            "entries": len(entries),
        }
        self.directories[key] = value
        return value

    def finish(self) -> None:
        for key in self.expected_hashes.keys() - self.verified:
            path = Path(key)
            root = next((root for root in self.roots if path.is_relative_to(root)), None)
            if root is None:
                raise ModelError("SOURCE_CHANGED", "/source-map", "Observed source root disappeared during observation")
            physical = safe_file(root, path.relative_to(root).as_posix())
            try:
                self._verify(physical, physical.stat(), key)
            except OSError as error:
                raise ModelError(
                    "SOURCE_CHANGED", "/source-map", "Observed source file disappeared during observation"
                ) from error

    def _verify(self, path: Path, info: os.stat_result, expected_key: str = "") -> None:
        key = expected_key or os.path.normcase(str(path))
        if key not in self.expected_hashes:
            return
        physical_id = (info.st_dev, info.st_ino) if info.st_ino else (key,)
        observed = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        if physical_id not in self.hashes:
            hashed, _, fingerprint = file_digest(path)
            self.hashes[physical_id] = (hashed, fingerprint)
        hashed, fingerprint = self.hashes[physical_id]
        if fingerprint != observed or hashed != self.expected_hashes[key]:
            raise ModelError("SOURCE_CHANGED", "/source-map", "Source content changed during observation")
        self.verified.add(key)
