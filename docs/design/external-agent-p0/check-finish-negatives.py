"""Verify finalization faults cannot turn guard failures into successful exits."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = "a5b405ac2f4df71131b9006563ff3a3e46013d09"
CHILD = """
import logging
import sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
from p0_guard import protection
fault, violation = sys.argv[2:4]
if violation == 'guard':
    try:
        sys.audit('socket.connect')
    except AssertionError:
        pass
    assert protection.attempts == ['socket.connect']
protection.completed = True
print('injection: ' + fault + ' ' + violation, file=sys.stderr, flush=True)
if fault == 'report':
    patch.object(protection, 'write_report', side_effect=OSError('injected report failure')).start()
elif fault == 'diagnostic':
    patch.object(logging.getLogger('p0_guard'), 'warning', side_effect=OSError('injected log failure')).start()
    patch.object(logging.getLogger('p0_guard'), 'exception', side_effect=OSError('injected diagnostic failure')).start()
elif fault == 'log':
    patch.object(logging.getLogger('p0_guard'), 'warning', side_effect=OSError('injected log failure')).start()
else:
    patch.object(getattr(sys, fault), 'flush', side_effect=OSError('injected flush failure')).start()
"""


def main() -> None:
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "finish-negative-results.json").write_text('{"status": "RUNNING"}', encoding="utf-8")
    results = []
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        root = Path(temporary)
        baseline = root / "baseline"
        baseline.mkdir()
        for name in ["p0_guard.py", "experiment.py", "check-render.cjs"]:
            content = subprocess.check_output(["git", "show", f"{BASELINE}:docs/design/external-agent-p0/{name}"])
            (baseline / name).write_bytes(content)
        cases = [("baseline", baseline, "report", "guard", 0)]
        cases += [
            ("current", HERE, fault, violation, 1)
            for fault in ["report", "log", "stdout", "stderr", "diagnostic"]
            for violation in ["guard", "clean"]
        ]
        for version, module, fault, violation, expected in cases:
            destination = root / f"{version}-{fault}-{violation}"
            result = subprocess.run(
                [sys.executable, "-c", CHILD, str(module), fault, violation, "--output", str(destination)],
                capture_output=True,
                text=True,
                timeout=30,
                env=dict(os.environ),
            )
            marker = f"injection: {fault} {violation}"
            assert marker in result.stderr, result.stderr
            record = {
                "version": version,
                "fault": fault,
                "violation": violation,
                "expected_exit": expected,
                "actual_exit": result.returncode,
            }
            report = json.loads((destination / "results.json").read_text(encoding="utf-8"))
            record["report_status"] = report["status"]
            if version == "current":
                assert report["status"] == ("RUNNING" if fault == "report" else "FAIL"), report
            results.append(record)
            (output / "finish-negative-results.json").write_text(
                json.dumps({"cases": results}, indent=2), encoding="utf-8"
            )
            assert result.returncode == expected, (record, result.stderr)
    (output / "finish-negative-results.json").write_text(
        json.dumps({"status": "PASS", "cases": results}, indent=2), encoding="utf-8"
    )
    print(json.dumps(results))


if __name__ == "__main__":
    main()
