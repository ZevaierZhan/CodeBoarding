import argparse
import json
import sys
from pathlib import Path
from typing import Never

from filelock import Timeout

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts, export_multilanguage
from architecture_model.maintenance import preview, query, rebind, refresh, resolve
from architecture_model.schema import Facts, Model
from architecture_model.store import ModelStore, load_json
from architecture_model.validation import parse
from architecture_model.viewer import export_html


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        raise ModelError("USAGE_ERROR", "/arguments", message)


def run(arguments: list[str]) -> dict:
    parser = Parser(description="Maintain architecture explanations without an internal provider")
    commands = parser.add_subparsers(dest="resource", required=True)
    model = commands.add_parser("model")
    model.add_argument("--file", type=Path, default=Path("architecture-model.json"))
    actions = model.add_subparsers(dest="action", required=True)
    initialize = actions.add_parser("init")
    initialize.add_argument("--project", type=Path, required=True)
    initialize.add_argument("--author", required=True)
    read = actions.add_parser("read")
    read.add_argument("--component", default="")
    read.add_argument("--scenario", default="")
    maintenance = actions.add_parser(
        "maintenance", help="Show current interpretation coverage and historical observations"
    )
    for name in ("binding", "component", "scenario"):
        maintenance.add_argument(f"--{name}", default="")
    for name in ("maintenance-preview", "maintenance-refresh"):
        action = actions.add_parser(name)
        action.add_argument("--facts", type=Path, required=True)
        if name == "maintenance-refresh":
            action.add_argument("--token", required=True)
            action.add_argument("--author", required=True)
            action.add_argument("--expected-revision", type=int, required=True)
    for name in ("maintenance-rebind", "maintenance-resolve"):
        action = actions.add_parser(name)
        action.add_argument("--item", required=True)
        action.add_argument("--expected-revision", type=int, required=True)
        if name == "maintenance-rebind":
            action.add_argument("--candidate", required=True)
            action.add_argument("--author", required=True)
            action.add_argument("--reason", required=True)
        else:
            action.add_argument("--review", type=Path, required=True)
    for name in ("validate", "diff", "apply"):
        action = actions.add_parser(name)
        action.add_argument("--patch", type=Path, required=name in ("diff", "apply"))
        if name == "apply":
            action.add_argument("--expected-revision", type=int, required=True)
    actions.add_parser("schema")
    export = actions.add_parser("export-html", help="Export one complete revision as an offline read-only document")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--source-root", type=Path)
    export.add_argument(
        "--source-map", type=Path, help="JSON object mapping stable source root IDs to local directories"
    )
    facts = commands.add_parser("facts").add_subparsers(dest="action", required=True).add_parser("export")
    for name in ("repo", "output"):
        facts.add_argument(f"--{name}", type=Path, required=True)
    for name in ("node", "pyright", "tokei", "tools"):
        facts.add_argument(f"--{name}", type=Path)
    facts.add_argument("--source-root-id", default="")
    facts.add_argument("--project-id", required=True)
    args = parser.parse_args(arguments)
    if args.resource == "facts":
        if args.tools:
            snapshot = export_multilanguage(args.repo, args.project_id, args.output, args.source_root_id, args.tools)
        else:
            if not all((args.node, args.pyright, args.tokei)) or args.source_root_id:
                raise ModelError(
                    "USAGE_ERROR", "/tools", "Use --tools with --source-root-id, or all legacy Python tool paths"
                )
            snapshot = export_facts(args.repo, args.project_id, args.output, args.node, args.pyright, args.tokei)
        return {
            "facts_id": snapshot.id,
            "source_version": snapshot.source.digest,
            "output": str(args.output),
            "symbols": len(snapshot.symbols),
            "calls": len(snapshot.calls),
        }
    store = ModelStore(args.file)
    if args.action == "schema":
        return Model.model_json_schema()
    if args.action == "init":
        initialized = store.initialize(load_json(args.project), args.author)
        return {"model_id": initialized.id, "revision": initialized.revision, "committed": True}
    if args.action == "read":
        return store.read_scope(args.component, args.scenario)
    if args.action == "export-html":
        mapping = load_json(args.source_map) if args.source_map else {}
        if not isinstance(mapping, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()
        ):
            raise ModelError("USAGE_ERROR", "/source-map", "Expected root ID to directory mapping")
        return export_html(
            store.read(), args.output, args.source_root, {key: Path(value) for key, value in mapping.items()}
        )
    if args.action == "maintenance":
        return query(store.read(), args.binding, args.component, args.scenario)
    if args.action == "maintenance-preview":
        return preview(store.read(), parse(Facts, load_json(args.facts)))
    if args.action == "maintenance-refresh":
        return refresh(store, parse(Facts, load_json(args.facts)), args.expected_revision, args.token, args.author)
    if args.action == "maintenance-rebind":
        return rebind(store, args.item, args.candidate, args.expected_revision, args.author, args.reason)
    if args.action == "maintenance-resolve":
        return resolve(store, args.item, load_json(args.review), args.expected_revision)
    if args.action == "apply":
        return store.apply(args.expected_revision, load_json(args.patch))
    if args.patch:
        proposed, difference = store.preview(load_json(args.patch))
        return {"valid": True, "candidate_revision": proposed.revision, "diff": difference, "committed": False}
    current = store.read()
    return {"valid": True, "model_id": current.id, "revision": current.revision, "committed": False}


def main() -> int:
    try:
        result = {"ok": True, "result": run(sys.argv[1:])}
        status = 0
    except ModelError as error:
        result = {"ok": False, "error": error.as_dict()}
        status = 1
    except (OSError, Timeout) as error:
        result = {"ok": False, "error": {"code": "IO_ERROR", "location": "/", "message": str(error)}}
        status = 1
    try:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + "\n")
        sys.stdout.flush()
    except (OSError, UnicodeError):
        # os.replace is the commit point; a delivery failure never rolls it back.
        sys.stderr.write("JSON output delivery failed; commit may have completed. Read the model revision.\n")
        return 2
    return status
