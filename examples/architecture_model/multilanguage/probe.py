"""Reproduce native facts exports without generating architecture explanations."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tools", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    target = output / "target"
    shutil.copytree(HERE / "source", target, ignore=shutil.ignore_patterns("node_modules", "target", ".codeboarding"))
    records = []
    for root in ("frontend", "backend"):
        subprocess.run(["git", "init", str(target / root)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(target / root), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(target / root),
                "-c",
                "user.name=M5 Probe",
                "-c",
                "user.email=m5@example.invalid",
                "commit",
                "-m",
                f"Independent {root} baseline",
            ],
            check=True,
            capture_output=True,
        )
    java_vue = output / "java-vue"
    shutil.copytree(HERE / "java-vue", java_vue)
    cases = [
        ("frontend", target / "frontend"),
        ("backend", target / "backend"),
        ("mixed", target),
        ("vue-typescript", java_vue / "frontend"),
        ("java", java_vue / "backend"),
        ("java-vue", java_vue),
    ]
    for name, repo in cases:
        destination = output / f"{name}.facts.json"
        command = [
            sys.executable,
            "-m",
            "architecture_model",
            "facts",
            "export",
            "--repo",
            str(repo),
            "--project-id",
            "m5-system",
            "--source-root-id",
            name,
            "--tools",
            str(args.tools.resolve()),
            "--output",
            str(destination),
        ]
        result = subprocess.run(command, cwd=ENGINE, capture_output=True, text=True, timeout=210)
        (output / f"{name}.stdout.json").write_text(result.stdout, encoding="utf-8")
        (output / f"{name}.stderr.log").write_text(result.stderr, encoding="utf-8")
        record = {"case": name, "command": command, "exit_code": result.returncode, "published": destination.exists()}
        if destination.exists():
            facts = json.loads(destination.read_text(encoding="utf-8"))
            record.update(
                snapshot_id=facts["id"],
                files=len(facts["source"]["files"]),
                symbols=len(facts["symbols"]),
                calls=len(facts["calls"]),
                languages=sorted(set(facts["file_languages"].values())),
            )
        records.append(record)
        (output / "results.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
