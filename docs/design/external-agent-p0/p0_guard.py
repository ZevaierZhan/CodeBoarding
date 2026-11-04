"""Process-lifetime protection for the standalone P0 experiment."""

import argparse
import atexit
import hashlib
import json
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path


class ProbeProtection:
    def __init__(self) -> None:
        os.environ["CODEBOARDING_TELEMETRY"] = "false"
        os.environ["DO_NOT_TRACK"] = "1"
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--output", type=Path, required=True)
        args, _ = parser.parse_known_args()
        self.output = args.output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.run_metadata = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "platform": sys.platform,
            "probe_source_sha256": {
                name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
                for name in ["experiment.py", "p0_guard.py", "check-render.cjs"]
            },
        }
        self.report: dict = {"status": "RUNNING", "guard_attempts": [], **self.run_metadata}
        self.attempts: list[str] = []
        self.completed = False
        self.threads = set(threading.enumerate())
        self.write_report()
        # Registered before native imports, so their exit callbacks run under protection first.
        atexit.register(self.finish)
        sys.addaudithook(self.audit)
        sys.setprofile(self.profile)
        threading.setprofile(self.profile)

    def audit(self, event: str, args: tuple) -> None:
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
            self.attempts.append(event)
            raise AssertionError(f"Forbidden network operation: {event}")

    def profile(self, frame, event, _arg) -> None:
        module = frame.f_globals.get("__name__", "")
        name = frame.f_code.co_name
        forbidden = module == "agents.llm_config" and name in {
            "configure_models",
            "validate_api_key_provided",
            "initialize_agent_llm",
        }
        forbidden |= module == "agents.scope_analysis_agent" and name == "analyze"
        forbidden |= module.startswith("langchain") and name in {
            "invoke",
            "ainvoke",
            "generate",
            "agenerate",
            "stream",
            "astream",
        }
        if event == "call" and forbidden:
            self.attempts.append(f"{module}.{name}")
            raise AssertionError(f"Internal LLM path entered: {self.attempts[-1]}")

    def write_report(self) -> None:
        (self.output / "results.json").write_text(json.dumps(self.report, indent=2), encoding="utf-8")

    def settle_threads(self) -> list[str]:
        deadline = time.monotonic() + 10
        pending = [t for t in threading.enumerate() if t not in self.threads]
        for thread in pending:
            thread.join(max(0, deadline - time.monotonic()))
        return [t.name for t in threading.enumerate() if t not in self.threads]

    def finish(self) -> None:
        failed = True
        try:
            alive = self.settle_threads()
            passed = self.completed and not self.attempts and not alive
            self.report.update(
                self.run_metadata,
                status="PASS" if passed else "FAIL",
                guard_attempts=self.attempts,
                unfinished_threads=alive,
                telemetry_client_absent=self.report.get("telemetry_client_absent", False),
            )
            self.write_report()
            logging.getLogger(__name__).warning("P0 probes %s: %s", self.report["status"], self.output)
            sys.stdout.flush()
            sys.stderr.flush()
            failed = not passed
        except BaseException:
            self.report["status"] = "FAIL"
            try:
                self.write_report()
            finally:
                logging.getLogger(__name__).exception("P0 finalization failed")
        finally:
            # atexit ignores exceptions, including failures in diagnostic output.
            if failed:
                os._exit(1)


protection = ProbeProtection()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--probe", choices=["caught", "thread", "exit"], required=True)
    args = parser.parse_args()

    def swallowed_connect() -> None:
        with socket.socket() as sock:
            try:
                sock.connect(("192.0.2.1", 9))
            except AssertionError:
                pass

    if args.probe == "thread":
        worker = threading.Thread(target=swallowed_connect)
        worker.start()
        worker.join()
    elif args.probe == "exit":
        atexit.register(swallowed_connect)
    else:
        swallowed_connect()
    protection.completed = True
