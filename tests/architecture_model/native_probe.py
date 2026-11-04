"""Standalone native extraction probe; guards never enter the production package."""

import atexit
import importlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import FrameType

ATTEMPTS: list[str] = []
STATE: dict = {"completed": False}


def audit(event: str, arguments: tuple) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto"}:
        ATTEMPTS.append(event)
        raise AssertionError(event)


def profile(frame: FrameType, event: str, argument: object) -> None:
    module = frame.f_globals.get("__name__") or ""
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
        ATTEMPTS.append(f"{module}.{name}")
        raise AssertionError(ATTEMPTS[-1])


def main() -> None:
    for key in list(os.environ):
        if key.endswith("API_KEY") or key in {"DO_NOT_TRACK", "CODEBOARDING_TELEMETRY"}:
            del os.environ[key]
    baseline = set(threading.enumerate())
    repo, node, pyright, tokei, output = map(Path, sys.argv[1:])
    STATE.update(output=output, baseline=baseline)
    atexit.register(finish)
    sys.addaudithook(audit)
    sys.setprofile(profile)
    threading.setprofile(profile)
    worker = importlib.import_module("architecture_model.facts_worker")
    facts = worker.extract(repo.resolve(), "probe", node.resolve(), pyright.resolve(), tokei.resolve())
    STATE.update(
        completed=True,
        telemetry_client_absent=worker.telemetry._client is None,
        symbols=len(facts.symbols),
        calls=len(facts.calls),
    )


def finish() -> None:
    failed = True
    try:
        _finish_report()
        failed = False
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
        if failed:
            os._exit(1)


def _finish_report() -> None:
    deadline = time.monotonic() + 5
    for thread in set(threading.enumerate()) - STATE["baseline"]:
        thread.join(max(0, deadline - time.monotonic()))
    alive = [thread.name for thread in set(threading.enumerate()) - STATE["baseline"]]
    passed = STATE["completed"] and not ATTEMPTS and not alive and STATE["telemetry_client_absent"]
    STATE["output"].write_text(
        json.dumps(
            {
                "status": "PASS" if passed else "FAIL",
                "attempts": ATTEMPTS,
                "unfinished_threads": alive,
                "telemetry_client_absent": STATE.get("telemetry_client_absent", False),
                "symbols": STATE.get("symbols", 0),
                "calls": STATE.get("calls", 0),
            }
        )
    )
    sys.stdout.flush()
    sys.stderr.flush()
    if not passed:
        raise AssertionError("Native probe failed")


if __name__ == "__main__":
    main()
