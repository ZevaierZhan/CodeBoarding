import argparse
import json
import sys
from pathlib import Path
from typing import Never

from filelock import Timeout

from architecture_model.errors import ModelError
from architecture_model.facts import export_facts
from architecture_model.schema import Model
from architecture_model.store import ModelStore, load_json


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
    for name in ("validate", "diff", "apply"):
        action = actions.add_parser(name)
        action.add_argument("--patch", type=Path, required=name in ("diff", "apply"))
        if name == "apply":
            action.add_argument("--expected-revision", type=int, required=True)
    actions.add_parser("schema")
    facts = commands.add_parser("facts").add_subparsers(dest="action", required=True).add_parser("export")
    for name in ("repo", "output", "node", "pyright", "tokei"):
        facts.add_argument(f"--{name}", type=Path, required=True)
    facts.add_argument("--project-id", required=True)
    args = parser.parse_args(arguments)
    if args.resource == "facts":
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
