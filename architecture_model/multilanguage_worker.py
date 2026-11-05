"""Normalize native adapters into root-scoped, immutable facts."""

import ast
import contextlib
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["CODEBOARDING_TELEMETRY"] = "false"
os.environ["DO_NOT_TRACK"] = "1"
os.environ["CODEBOARDING_INSTALL_DEPENDENCIES"] = "false"
os.environ["CODEBOARDING_STRICT_SYMBOL_IDENTITY"] = "true"

from architecture_model.facts_worker import ExtractionErrors, _strict_files
from architecture_model.schema import Call, CallSite, Facts, Location, SourceVersion
from architecture_model.store import atomic_write, load_json
from architecture_model.validation import digest, validate_facts
from infra.logging_config import setup_logging
from infra.repo_utils.ignore import CODEBOARDINGIGNORE_TEMPLATE, RepoIgnoreManager
from infra.utils import get_config
from infra.vscode_constants import VSCODE_CONFIG
from static_analyzer import StaticAnalyzer
from static_analyzer.config import SOURCE_EXTENSION_TO_LANGUAGE
from static_analyzer.engine.adapters import get_all_adapters
from static_analyzer.engine.adapters.java_adapter import JavaAdapter
from static_analyzer.typescript_config_scanner import TypeScriptConfigScanner


class NativeFailures(ExtractionErrors):
    def __init__(self) -> None:
        super().__init__()
        self.setLevel(logging.WARNING)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("static_analyzer") and (
            record.levelno >= logging.ERROR
            or any(
                message in record.getMessage()
                for message in (
                    "LSP error for request",
                    "LSP could not serve",
                    "Timeout waiting for",
                    "build import failed",
                )
            )
        ):
            self.messages.append(record.getMessage())


