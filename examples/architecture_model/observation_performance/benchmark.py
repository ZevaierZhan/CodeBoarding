"""Measure real CLI planning with synthetic or read-only external inputs."""

import argparse
import cProfile
import ctypes
import hashlib
import importlib
import json
import os
import platform
import pstats
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from architecture_model.cli import run
from architecture_model.file_inventory import export_inventory
from architecture_model.store import ModelStore, atomic_write, load_json


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("faults", ctypes.c_uint32)] + [
        (name, ctypes.c_size_t)
        for name in ("peak", "working", "pool_peak", "pool", "nonpaged_peak", "nonpaged", "pagefile", "peak_pagefile")
    ]


def prepare(directory: Path, files: int) -> None:
    directory.mkdir(parents=True, exist_ok=False)
    source = directory / "source"
    source.mkdir()
    for index in range(files):
        parent = source / f"package-{index // 100:04}"
        parent.mkdir(exist_ok=True)
        (parent / f"file-{index:05}.ts").write_text(f"export const value = {index};\n", encoding="utf-8")
    store = ModelStore(directory / "model.json")
    store.initialize({"id": "benchmark", "name": "Benchmark", "boundary": "Synthetic overlapping roots"}, "benchmark")
    operations = []
    for root, patterns in (("all", ["*"]), ("native", ["*/*.ts"]), ("subset", ["package-0000/*"])):
        facts = export_inventory(source, "benchmark", directory / f"{root}.json", root, patterns, [])
        operations.append({"action": "create", "collection": "facts", "id": facts.id, "value": facts.model_dump()})
    store.apply(0, {"author": "benchmark", "summary": "Independent overlapping scopes", "operations": operations})
    atomic_write(directory / "mapping.json", {root: str(source.resolve()) for root in ("all", "native", "subset")})


