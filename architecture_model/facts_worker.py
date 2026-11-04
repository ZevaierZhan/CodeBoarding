import ast
import contextlib
import hashlib
import inspect
import json
import logging
import os
import subprocess
import sys
import tempfile
from stat import S_ISDIR, S_ISREG
from pathlib import Path

# The worker owns its process environment, before any native telemetry imports.
os.environ["CODEBOARDING_TELEMETRY"] = "false"
os.environ["DO_NOT_TRACK"] = "1"

from architecture_model.schema import Call, CallSite, Facts, Location, SourceVersion
from architecture_model.store import atomic_write
from architecture_model.validation import digest, validate_facts
from infra.logging_config import setup_logging
from infra.monitoring.telemetry.service import telemetry
from infra.repo_utils.ignore import CODEBOARDINGIGNORE_TEMPLATE, RepoIgnoreManager
from infra.utils import get_config
from infra.vscode_constants import VSCODE_CONFIG
from static_analyzer import StaticAnalyzer
from static_analyzer.config import Language
from static_analyzer.engine.adapters.python_adapter import PythonAdapter


class ExtractionErrors(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("static_analyzer"):
            self.messages.append(record.getMessage())


def extract(repo: Path, project_id: str, node: Path, pyright: Path, tokei: Path) -> Facts:
    if telemetry._client is not None:
        raise RuntimeError("Telemetry initialized before opt-out")
    VSCODE_CONFIG["lsp_servers"]["python"]["command"] = [str(node), str(pyright), "--stdio"]
    VSCODE_CONFIG["tools"]["tokei"]["command"] = [str(tokei), "-o", "json"]
    python_command = get_config("lsp_servers")["python"]["command"]
    tokei_command = get_config("tools")["tokei"]["command"]
    extraction_scope = _extraction_scope(repo, python_command, tokei_command)
    before, trees = _manifest(repo)
    if not before:
        raise ValueError("No Python source files in extraction scope")
    failures = ExtractionErrors()
    root_logger = logging.getLogger()
    with contextlib.ExitStack() as lifecycle:
        root_logger.addHandler(failures)
        lifecycle.callback(root_logger.removeHandler, failures)
        analyzer = StaticAnalyzer(repo, resident_servers=False)
        lifecycle.callback(analyzer.stop_clients)
        if any(config.adapter.language_enum != Language.PYTHON for config in analyzer._engine_configs):
            raise ValueError("M1 export accepts Python-only analysis roots")
        with tempfile.TemporaryDirectory(prefix="codeboarding-static-") as cache:
            analyzer.start_clients()
            results = analyzer.analyze(Path(cache), skip_cache=True)
    if failures.messages:
        raise RuntimeError("Static engine reported errors: " + "; ".join(failures.messages))
    graph = results.get_cfg(Language.PYTHON)
    extracted_files = {
        Path(path).resolve().relative_to(repo).as_posix() for path in results.get_source_files(Language.PYTHON)
    }
    if extracted_files != set(before):
        raise ValueError(f"Incomplete extraction: expected {sorted(before)}, got {sorted(extracted_files)}")
    symbols: dict[str, Location] = {}
    for name, symbol in sorted(graph.nodes.items()):
        path = Path(symbol.file_path).resolve().relative_to(repo).as_posix()
        symbols[f"{path}|{name}"] = Location(
            path=path,
            symbol=name,
            kind=symbol.type.name,
            content_hash=before[path],
            start=symbol.line_start,
            end=symbol.line_end,
        )
    for path, tree in trees.items():
        for function in ast.walk(tree):
            if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and not any(
                item.path == path
                and item.symbol.rsplit(".", 1)[-1] == function.name
                and item.start <= function.lineno <= item.end
                for item in symbols.values()
            ):
                raise ValueError(f"Callable missing from static extraction: {path}:{function.lineno}")
    calls = [
        Call(
            source=edge.get_source(),
            target=edge.get_destination(),
            sites=[
                CallSite(
                    path=Path(str(site.get("file", edge.src_node.file_path))).resolve().relative_to(repo).as_posix(),
                    line=site["line"],
                    column=site.get("column", 0),
                )
                for site in edge.call_sites
            ],
        )
        for edge in graph.edges
    ]
    git = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
    facts = Facts(
        id="pending",
        project_id=project_id,
        source=SourceVersion(
            digest=digest(before),
            git_commit=git.stdout.strip() if git.returncode == 0 else "",
            files=before,
            scope="All Python files discovered by PythonAdapter and repository ignore rules",
        ),
        symbols=symbols,
        file_locations={
            path: Location(
                path=path,
                symbol="",
                kind="FILE",
                content_hash=content_hash,
                start=1,
                end=max(1, len((repo / path).read_bytes().splitlines())),
            )
            for path, content_hash in before.items()
        },
        calls=sorted(calls, key=lambda call: (call.source, call.target)),
        tools={
            "engine": "StaticAnalyzer/PythonAdapter",
            "node": python_command[0],
            "pyright_js": python_command[1],
            "tokei": tokei_command[0],
            "python_command": json.dumps(python_command),
            "tokei_command": json.dumps(tokei_command),
            "maintenance_scope": extraction_scope,
        },
        limitations=[
            "Static call records are not runtime execution or a complete dynamic call graph.",
            "Names, clustering, responsibilities and design intent are not extracted code facts.",
            "content_hash is SHA-256 of exact file bytes; source digest covers the declared Python scope.",
            "Git commit is context only; the content manifest identifies dirty and untracked source.",
        ],
    )
    facts.id = digest(facts.model_dump(exclude={"id"}))
    if _manifest(repo)[0] != before:
        raise ValueError("Source changed during extraction; rerun on a stable working tree")
    if _extraction_scope(repo, python_command, tokei_command) != extraction_scope:
        raise ValueError("Extraction configuration changed during analysis")
    validate_facts(facts)
    return facts


def main() -> int:
    setup_logging()
    try:
        repo, project_id, output, node, pyright, tokei = sys.argv[1:]
        with contextlib.redirect_stdout(sys.stderr):
            facts = extract(Path(repo), project_id, Path(node), Path(pyright), Path(tokei))
        atomic_write(Path(output), facts.model_dump())
        return 0
    except Exception:
        logging.exception("Facts export failed")
        return 1


def _manifest(repo: Path) -> tuple[dict[str, str], dict[str, ast.Module]]:
    adapter = PythonAdapter()
    manager = RepoIgnoreManager(repo)
    files = [path for path in _strict_files(repo, repo, manager, set()) if path.suffix in adapter.file_extensions]
    discovered = adapter.discover_source_files(repo, manager)
    if set(files) != set(discovered):
        raise ValueError("Native discovery differs from strict source inventory")
    manifest: dict[str, str] = {}
    trees: dict[str, ast.Module] = {}
    for path in sorted(files):
        relative = path.resolve().relative_to(repo).as_posix()
        content = path.read_bytes()
        trees[relative] = ast.parse(content, filename=relative)
        manifest[relative] = hashlib.sha256(content).hexdigest()
    return manifest, trees


def _strict_files(root: Path, directory: Path, manager: RepoIgnoreManager, visited: set[Path]) -> list[Path]:
    resolved = directory.resolve()
    if not resolved.is_relative_to(root) or resolved in visited:
        raise ValueError("Source discovery encountered an escaping or repeated directory")
    visited.add(resolved)
    files = []
    for entry in sorted(directory.iterdir()):
        if manager.should_ignore(entry):
            continue
        mode = entry.stat().st_mode
        if S_ISDIR(mode):
            files.extend(_strict_files(root, entry, manager, visited))
        elif S_ISREG(mode):
            if not entry.resolve().is_relative_to(root):
                raise ValueError("Source discovery encountered an escaping file")
            files.append(entry)
    return files


def _extraction_scope(repo: Path, python_command: list[str], tokei_command: list[str]) -> str:
    patterns = []
    for relative, fallback in ((".gitignore", ""), (".codeboarding/.codeboardingignore", CODEBOARDINGIGNORE_TEMPLATE)):
        path = repo / relative
        patterns.extend((path.read_text(encoding="utf-8") if path.exists() else fallback).splitlines(keepends=True))
    engine_root = Path(__file__).resolve().parents[1] / "static_analyzer"
    implementation = {
        path.relative_to(engine_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in engine_root.rglob("*.py")
        if "servers" not in path.relative_to(engine_root).parts
    }
    implementation["ignore"] = hashlib.sha256(Path(inspect.getfile(RepoIgnoreManager)).read_bytes()).hexdigest()
    implementation["exporter"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    descriptor = {
        "protocol": "python-file-v1",
        "complete": True,
        "implementation": digest(implementation),
        "patterns": patterns,
        "tools": [
            hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in (*python_command[:2], tokei_command[0])
        ],
        "configuration": {
            name: hashlib.sha256((repo / name).read_bytes()).hexdigest()
            for name in ("pyrightconfig.json", "pyproject.toml", "setup.cfg")
            if (repo / name).exists()
        },
    }
    return json.dumps(descriptor, sort_keys=True, separators=(",", ":"))


if __name__ == "__main__":
    sys.exit(main())
