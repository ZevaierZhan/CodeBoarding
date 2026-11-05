"""Capture complete CLI reads and query bounded context from any target directory."""

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

MAX_OUTPUT = 4096
PATH_OPTIONS = {
    "--file",
    "--repo",
    "--output",
    "--source-root",
    "--project",
    "--facts",
    "--patch",
    "--review",
    "--node",
    "--pyright",
    "--tokei",
    "--tools",
    "--source-map",
}
COLLECTIONS = ("facts", "bindings", "components", "relations", "scenarios", "opinions", "verifications", "maintenance")


def engine_command(explicit: str) -> tuple[list[str], Path]:
    home = explicit
    if not home:
        installed = shutil.which("codeboarding-model")
        if installed:
            return [installed], Path.cwd()
        home = os.environ.get("CODEBOARDING_HOME", "")
    if not home:
        raise ValueError(
            "Supply --engine CODEBOARDING_HOME, install codeboarding-model in the engine environment, or set CODEBOARDING_HOME"
        )
    root = Path(home).resolve()
    if not (root / "architecture_model/cli.py").is_file() or not (root / "pyproject.toml").is_file():
        raise ValueError(f"Explicit engine checkout is unavailable: {root}")
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("uv is required for the selected engine checkout; prepare its environment separately")
    return [uv, "run", "--project", str(root), "--no-sync", "python", "-m", "architecture_model"], root


def absolute_arguments(arguments: list[str]) -> list[str]:
    result = list(arguments)
    for index, value in enumerate(arguments):
        option, separator, argument = value.partition("=")
        if option in PATH_OPTIONS:
            if separator:
                result[index] = option + "=" + str(Path(argument).resolve())
            elif index + 1 < len(arguments):
                result[index + 1] = str(Path(arguments[index + 1]).resolve())
    if result and result[0] == "model" and result != ["model", "schema"]:
        if not any(value == "--file" or value.startswith("--file=") for value in result):
            raise ValueError("Supply an explicit --file MODEL; the target model is not the engine's default file")
    return result