def measure(arguments: list[str], instrument: bool) -> dict:
    counters: Counter = Counter()
    original_stat, original_lstat, original_open = os.stat, os.lstat, Path.open

    def counted_stat(*args, **kwargs):
        counters["stat"] += 1
        return original_stat(*args, **kwargs)

    def counted_lstat(*args, **kwargs):
        counters["lstat"] += 1
        return original_lstat(*args, **kwargs)

    def counted_open(path, *args, **kwargs):
        counters["path_opens"] += 1
        stream = original_open(path, *args, **kwargs)
        if args and args[0] == "rb":
            counters["binary_opens"] += 1
            return CountedReader(stream)
        return stream

    class CountedReader:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, *args):
            block = self.stream.read(*args)
            counters["binary_bytes_read"] += len(block)
            return block

    profile = cProfile.Profile()
    started = time.perf_counter()
    if instrument:
        with patch("os.stat", counted_stat), patch("os.lstat", counted_lstat), patch.object(Path, "open", counted_open):
            result = profile.runcall(run, arguments)
    else:
        result = run(arguments)
    elapsed = time.perf_counter() - started
    timings = {}
    if instrument:
        stats = pstats.Stats(profile)
        for (filename, _, name), (_, calls, own, cumulative, _) in vars(stats)["stats"].items():
            if name in (
                "_workspace",
                "coverage_report",
                "_engine_digest",
                "query",
                "preview",
                "_impact",
                "atomic_write",
                "file_digest",
                "safe_file",
                "check_plan",
                "generate_plan",
                "read",
                "validate_model",
            ):
                key = Path(filename).name + ":" + name
                timings[key] = {"calls": calls, "own_s": own, "inclusive_s": cumulative}
    if os.name == "nt":
        memory = MemoryCounters()
        memory.cb = ctypes.sizeof(memory)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(-1), ctypes.byref(memory), memory.cb):
            raise OSError("Cannot measure peak working set")
        peak = memory.peak
    else:
        peak = importlib.import_module("resource").getrusage(0).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    return {
        "seconds": elapsed,
        "status": result["status"],
        "summary": result.get("summary", {}),
        "requires_replan": result.get("requires_replan", False),
        "stdout_bytes": len(json.dumps({"ok": True, "result": result}, ensure_ascii=False).encode()) + 1,
        "plan_bytes": Path(result["output"]).stat().st_size if "output" in result else 0,
        "peak_rss_bytes": peak,
        "counters": dict(counters),
        "profile": timings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="Disposable output; never inside mapped sources")
    parser.add_argument("--prepare", type=int, default=0, metavar="FILES")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--mapping", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--worker", choices=("generate", "check"))
    parser.add_argument("--instrument", action="store_true")
    parser.add_argument("--same-process", type=int, default=1)
    parser.add_argument("--no-profile", action="store_true")
    parser.add_argument("--no-same-process", action="store_true")
    args = parser.parse_args()
    if args.runs < 1 or args.same_process < 1 or args.prepare < 0:
        parser.error("runs and same-process must be positive; prepare must be nonnegative")
    directory = args.directory.resolve()
    if args.prepare:
        prepare(directory, args.prepare)
    model = args.model or directory / "model.json"
    mapping = args.mapping or directory / "mapping.json"
    before = hashlib.sha256(model.read_bytes()).hexdigest()
    if args.worker:
        prefix = ["model", "--file", str(model)]
        results = []
        for _ in range(args.same_process):
            if args.worker == "generate":
                arguments = [
                    *prefix,
                    "maintenance-plan",
                    "--source-map",
                    str(mapping),
                    "--output",
                    str(directory / "plan.json"),
                ]
            else:
                arguments = [*prefix, "maintenance-plan-check", "--plan", str(directory / "plan.json")]
            results.append(measure(arguments, args.instrument))
        assert hashlib.sha256(model.read_bytes()).hexdigest() == before
        print(json.dumps(results))
        return
    root_map = load_json(mapping)
    if not isinstance(root_map, dict) or any(
        not isinstance(path, str) or not Path(path).is_absolute() for path in root_map.values()
    ):
        raise ValueError("Expected a mapping to absolute source directories")
    if any(directory.is_relative_to(Path(path).resolve()) for path in root_map.values()):
        raise ValueError("Benchmark output must be outside mapped source directories")
    protected = {model.resolve(), mapping.resolve()}
    if any(
        (directory / name).resolve() in protected
        for name in ("plan.json", "measurements.json", "samples-in-progress.json", "worker-failure.json")
    ):
        raise ValueError("Benchmark outputs must not replace model or mapping inputs")
    directory.mkdir(parents=True, exist_ok=True)
    samples: dict[str, list] = {
        "generate": [],
        "check": [],
        "same_process_check": [],
        "profile_generate": [],
        "profile_check": [],
    }
    for index in range(args.runs + int(not args.no_profile)):
        for mode in ("generate", "check"):
            if mode == "generate":
                (directory / "plan.json").unlink(missing_ok=True)
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--directory",
                str(directory),
                "--model",
                str(model),
                "--mapping",
                str(mapping),
                "--worker",
                mode,
            ]
            if index == args.runs:
                command.append("--instrument")
            start = time.perf_counter()
            rows = _run_worker(command, directory)
            rows[0]["process_seconds"] = time.perf_counter() - start
            samples[("profile_" if index == args.runs else "") + mode].extend(rows)
            atomic_write(directory / "samples-in-progress.json", samples)
    if not args.no_same_process:
        samples["same_process_check"] = _run_worker(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--directory",
                str(directory),
                "--model",
                str(model),
                "--worker",
                "check",
                "--same-process",
                str(args.runs),
            ],
            directory,
        )
    report = {
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
        },
        "model_unchanged": hashlib.sha256(model.read_bytes()).hexdigest() == before,
        "samples": samples,
        "timing_summary": {
            key: {
                "median_s": statistics.median(row["seconds"] for row in rows),
                "max_s": max(row["seconds"] for row in rows),
                "min_s": min(row["seconds"] for row in rows),
            }
            for key, rows in samples.items()
            if rows
        },
    }
    atomic_write(directory / "measurements.json", report)
    print(json.dumps(report["timing_summary"]))


def _run_worker(command: list[str], directory: Path) -> list[dict]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        diagnostic = directory / "worker-failure.json"
        atomic_write(diagnostic, {"exit_code": error.returncode, "stdout": error.stdout, "stderr": error.stderr})
        raise RuntimeError(f"Benchmark worker failed; inspect {diagnostic}") from error
    return json.loads(completed.stdout)


if __name__ == "__main__":
    main()
