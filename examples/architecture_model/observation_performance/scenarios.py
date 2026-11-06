"""Measure disposable change scenarios through ModelStore and the CLI."""

import argparse
import json
import os
import runpy
import shutil
import time
from pathlib import Path

from architecture_model.cli import run
from architecture_model.store import ModelStore, atomic_write, revision_candidate
from architecture_model.validation import digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--files", type=int, default=100)
    args = parser.parse_args()
    directory = args.directory.resolve()
    runpy.run_path(str(Path(__file__).with_name("benchmark.py")))["prepare"](directory, args.files)
    model, mapping, plan = (directory / name for name in ("model.json", "mapping.json", "plan.json"))
    prefix = ["model", "--file", str(model)]
    baseline = model.read_bytes()
    original_map = mapping.read_bytes()
    original_facts = (directory / "all.json").read_bytes()
    path = directory / "source/package-0000/file-00000.ts"
    content, info = path.read_bytes(), path.stat()
    results = []
    for scenario in (
        "unchanged",
        "modified",
        "restored_mtime",
        "restored_bytes",
        "added",
        "deleted",
        "renamed",
        "mapping_copy",
        "mapping_bytes",
        "facts",
        "extractor",
        "revision",
        "model_content",
        "engine",
    ):
        plan.unlink(missing_ok=True)
        facts = directory / "all.json"
        run([*prefix, "maintenance-plan", "--source-map", str(mapping), "--facts", str(facts), "--output", str(plan)])
        if scenario in ("modified", "restored_mtime", "restored_bytes"):
            path.write_bytes(content.replace(b"0", b"9"))
            if scenario == "restored_bytes":
                path.write_bytes(content)
            if scenario != "modified":
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        elif scenario == "added":
            (path.parent / "untracked.ts").write_bytes(b"new")
        elif scenario == "deleted":
            path.unlink()
        elif scenario == "renamed":
            path.rename(path.with_name("renamed.ts"))
        elif scenario == "mapping_copy":
            copy = directory / "copy"
            shutil.copytree(directory / "source", copy)
            atomic_write(mapping, {root: str(copy) for root in ("all", "native", "subset")})
        elif scenario == "mapping_bytes":
            mapping.write_bytes(original_map + b"\n")
        elif scenario in ("facts", "extractor"):
            value = json.loads(original_facts)
            if scenario == "extractor":
                descriptor = json.loads(value["tools"]["maintenance_scope"])
                descriptor["implementation"] = "disposable extractor upgrade"
                value["tools"]["maintenance_scope"] = json.dumps(descriptor)
            else:
                value["limitations"].append("Disposable facts change, without changing Git HEAD")
            value["id"] = digest({key: entry for key, entry in value.items() if key != "id"})
            atomic_write(facts, value)
        elif scenario == "revision":
            store = ModelStore(model)
            store.commit(
                store.read().revision,
                lambda current: revision_candidate(
                    current, current.model_copy(deep=True), "benchmark", "Concurrent revision"
                ),
            )
        elif scenario == "model_content":
            value = json.loads(baseline)
            value["project"]["boundary"] += " changed without a revision"
            atomic_write(model, value)
        elif scenario == "engine":
            value = json.loads(plan.read_text())
            value["validity"]["engine_digest"] = "different engine"
            value["plan_id"] = digest({key: entry for key, entry in value.items() if key != "plan_id"})
            atomic_write(plan, value)
        started = time.perf_counter()
        result = run([*prefix, "maintenance-plan-check", "--plan", str(plan)])
        elapsed = time.perf_counter() - started
        expected_stale = scenario not in ("unchanged", "restored_bytes")
        assert result["requires_replan"] == expected_stale, (scenario, result)
        results.append(
            {
                "scenario": scenario,
                "seconds": elapsed,
                "status": result["status"],
                "requires_replan": result["requires_replan"],
                "reason_codes": [item["code"] for item in result["reasons"]],
            }
        )
        path.write_bytes(content)
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        (path.parent / "untracked.ts").unlink(missing_ok=True)
        path.with_name("renamed.ts").unlink(missing_ok=True)
        mapping.write_bytes(original_map)
        facts.write_bytes(original_facts)
        model.write_bytes(baseline)
    atomic_write(
        directory / "scenarios.json",
        {"files": args.files, "results": results, "model_unchanged": model.read_bytes() == baseline},
    )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