def extract_multilanguage(repo: Path, project_id: str, root_id: str, tool_file: Path) -> Facts:
    repo = repo.resolve()
    config = load_json(tool_file)
    if not isinstance(config, dict) or set(config) - {"lsp_servers", "tokei", "typescript_sdk", "jdtls_root"}:
        raise ValueError("Tools must contain lsp_servers and tokei only")
    servers = config.get("lsp_servers")
    if not isinstance(servers, dict) or not servers:
        raise ValueError("Explicit lsp_servers configuration required")
    for language, command in servers.items():
        if language not in VSCODE_CONFIG["lsp_servers"]:
            raise ValueError(f"Unknown language tool: {language}")
        _validate_command(command)
        VSCODE_CONFIG["lsp_servers"][language]["command"] = command
    _validate_command(config.get("tokei"))
    VSCODE_CONFIG["tools"]["tokei"]["command"] = config["tokei"]
    if sdk := config.get("typescript_sdk"):
        if not isinstance(sdk, str) or not Path(sdk).is_absolute() or not Path(sdk).is_file():
            raise ValueError("typescript_sdk must be an absolute tsserver.js file")
        VSCODE_CONFIG["lsp_servers"]["typescript"]["tsserver_path"] = sdk
    if jdtls := config.get("jdtls_root"):
        if not isinstance(jdtls, str) or not Path(jdtls).is_absolute() or not (Path(jdtls) / "plugins").is_dir():
            raise ValueError("jdtls_root must be an absolute JDTLS installation")
        VSCODE_CONFIG["lsp_servers"]["java"]["jdtls_root"] = jdtls
    before, languages = _inventory(repo)
    if not before:
        raise ValueError("No supported source files in extraction scope")
    for language in set(languages.values()) - {"vue"}:
        key = "typescript" if language == "javascript" and "typescript" in servers else language
        if key not in servers:
            raise ValueError(f"Missing explicit language tool for {language}; no facts published")
    selected = {
        "typescript" if language == "javascript" and "typescript" in servers else language
        for language in languages.values()
        if language != "vue"
    }
    config = {
        "tokei": config["tokei"],
        "lsp_servers": {language: servers[language] for language in sorted(selected)},
        **(
            {"typescript_sdk": config["typescript_sdk"]}
            if "typescript" in selected and config.get("typescript_sdk")
            else {}
        ),
        **({"jdtls_root": config["jdtls_root"]} if "java" in selected and config.get("jdtls_root") else {}),
    }
    if "java" in selected:
        jdtls_root = JavaAdapter._find_jdtls_root()
        if jdtls_root is None:
            raise ValueError("Java facts require an installed JDTLS distribution")
        config["jdtls_root"] = str(jdtls_root.resolve())
        VSCODE_CONFIG["lsp_servers"]["java"]["jdtls_root"] = config["jdtls_root"]
    descriptor = _descriptor(repo, config)
    symbols: dict[str, Location] = {}
    calls: list[Call] = []
    projects: dict[str, str] = {}
    failures = NativeFailures()
    root_logger = logging.getLogger()
    with contextlib.ExitStack() as lifecycle:
        root_logger.addHandler(failures)
        lifecycle.callback(root_logger.removeHandler, failures)
        analyzer = StaticAnalyzer(repo, resident_servers=False)
        lifecycle.callback(analyzer.stop_clients)
        configs = list(analyzer._engine_configs)
        if not configs:
            raise ValueError("Native scanner found no supported projects")
        ts_projects = {}
        if "typescript" in selected or "javascript" in selected:
            for project_config in TypeScriptConfigScanner(
                repo, ignore_manager=analyzer.ignore_manager
            ).find_typescript_projects():
                for source_file in project_config.files:
                    ts_projects[source_file.resolve().relative_to(repo).as_posix()] = project_config.root.relative_to(
                        repo
                    ).as_posix()
        for engine_config in configs:
            adapter = engine_config.adapter
            # Export each native project separately before native name-only graph merging.
            analyzer._engine_configs = [engine_config]
            analyzer.start_clients()
            with tempfile.TemporaryDirectory(prefix="codeboarding-multi-") as cache:
                result = analyzer.analyze(Path(cache), skip_cache=True)
            analyzer.stop_clients()
            language = adapter.results_language
            files = {Path(p).resolve().relative_to(repo).as_posix() for p in result.get_source_files(language)}
            expected = engine_config.source_files or adapter.discover_source_files(
                engine_config.project_path, analyzer.ignore_manager
            )
            expected_paths = {p.resolve().relative_to(repo).as_posix() for p in expected}
            if files != expected_paths or not files:
                raise ValueError(f"Incomplete {adapter.language} project extraction")
            project = engine_config.project_path.relative_to(repo).as_posix()
            for path in files:
                if path not in before or path in projects:
                    raise ValueError(f"Uninventoried or overlapping project file: {path}")
                projects[path] = ts_projects.get(path, project)
                if languages[path] == "rust":
                    crate = next(
                        (
                            parent
                            for parent in (repo / path).parents
                            if parent.is_relative_to(repo) and (parent / "Cargo.toml").is_file()
                        ),
                        None,
                    )
                    if crate:
                        projects[path] = crate.relative_to(repo).as_posix()
            graph = result.get_cfg(language)
            if not graph.nodes and adapter.language_enum.value != "python":
                raise ValueError(f"Empty {adapter.language} symbol extraction cannot establish facts")
            for name, node in sorted(graph.nodes.items()):
                path = Path(node.file_path).resolve().relative_to(repo).as_posix()
                key = f"{path}|{name}"
                location = Location(
                    path=path,
                    symbol=name,
                    kind=node.type.name,
                    content_hash=before[path],
                    start=node.line_start,
                    end=node.line_end,
                )
                if key in symbols:
                    raise ValueError(f"Native symbol identity collision: {key}")
                symbols[key] = location
            for edge in graph.edges:
                source_path = Path(edge.src_node.file_path).resolve().relative_to(repo).as_posix()
                target_path = Path(edge.dst_node.file_path).resolve().relative_to(repo).as_posix()
                calls.append(
                    Call(
                        source=f"{source_path}|{edge.get_source()}",
                        target=f"{target_path}|{edge.get_destination()}",
                        sites=[
                            CallSite(
                                path=Path(str(site.get("file", edge.src_node.file_path)))
                                .resolve()
                                .relative_to(repo)
                                .as_posix(),
                                line=site["line"],
                                column=site.get("column", 0),
                            )
                            for site in edge.call_sites
                        ],
                    )
                )
    if failures.messages:
        raise RuntimeError("Native extraction errors: " + "; ".join(failures.messages))
    unclaimed = set(before) - set(projects)
    if any(languages[path] != "vue" for path in unclaimed):
        raise ValueError(f"Source files omitted by native projects: {sorted(unclaimed)}")
    projects.update({path: "." for path in unclaimed})
    for path, language in languages.items():
        if language == "python":
            tree = ast.parse((repo / path).read_bytes(), filename=path)
            for function in ast.walk(tree):
                if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and not any(
                    loc.path == path
                    and loc.symbol.rsplit(".", 1)[-1] == function.name
                    and loc.start <= function.lineno <= loc.end
                    for loc in symbols.values()
                ):
                    raise ValueError(f"Callable missing: {path}:{function.lineno}")
    git = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
    facts = Facts(
        schema_version=2,
        id="pending",
        project_id=project_id,
        source_root_id=root_id,
        file_languages=languages,
        file_projects=projects,
        source=SourceVersion(
            digest=digest(before),
            git_commit=git.stdout.strip() if git.returncode == 0 else "",
            files=before,
            scope="Strict supported-source inventory; Vue file evidence only; native project symbol/call scope",
        ),
        symbols=symbols,
        calls=sorted(calls, key=lambda call: (call.source, call.target)),
        file_locations={
            path: Location(
                path=path,
                kind="FILE",
                content_hash=value,
                start=1,
                end=max(1, len((repo / path).read_bytes().splitlines())),
            )
            for path, value in before.items()
        },
        tools={
            "engine": "StaticAnalyzer/native adapters",
            "maintenance_scope": descriptor,
            "commands": json.dumps(config, sort_keys=True),
            "versions": json.dumps(_versions(config), sort_keys=True),
        },
        limitations=[
            "Static calls are not executions. External/unresolved calls, registrations and dynamic dispatch are incomplete.",
            "Non-Python symbol completeness is bounded by native LSP document symbols; no independent callable census.",
            "Vue SFC has file-level evidence only; native adapters do not discover .vue functions.",
            "Unknown source suffixes are outside scope. Root inventory completeness does not prove semantic completeness.",
            "Symbol identity is (source_root_id, language, file project, path|native name), scoped to an immutable snapshot.",
        ],
    )
    if _inventory(repo)[0] != before or _descriptor(repo, config) != descriptor:
        raise ValueError("Source or extraction configuration changed during analysis")
    facts.id = digest(facts.model_dump(exclude={"id"}))
    validate_facts(facts)
    return facts


