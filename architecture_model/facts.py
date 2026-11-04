import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from filelock import FileLock

from architecture_model.errors import ModelError
from architecture_model.schema import Facts
from architecture_model.store import atomic_write, load_json
from architecture_model.validation import parse, validate_facts


def export_facts(repo: Path, project_id: str, output: Path, node: Path, pyright: Path, tokei: Path) -> Facts:
    paths = [repo, node, pyright, tokei]
    if not repo.is_dir() or any(not path.is_file() for path in paths[1:]):
        raise ModelError("TOOL_MISSING", "/tools", "Repository and explicit Node, Pyright JS, Tokei paths must exist")
    with tempfile.TemporaryDirectory(prefix="codeboarding-facts-") as temporary:
        result = Path(temporary) / "facts.json"
        command = [
            sys.executable,
            "-m",
            "architecture_model.facts_worker",
            str(repo.resolve()),
            project_id,
            str(result),
            str(node.resolve()),
            str(pyright.resolve()),
            str(tokei.resolve()),
        ]
        try:
            process = run_worker(command)
        except subprocess.TimeoutExpired as error:
            raise ModelError("FACTS_FAILED", "/facts", "Static analysis exceeded 180 seconds") from error
        if process.stderr:
            sys.stderr.write(process.stderr)
        if process.returncode != 0 or not result.is_file():
            raise ModelError("FACTS_FAILED", "/facts", f"Static worker exited {process.returncode}; see stderr")
        facts = parse(Facts, load_json(result))
        validate_facts(facts)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(output) + ".lock", timeout=30):
        if output.exists():
            raise ModelError("ALREADY_EXISTS", str(output), "Facts publication never overwrites an existing file")
        atomic_write(output, facts.model_dump())
    return facts


def run_worker(command: list[str]) -> subprocess.CompletedProcess:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=sys.platform != "win32",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
    )
    try:
        stdout, stderr = process.communicate(timeout=180)
    except BaseException:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if sys.platform == "win32":
                process.kill()
            else:
                os.killpg(process.pid, 9)
            process.communicate(timeout=5)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
