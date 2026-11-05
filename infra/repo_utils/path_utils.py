import posixpath
import os
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath


def normalize_repo_path(file_path: str | PurePath, repo_root: PurePath | str | None = None) -> str:
    """Return a portable repo-relative path string."""
    path = _portable_path(file_path)
    if path.is_absolute() and repo_root is not None:
        root = _portable_path(repo_root)
        if isinstance(file_path, (str, Path)) and Path(file_path).is_absolute():
            path = _portable_path(Path(file_path).resolve())
            root = _portable_path(Path(repo_root).resolve())
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return "" if str(path) == "." else path.as_posix()


def to_relative_path(file_path: str | PurePath, repo_root: Path) -> str:
    """Convert a path under *repo_root* to a portable repo-relative path."""
    path = _portable_path(file_path)
    if not path.is_absolute():
        if path.drive or ".." in path.parts:
            raise ValueError(f"Relative path escapes or depends on another drive: {file_path!s}")
        return normalize_repo_path(file_path)
    native = Path(file_path)
    root = _portable_path(repo_root)
    if native.is_absolute():
        path = _portable_path(native.resolve())
        root = _portable_path(repo_root.resolve())
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(file_path)


def to_absolute_path(file_path: str | PurePath, repo_root: Path) -> str:
    """Expand a repo-relative path to an absolute path in the root's path dialect."""
    path = _portable_path(file_path)
    if path.is_absolute():
        return str(file_path)
    if path.drive or ".." in path.parts:
        raise ValueError(f"Relative path escapes or depends on another drive: {file_path!s}")
    if isinstance(file_path, PurePosixPath) and isinstance(repo_root, PureWindowsPath) and "\\" in str(file_path):
        raise ValueError(f"A POSIX backslash filename cannot be restored on Windows: {file_path!s}")
    if repo_root.is_absolute():
        target = repo_root / path.as_posix()
        if not target.resolve().is_relative_to(repo_root.resolve()):
            raise ValueError(f"Relative path resolves outside repository root: {file_path!s}")
        return str(target)
    return (_portable_path(repo_root) / path).as_posix()


def serialize_cached_path(value: str, repo_root: Path) -> str:
    """Label native paths so relative filenames cannot masquerade as foreign absolute paths."""
    native = Path(value)
    if native.is_absolute() and not native.resolve().is_relative_to(repo_root.resolve()):
        dialect = "windows" if isinstance(native, PureWindowsPath) else "posix"
        return f"{dialect}:{native}"
    relative = to_relative_path(native, repo_root)
    to_absolute_path(PurePosixPath(relative), repo_root)
    return f"relative:{relative}"


def restore_cached_path(value: str, repo_root: Path, *, legacy: bool = False) -> str:
    """Restore labelled cache paths; reject ambiguous or unrepresentable old identities."""
    if legacy:
        windows = PureWindowsPath(value)
        if windows.drive or ("\\" in value and not value.startswith("/")):
            raise ValueError(f"Ambiguous legacy cache path requires reanalysis: {value!r}")
        dialect, path = ("posix" if value.startswith("/") else "relative"), value
    else:
        dialect, separator, path = value.partition(":")
        if not separator:
            raise ValueError(f"Missing cache path dialect: {value!r}")
    if dialect == "windows" and os.name == "nt" and PureWindowsPath(path).is_absolute():
        return to_absolute_path(PureWindowsPath(path), repo_root)
    if dialect == "posix" and os.name != "nt" and PurePosixPath(path).is_absolute():
        return to_absolute_path(PurePosixPath(path), repo_root)
    if dialect != "relative" or PurePosixPath(path).is_absolute():
        raise ValueError(f"Invalid or foreign absolute cache path requires reanalysis: {value!r}")
    if os.name == "nt" and ("\\" in path or ":" in path):
        raise ValueError(f"A POSIX filename cannot be restored on Windows: {value!r}")
    return to_absolute_path(PurePosixPath(path), repo_root)


def _portable_path(value: str | PurePath) -> PurePath:
    """Keep explicit path dialects; untyped relative strings follow the host."""
    text = str(value)
    if isinstance(value, PurePosixPath):
        return PurePosixPath(posixpath.normpath(text))
    windows = PureWindowsPath(text)
    if windows.drive:
        return PureWindowsPath(posixpath.normpath(windows.as_posix()))
    if isinstance(value, PureWindowsPath) or (os.name == "nt" and not text.startswith("/")):
        text = windows.as_posix()
    return PurePosixPath(posixpath.normpath(text))