def invoke(engine: str, arguments: list[str], destination: Path) -> dict:
    prefix, directory = engine_command(engine)
    normalized = absolute_arguments(arguments)
    for index, argument in enumerate(normalized):
        if argument == "--file" and Path(normalized[index + 1]).resolve() == destination.resolve():
            raise ValueError("A CLI response must not replace the persistent model")
        if argument.startswith("--file=") and Path(argument.split("=", 1)[1]).resolve() == destination.resolve():
            raise ValueError("A CLI response must not replace the persistent model")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        process = subprocess.run([*prefix, *normalized], cwd=directory, stdout=output, timeout=240)
    if process.returncode == 2:
        raise RuntimeError(
            f"CLI result delivery failed; a write may have committed. Reread model revision; inspect {destination}"
        )
    try:
        envelope = json.loads(destination.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise RuntimeError(
            f"CLI response is incomplete or invalid; operation may have completed. Reread model revision; inspect {destination}"
        ) from error
    if process.returncode or envelope.get("ok") is not True:
        raise RuntimeError(
            f"CLI exit {process.returncode}; inspect {destination}: {envelope.get('error', 'Result delivery may have failed; reread model revision')}"
        )
    return envelope


def inventory(model: dict) -> list[dict]:
    rows = [
        {"id": model["id"], "collection": "model", "pointer": ""},
        {
            "id": model["project"]["id"],
            "collection": "project",
            "pointer": "/project",
            "name": model["project"]["name"],
        },
    ]
    for collection in COLLECTIONS:
        for index, item in enumerate(model[collection]):
            row = {"id": item["id"], "collection": collection, "pointer": f"/{collection}/{index}"}
            for field in ("name", "parent_id", "source_id", "target_id", "binding_id"):
                if field in item:
                    row[field] = item[field]
            if collection == "bindings":
                row.update(path=item["location"]["path"], symbol=item["location"]["symbol"])
                snapshot: dict = next((entry for entry in model["facts"] if entry["id"] == item["snapshot_id"]), {})
                row["source_root_id"] = snapshot.get("source_root_id", "")
                row["language"] = snapshot.get("file_languages", {}).get(item["location"]["path"], "legacy")
            if collection == "facts":
                row["source_root_id"] = item.get("source_root_id", "")
            if collection == "relations" and item.get("contract"):
                row["mechanism"] = item["contract"]["mechanism"]
                row["operation"] = item["contract"]["operation"]
            rows.append(row)
            if collection == "scenarios":
                rows.extend(
                    {
                        "id": step["id"],
                        "collection": "steps",
                        "scenario_id": item["id"],
                        "pointer": f"/scenarios/{index}/steps/{step_index}",
                    }
                    for step_index, step in enumerate(item["steps"])
                )
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Complete read contains duplicate object IDs")
    return rows


def complete_model(envelope: dict) -> dict:
    if envelope.get("ok") is not True or envelope["result"].get("complete") is not True:
        raise ValueError("Capture requires a successful complete:true read, never console fragments or scoped context")
    result = envelope["result"]
    model = result["model"]
    if (model["id"], model["revision"]) != (result["model_id"], result["revision"]):
        raise ValueError("Read envelope identity/revision differs from its model")
    return model


def capture(engine: str, model_path: Path, cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=False)
    snapshot = cache / "read.json"
    model = complete_model(invoke(engine, ["model", "--file", str(model_path.resolve()), "read"], snapshot))
    value = {
        "artifact_type": "temporary-complete-read-index",
        "model_path": str(model_path.resolve()),
        "model_id": model["id"],
        "revision": model["revision"],
        "read_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "inventory": inventory(model),
    }
    write_json(cache / "index.json", value)
    return overview(model, value, cache)


def load_context(cache: Path) -> tuple[dict, dict]:
    index = json.loads((cache / "index.json").read_text(encoding="utf-8"))
    content = (cache / "read.json").read_bytes()
    if (
        index.get("artifact_type") != "temporary-complete-read-index"
        or hashlib.sha256(content).hexdigest() != index["read_sha256"]
    ):
        raise ValueError("Temporary complete read is missing, altered or truncated; capture a new context")
    model = complete_model(json.loads(content))
    if (model["id"], model["revision"]) != (index["model_id"], index["revision"]):
        raise ValueError("Temporary read and index identity/revision disagree")
    if inventory(model) != index["inventory"]:
        raise ValueError("Temporary ID inventory differs from the complete read")
    return model, index


def overview(model: dict, index: dict, cache: Path) -> dict:
    scalar: dict = next((item for item in model["facts"] if item["id"] == model["maintenance_target_snapshot_id"]), {})
    explicit_targets = dict(model.get("maintenance_targets", {}))
    if scalar.get("source_root_id"):
        explicit_targets.setdefault(scalar["source_root_id"], scalar["id"])
    return {
        "artifact_type": index["artifact_type"],
        "cache": str(cache.resolve()),
        "model_path": index["model_path"],
        "model_id": model["id"],
        "revision": model["revision"],
        "project": {key: str(value)[:512] for key, value in model["project"].items()},
        "counts": {collection: len(model[collection]) for collection in COLLECTIONS},
        "facts": [
            {
                "id": item["id"],
                "source_root_id": item.get("source_root_id", ""),
                "source_version": item["source"]["digest"],
                "git_commit": item["source"]["git_commit"],
                "files": len(item["source"]["files"]),
            }
            for item in model["facts"][:5]
        ],
        "facts_shown": min(5, len(model["facts"])),
        "maintenance_target": scalar.get("id", "") if not scalar.get("source_root_id") else "",
        "maintenance_target_scope": "legacy root only; an overwritten legacy target is unknown",
        "named_maintenance_target_count": len(explicit_targets),
        "unresolved_observations": sum(
            item["disposition"] != "unchanged" and item["resolution"] is None for item in model["maintenance"]
        ),
        "notice": "Temporary read/index, not a writable model. Summary text may be shortened; query the complete read for exact values and all IDs.",
    }


def page(index: dict, collection: str, search: str, offset: int, limit: int) -> dict:
    rows = [
        row
        for row in index["inventory"]
        if (not collection or row["collection"] == collection)
        and search.casefold() in json.dumps(row, ensure_ascii=False).casefold()
    ]
    selected = rows[offset : offset + limit]
    result = {"total": len(rows), "offset": offset, "items": selected, "next_offset": offset + len(selected)}
    while len(json.dumps(result, ensure_ascii=True, separators=(",", ":"))) > MAX_OUTPUT - 128 and selected:
        selected.pop()
        result["next_offset"] = offset + len(selected)
    if offset < len(rows) and not selected:
        raise ValueError(
            "One inventory entry exceeds the output budget; use get with --output and query its exact fields"
        )
    return result


def select(model: dict, index: dict, identity: str, pointer: str) -> object:
    selected: object = model
    if identity:
        matches = [row for row in index["inventory"] if row["id"] == identity]
        if len(matches) != 1:
            raise ValueError(f"ID not present exactly once in complete inventory: {identity}")
        selected = walk(model, matches[0]["pointer"])
    return walk(selected, pointer)


def walk(value: object, pointer: str) -> object:
    if pointer and not pointer.startswith("/"):
        raise ValueError("Use an RFC 6901 JSON pointer beginning with /, or an empty pointer")
    for part in pointer.split("/")[1:]:
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict):
            value = value[key]
        elif isinstance(value, list):
            if not key.isdigit():
                raise ValueError("Array pointer requires a nonnegative index")
            value = value[int(key)]
        else:
            raise ValueError("JSON pointer descends into a scalar")
    return value


