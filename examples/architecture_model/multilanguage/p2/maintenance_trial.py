"""Exercise legacy and explicit-root targets using real exported source facts."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from architecture_model.maintenance import preview, query, refresh, resolve
from architecture_model.schema import Facts
from architecture_model.store import ModelStore, load_json
from architecture_model.validation import parse
from architecture_model.viewer import export_html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / "legacy-source"
    source.mkdir()
    tools = json.loads(args.tools.read_text(encoding="utf-8"))
    store = ModelStore(output / "model.json")
    store.initialize(
        {
            "id": "m5-system",
            "name": "Legacy and explicit-root acceptance",
            "boundary": "Source maintenance targets, not runtime execution",
        },
        "M5 Agent",
    )
    versions = []
    for index in range(3):
        (source / "app.py").write_text(f"def value():\n    return {index+1}\n", encoding="utf-8")
        destination = output / f"legacy-{index}.facts.json"
        command = [
            sys.executable,
            "-m",
            "architecture_model",
            "facts",
            "export",
            "--repo",
            str(source),
            "--project-id",
            "m5-system",
            "--output",
            str(destination),
            "--node",
            tools["lsp_servers"]["python"][0],
            "--pyright",
            tools["lsp_servers"]["python"][1],
            "--tokei",
            tools["tokei"][0],
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        (output / f"legacy-{index}.response.json").write_text(result.stdout, encoding="utf-8")
        facts = parse(Facts, load_json(destination))
        versions.append(facts.id)
        if index == 0:
            binding = {
                "id": "legacy-binding",
                "snapshot_id": facts.id,
                "source_version": facts.source.digest,
                "location": next(iter(facts.symbols.values())).model_dump(),
                "status": "current",
            }
            store.apply(
                0,
                {
                    "author": "M5 Agent",
                    "summary": "Bind genuine Python v1 facts",
                    "operations": [
                        {"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()},
                        {"action": "create", "collection": "bindings", "id": binding["id"], "value": binding},
                    ],
                },
            )
        report = preview(store.read(), facts)
        refresh(store, facts, store.read().revision, report["token"], "M5 Agent")
        if index == 1:
            item = report["observations"][0]
            resolve(
                store,
                item["id"],
                {
                    "author": "M5 Agent",
                    "reason": "Inspected changed Python return value; this is a source review only",
                    "outcome": "confirmed",
                    "source_version": facts.source.digest,
                    "operations": [],
                },
                store.read().revision,
            )
    operations = []
    roots = {}
    for root in ("frontend", "backend"):
        snapshot = parse(Facts, load_json(args.native / f"{root}.facts.json"))
        roots[root] = snapshot
        location = next(iter(snapshot.symbols.values()))
        binding = {
            "id": root + "-binding",
            "snapshot_id": snapshot.id,
            "source_version": snapshot.source.digest,
            "location": location.model_dump(),
            "status": "current",
        }
        operations += [
            {"action": "create", "collection": "facts", "id": snapshot.id, "value": snapshot.model_dump()},
            {"action": "create", "collection": "bindings", "id": binding["id"], "value": binding},
        ]
    store.apply(
        store.read().revision,
        {"author": "M5 Agent", "summary": "Add genuine independent TS/Rust roots", "operations": operations},
    )
    before = store.read()
    (output / "before.json").write_text(json.dumps(before.model_dump(), indent=2) + "\n", encoding="utf-8")
    (output / "before-query.json").write_text(json.dumps(query(before), indent=2) + "\n", encoding="utf-8")
    export_html(before, output / "before.html", source)
    for root in ("frontend", "backend"):
        target = roots[root]
        report = preview(store.read(), target)
        refresh(store, target, store.read().revision, report["token"], "M5 Agent")
        current = store.read()
        assert current.maintenance_target_snapshot_id == versions[-1]
        assert current.maintenance[: len(before.maintenance)] == before.maintenance
        assert current.bindings == before.bindings
        current_query = query(current)
        assert all(
            item.id in current_query["latest_observation_ids"]
            for item in before.maintenance
            if item.target_snapshot_id == versions[-1]
        )
        (output / f"after-{root}-query.json").write_text(json.dumps(current_query, indent=2) + "\n", encoding="utf-8")
        export_html(current, output / f"after-{root}.html", source)
    (output / "result.json").write_text(
        json.dumps(
            {
                "legacy_latest": versions[-1],
                "explicit_targets": store.read().maintenance_targets,
                "legacy_pending_and_resolved_unchanged": True,
                "bindings_unchanged": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
