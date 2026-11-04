"""Compare swallowed guard violations with the review baseline, without external I/O."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main() -> None:
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["CODEBOARDING_TELEMETRY"] = "false"
    env["DO_NOT_TRACK"] = "1"
    baseline = subprocess.check_output(
        ["git", "show", "a57e2e773a7e79971e202ca2fafe903e5347c399:docs/design/external-agent-p0/experiment.py"],
        cwd=ROOT,
        text=True,
    )
    baseline = baseline.replace(
        'FIXTURE = Path(__file__).parent / "fixture"', f"FIXTURE = Path({str(HERE / 'fixture')!r})"
    )
    marker = "            repo = Path(temporary)"
    assert marker in baseline
    injection = """            with socket.socket() as sock:
                try:
                    sock.connect(('192.0.2.1', 9))
                except AssertionError:
                    pass
"""
    baseline = baseline.replace(marker, injection + marker, 1)
    baseline_script = output / "baseline-injected.py"
    baseline_script.write_text(baseline, encoding="utf-8")
    baseline_output = output / "baseline-injected"
    old = subprocess.run(
        [sys.executable, str(baseline_script), "--output", str(baseline_output), "--pyright-js", sys.argv[2]],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    (output / "baseline-injected.log").write_text(old.stdout + old.stderr, encoding="utf-8")
    assert old.returncode == 0, old.stderr
    old_report = json.loads((baseline_output / "results.json").read_text())
    assert old_report["guard_attempts"] == ["socket.connect"], old_report
    assert "P0 probes passed" in old.stderr
    cases = []
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        for name in ["caught", "thread", "exit"]:
            destination = Path(temporary) / name
            result = subprocess.run(
                [sys.executable, str(HERE / "p0_guard.py"), "--output", str(destination), "--probe", name],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            report = json.loads((destination / "results.json").read_text())
            assert result.returncode == 1, result.stderr
            assert report["status"] == "FAIL" and report["guard_attempts"] == ["socket.connect"], report
            assert "probes PASS" not in result.stderr
            cases.append({"name": name, "test_status": "PASS", "probe_exit": result.returncode, "report": report})
    summary = {"status": "PASS", "baseline_exit": old.returncode, "baseline_report": old_report, "cases": cases}
    (output / "guard-negative-results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