def check(engine: str, index: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="codeboarding-revision-") as temporary:
        result = invoke(
            engine, ["model", "--file", index["model_path"], "validate"], Path(temporary) / "revision.json"
        )["result"]
    if (result["model_id"], result["revision"]) != (index["model_id"], index["revision"]):
        raise ValueError(
            f"STALE_CONTEXT: cached revision {index['revision']}, current {result['revision']}; discard stale candidate, capture again and reconcile"
        )
    return {
        "current": True,
        "model_id": result["model_id"],
        "revision": result["revision"],
        "notice": "Apply still requires this expected revision; the store rejects races.",
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


def encode(value: object) -> str:
    output = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(output) > MAX_OUTPUT:
        raise ValueError(
            "Result exceeds 4096 characters; use a narrower pointer/page or get --output FILE, then query that file"
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine", default="", help="Explicit CodeBoarding checkout; otherwise installed CLI, then CODEBOARDING_HOME"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    read = commands.add_parser("capture")
    read.add_argument("--model", type=Path, required=True)
    read.add_argument("--cache", type=Path, required=True)
    for name in ("summary", "list", "get", "check"):
        command = commands.add_parser(name)
        command.add_argument("--cache", type=Path, required=True)
        if name == "list":
            command.add_argument("--collection", choices=(*COLLECTIONS, "steps", "model", "project"), default="")
            command.add_argument("--search", default="")
            command.add_argument("--offset", type=int, default=0)
            command.add_argument("--limit", type=int, default=10)
        if name == "get":
            command.add_argument("--id", default="")
            command.add_argument("--pointer", default="")
            command.add_argument("--output", type=Path)
    proxy = commands.add_parser("cli")
    proxy.add_argument("--response", type=Path, required=True)
    proxy.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            result = capture(args.engine, args.model, args.cache)
        elif args.command == "cli":
            arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            response = invoke(args.engine, arguments, args.response)
            result = {
                "response": str(args.response.resolve()),
                "result": {
                    key: value
                    for key, value in response["result"].items()
                    if key in {"model_id", "revision", "committed", "valid", "output", "facts_id", "source_version"}
                },
            }
        else:
            model, index = load_context(args.cache)
            if args.command == "summary":
                result = overview(model, index, args.cache)
            elif args.command == "list":
                if args.offset < 0 or not 1 <= args.limit <= 100:
                    raise ValueError("offset must be nonnegative and limit must be 1..100")
                result = page(index, args.collection, args.search, args.offset, args.limit)
            elif args.command == "get":
                result = select(model, index, args.id, args.pointer)
                if args.output:
                    if args.output.resolve() in {
                        Path(index["model_path"]).resolve(),
                        (args.cache / "read.json").resolve(),
                        (args.cache / "index.json").resolve(),
                    }:
                        raise ValueError("Query output must be separate from the model and temporary context")
                    write_json(args.output, result)
                    result = {"output": str(args.output.resolve()), "bytes": args.output.stat().st_size}
            else:
                result = check(args.engine, index)
        output = encode({"ok": True, "result": result})
        print(output)
        return 0
    except (OSError, ValueError, KeyError, IndexError, RuntimeError, subprocess.SubprocessError) as error:
        logging.exception("Model context helper failed")
        failure = {"ok": False, "error": str(error)[:2000]}
        while len(json.dumps(failure, ensure_ascii=True)) > MAX_OUTPUT:
            failure["error"] = str(failure["error"])[: len(str(failure["error"])) // 2]
        print(encode(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
