import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _find_packages_on_disk() -> set[str]:
    """Return all Python packages (directories with __init__.py) under the repo root."""
    exclude_prefixes = {".venv", "tests", "repos", "build", "dist", "temp", "node_modules", "servers"}
    packages = set()
    for directory, subdirs, files in REPO_ROOT.walk():
        subdirs[:] = [name for name in subdirs if name not in exclude_prefixes and not name.startswith(".")]
        if "__init__.py" not in files:
            continue
        pkg = ".".join(directory.relative_to(REPO_ROOT).parts)
        packages.add(pkg)
    return packages


def _declared_packages() -> set[str]:
    """Return the packages listed in pyproject.toml [tool.setuptools] packages."""
    pyproject_path = REPO_ROOT / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    return set(data["tool"]["setuptools"]["packages"])


class TestPyprojectPackages(unittest.TestCase):
    def test_shared_clustering_ids_module_is_packaged(self):
        self.assertIn("infra", _declared_packages())
        self.assertTrue((REPO_ROOT / "infra" / "clustering_ids.py").is_file())

    def test_all_packages_declared_in_pyproject(self):
        on_disk = _find_packages_on_disk()
        declared = _declared_packages()
        missing = on_disk - declared
        self.assertEqual(
            missing,
            set(),
            f"Packages exist on disk but are missing from pyproject.toml [tool.setuptools] packages:\n"
            + "\n".join(f"  - {p}" for p in sorted(missing)),
        )

    def test_no_ghost_packages_in_pyproject(self):
        declared = _declared_packages()
        # Explicit namespace packages such as viewer_assets need no __init__.py.
        ghost = {name for name in declared if not REPO_ROOT.joinpath(*name.split(".")).is_dir()}
        self.assertEqual(
            ghost,
            set(),
            f"Packages declared in pyproject.toml do not exist on disk:\n"
            + "\n".join(f"  - {p}" for p in sorted(ghost)),
        )