def main() -> int:
    setup_logging()
    try:
        repo, project_id, output, root_id, tools = sys.argv[1:]
        with contextlib.redirect_stdout(sys.stderr):
            facts = extract_multilanguage(Path(repo), project_id, root_id, Path(tools))
        atomic_write(Path(output), facts.model_dump())
        return 0
    except Exception:
        logging.exception("Multilanguage facts export failed")
        return 1


def _validate_command(command: object) -> None:
    if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg for arg in command):
        raise ValueError("Tool command must be a nonempty argv array")
    if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
        raise ValueError("Tool executable must be an existing absolute file")


def _inventory(repo: Path) -> tuple[dict[str, str], dict[str, str]]:
    manager = RepoIgnoreManager(repo)
    files = _strict_files(repo, repo, manager, set())
    supported = {extension for adapter in get_all_adapters().values() for extension in adapter.file_extensions}
    selected = [path for path in files if path.suffix in supported or path.suffix == ".vue"]
    manifest = {path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in selected}
    languages = {
        path.relative_to(repo).as_posix(): (
            SOURCE_EXTENSION_TO_LANGUAGE[path.suffix].value if path.suffix != ".vue" else "vue"
        )
        for path in selected
    }
    return manifest, languages


def _descriptor(repo: Path, config: dict) -> str:
    engine = Path(__file__).resolve().parents[1]
    implementation = {
        str(path.relative_to(engine)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in ("static_analyzer", "architecture_model")
        for path in (engine / folder).rglob("*.py")
        if "servers" not in path.parts
    }
    implementation["ignore"] = hashlib.sha256((engine / "infra/repo_utils/ignore.py").read_bytes()).hexdigest()
    configuration = {}
    manager = RepoIgnoreManager(repo)
    for path in _strict_files(repo, repo, manager, set()):
        if path.name in {
            "Cargo.toml",
            "Cargo.lock",
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "pom.xml",
            "build.gradle",
            "pyproject.toml",
            "pyrightconfig.json",
            ".gitignore",
            ".codeboardingignore",
        } or path.name.startswith(("tsconfig", "jsconfig")):
            configuration[path.relative_to(repo).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    commands = [config["tokei"], *config["lsp_servers"].values()]
    tools = [
        digest(
            {
                str(index): hashlib.sha256(Path(arg).read_bytes()).hexdigest() if Path(arg).is_file() else arg
                for index, arg in enumerate(command)
            }
        )
        for command in commands
    ]
    if config.get("typescript_sdk"):
        tools.append(hashlib.sha256(Path(config["typescript_sdk"]).read_bytes()).hexdigest())
    java = get_config("lsp_servers").get("java", {})
    if "java" in config["lsp_servers"] and java.get("jdtls_root"):
        tools.append(
            digest(
                {
                    path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted((Path(java["jdtls_root"]) / "plugins").glob("*.jar"))
                }
            )
        )
    patterns = []
    for name, fallback in ((".gitignore", ""), (".codeboarding/.codeboardingignore", CODEBOARDINGIGNORE_TEMPLATE)):
        path = repo / name
        patterns.extend((path.read_text(encoding="utf-8") if path.exists() else fallback).splitlines(keepends=True))
    return json.dumps(
        {
            "protocol": "multilanguage-file-v2",
            "complete": True,
            "implementation": digest(implementation),
            "patterns": patterns,
            "tools": tools,
            "configuration": configuration,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _versions(config: dict) -> dict[str, str]:
    versions = {}
    for name, command in {"tokei": config["tokei"], **config["lsp_servers"]}.items():
        if len(command) > 1 and Path(command[1]).is_file():
            entry = Path(command[1])
            package = next(
                (parent / "package.json" for parent in entry.parents if (parent / "package.json").is_file()), None
            )
            if package:
                metadata = json.loads(package.read_text(encoding="utf-8"))
                versions[name] = f"{metadata.get('name', name)} {metadata.get('version', 'unknown')}"
                continue
        executable = command[:2] if len(command) > 1 and Path(command[1]).is_file() else command[:1]
        probe = subprocess.run([*executable, "--version"], capture_output=True, text=True, timeout=10)
        versions[name] = (
            (probe.stdout + probe.stderr).strip()[:1000]
            if probe.returncode == 0
            else f"version probe unavailable (exit {probe.returncode})"
        )
    if config.get("typescript_sdk"):
        metadata = json.loads(
            Path(config["typescript_sdk"]).parent.parent.joinpath("package.json").read_text(encoding="utf-8")
        )
        versions["typescript_sdk"] = metadata["version"]
    java = get_config("lsp_servers").get("java", {})
    if "java" in config["lsp_servers"] and java.get("jdtls_root"):
        versions["jdtls"] = ", ".join(
            path.name for path in sorted((Path(java["jdtls_root"]) / "plugins").glob("org.eclipse.jdt.ls.core_*.jar"))
        )
    return versions


if __name__ == "__main__":
    sys.exit(main())
