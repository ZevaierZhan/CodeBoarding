import posixpath
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath


def normalize_repo_path(file_path: str | Path, repo_root: Path | str | None = None) -> str:
    """Return a portable repo-relative path string."""
    path = _portable_path(file_path)
    if path.is_absolute() and repo_root is not None:
        root = _portable_path(repo_root)
        if Path(file_path).is_absolute():
            path = _portable_path(Path(file_path).resolve())
            root = _portable_path(Path(repo_root).resolve())
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return "" if str(path) == "." else path.as_posix()


def to_relative_path(file_path: str | Path, repo_root: Path) -> str:
    """Convert a path under *repo_root* to a portable repo-relative path."""
    path = _portable_path(file_path)
    if not path.is_absolute():
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


def to_absolute_path(file_path: str | Path, repo_root: Path) -> str:
    """Expand a repo-relative path to an absolute path in the root's path dialect."""
    path = _portable_path(file_path)
    if path.is_absolute():
        return str(file_path)
    if repo_root.is_absolute():
        return str(repo_root / path.as_posix())
    return (_portable_path(repo_root) / path).as_posix()


def _portable_path(value: str | Path) -> PurePath:
    """Interpret serialized Windows paths independently of the host platform."""
    text = str(value)
    windows = PureWindowsPath(text)
    if windows.drive:
        return PureWindowsPath(posixpath.normpath(windows.as_posix()))
    # Relative cache paths historically accept Windows separators; POSIX absolute names keep literal backslashes.
    if not text.startswith("/"):
        text = text.replace("\\", "/")
    return PurePosixPath(posixpath.normpath(text))
