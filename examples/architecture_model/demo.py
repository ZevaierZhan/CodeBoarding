"""Run continuous modeling through independent CLI processes against one model."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def cli(*arguments: str, success: bool = True) -> dict:
    environment = {key: value for key, value in os.environ.items() if not key.endswith("API_KEY")}
    process = subprocess.run(
        [sys.executable, "-m", "architecture_model", *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=210,
    )
    if bool(process.returncode == 0) != success:
        raise AssertionError(f"CLI exited {process.returncode}: {process.stdout}\n{process.stderr}")
    result = json.loads(process.stdout)
    assert result["ok"] == success, result
    return result["result"] if success else result["error"]


def write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def materialize(source: Path, destination: Path) -> None:
    for path in source.rglob("*.py.txt"):
        target = destination / path.relative_to(source).with_suffix("")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def claim(binding: str, explanation: str) -> dict:
    return {
        "kind": "inference",
        "explanation": explanation,
        "binding_ids": [binding],
        "assumptions": ["Responsibility is an interpretation of inspected source, not author intent."],
        "issues": [],
    }


def component(identity: str, binding: str, parent: str = "") -> dict:
    return {
        "id": identity,
        "name": identity,
        "responsibility": f"Explain {identity}",
        "rationale": "Separate entry, policy and formatting responsibilities.",
        "parent_id": parent,
        "binding_ids": [binding],
        "claim": claim(binding, f"Logical boundary around {identity}."),
    }


def scenario(identity: str, entries: list[tuple[str, str, str]]) -> dict:
    steps = [
        {
            "id": f"{identity}-{name}",
            "component_ids": [comp],
            "binding_ids": [binding],
            "claim": claim(binding, f"Inspect {name}; static explanation, not an observed execution."),
        }
        for name, comp, binding in entries
    ]
    return {
        "id": identity,
        "name": identity,
        "entry_step_id": steps[0]["id"],
        "steps": steps,
        "order": [step["id"] for step in steps],
        "transitions": [
            {
                "source_id": left["id"],
                "target_id": right["id"],
                "kind": "next",
                "condition": "Prior operation returns normally",
            }
            for left, right in zip(steps, steps[1:])
        ],
        "claim": claim(entries[0][2], "Handwritten explanation based on the fixture source."),
    }


def race(model: Path, output: Path, revision: int) -> list[dict]:
    worker = """
import json, pathlib, subprocess, sys, time
model, patch, revision, ready, go = sys.argv[1:]
pathlib.Path(ready).write_text('ready')
deadline = time.monotonic() + 20
while not pathlib.Path(go).exists():
    if time.monotonic() > deadline: raise TimeoutError('barrier')
    time.sleep(.01)
result = subprocess.run([sys.executable, '-m', 'architecture_model', 'model', '--file', model,
    'apply', '--expected-revision', revision, '--patch', patch], capture_output=True, text=True)
print(result.stdout, end='')
sys.exit(result.returncode)
"""
    processes = []
    go = output / "race-go"
    for index in range(2):
        patch = write(
            output / f"race-{index}.json",
            {
                "author": f"writer-{index}",
                "summary": "Race",
                "operations": [
                    {
                        "action": "update",
                        "collection": "components",
                        "id": "policy",
                        "value": {"name": f"writer-{index}"},
                    }
                ],
            },
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    worker,
                    str(model),
                    str(patch),
                    str(revision),
                    str(output / f"ready-{index}"),
                    str(go),
                ],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    deadline = time.monotonic() + 20
    try:
        while not all((output / f"ready-{index}").exists() for index in range(2)):
            assert time.monotonic() < deadline, "Race readiness timed out"
            time.sleep(0.01)
        go.write_text("go")
        responses = [json.loads(process.communicate(timeout=30)[0]) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
    assert sorted(process.returncode for process in processes) == [0, 1], responses
    assert [response["error"]["code"] for response in responses if not response["ok"]] == [
        "REVISION_CONFLICT"
    ], responses
    return responses


def run(output: Path, node: Path, pyright: Path, tokei: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    model = output / "architecture-model.json"
    prefix = ("model", "--file", str(model))
    project = write(
        output / "project.json",
        {
            "id": "order-project",
            "name": "Orders",
            "boundary": "Local route registration, order purchase and price quotation; no server or database.",
        },
    )
    cli(*prefix, "init", "--project", str(project), "--author", "example-agent")
    initial = model.read_bytes()
    tools = ("--node", str(node), "--pyright", str(pyright), "--tokei", str(tokei))
    p0 = output / "p0"
    materialize(ROOT / "docs/design/external-agent-p0/fixture", p0)
    p0_file = output / "p0-facts.json"
    cli("facts", "export", "--repo", str(p0), "--project-id", "p0", "--output", str(p0_file), *tools)
    original = json.loads(p0_file.read_text())
    expected = {("submit_order", "place_order"), ("place_order", "calculate_total"), ("place_order", "save_order")}
    edges = lambda facts: {
        (call["source"].rsplit(".", 1)[-1], call["target"].rsplit(".", 1)[-1]) for call in facts["calls"]
    }
    assert len(original["symbols"]) == 8 and edges(original) == expected
    changed = p0 / "orchestration/order.py"
    changed.write_text(
        changed.read_text()
        .replace("from persistence.store import save_order", "from persistence.receipt import format_receipt")
        .replace("save_order(total)", "format_receipt(total)")
    )
    changed_file = output / "p0-changed-facts.json"
    cli("facts", "export", "--repo", str(p0), "--project-id", "p0", "--output", str(changed_file), *tools)
    revised = json.loads(changed_file.read_text())
    assert edges(revised) == expected - {("place_order", "save_order")} | {("place_order", "format_receipt")}
    assert original["source"]["digest"] != revised["source"]["digest"]
    assert model.read_bytes() == initial
    fixture = output / "source"
    materialize(Path(__file__).parent / "fixture", fixture)
    facts_path = output / "facts.json"
    cli("facts", "export", "--repo", str(fixture), "--project-id", "order-project", "--output", str(facts_path), *tools)
    facts = json.loads(facts_path.read_text())
    bindings = []
    for location in facts["symbols"].values():
        name = location["symbol"].rsplit(".", 1)[-1]
        bindings.append(
            {
                "id": f"bind-{name}",
                "snapshot_id": facts["id"],
                "source_version": facts["source"]["digest"],
                "location": location,
                "status": "current",
                "history": [],
                "reason": "",
            }
        )
    revision = 0
    results: list[dict] = []

    def apply(operations: list[dict], summary: str, error: str = "") -> dict:
        nonlocal revision
        patch = write(
            output / f"patch-{len(results)}.json",
            {"author": "example-agent", "summary": summary, "operations": operations},
        )
        before = model.read_bytes()
        if error:
            response = cli(*prefix, "apply", "--expected-revision", str(revision), "--patch", str(patch), success=False)
            assert response["code"] == error, response
            assert model.read_bytes() == before
        else:
            for action in ("validate", "diff"):
                cli(*prefix, action, "--patch", str(patch))
                assert model.read_bytes() == before
            response = cli(*prefix, "apply", "--expected-revision", str(revision), "--patch", str(patch))
            revision += 1
            assert response["revision"] == revision
        results.append({"summary": summary, "response": response})
        return response

    create = lambda collection, value: {"action": "create", "collection": collection, "id": value["id"], "value": value}
    update = lambda collection, identity, value: {
        "action": "update",
        "collection": collection,
        "id": identity,
        "value": value,
    }
    delete = lambda identity: {"action": "delete", "collection": "components", "id": identity}
    apply(
        [
            create("facts", facts),
            *[create("bindings", binding) for binding in bindings],
            *[
                create("components", component(identity, binding))
                for identity, binding in [
                    ("application", "bind-start"),
                    ("entry", "bind-buy"),
                    ("policy", "bind-total"),
                    ("storage", "bind-save"),
                ]
            ],
            create("scenarios", scenario("startup", [("register", "application", "bind-start")])),
        ],
        "Save startup explanation",
    )
    a = scenario(
        "business-A",
        [("buy", "entry", "bind-buy"), ("price", "policy", "bind-total"), ("format", "storage", "bind-save")],
    )
    b = scenario("business-B", [("quote", "entry", "bind-quote"), ("price", "policy", "bind-total")])
    apply([create("scenarios", a)], "Add business A")
    apply([create("scenarios", b)], "Add business B sharing policy")
    before = model.read_bytes()
    scoped = cli(*prefix, "read", "--scenario", "business-A")
    assert not scoped["complete"] and len(scoped["model"]["scenarios"]) == 1
    assert model.read_bytes() == before
    response = apply(
        [update("components", "policy", {"responsibility": "Multiply quantity by ten; shared by purchase and quote."})],
        "Clarify shared policy",
    )
    assert response["diff"]["scenario_ids"] == ["business-A", "business-B"]
    full = cli(*prefix, "read")["model"]
    assert next(item for item in full["scenarios"] if item["id"] == "business-B") == b
    apply(
        [
            update(
                "components",
                "policy",
                {"name": "Pricing", "parent_id": "application", "binding_ids": ["bind-total", "bind-save"]},
            ),
            create("components", component("formatter", "bind-save", "application")),
        ],
        "Cross-directory members, split formatter, rename and reparent",
    )
    apply([delete("storage")], "Reject deletion with one omitted scenario reference", "DANGLING_REFERENCE")
    a["steps"][-1]["component_ids"] = ["formatter"]
    apply(
        [delete("storage"), update("scenarios", "business-A", {"steps": a["steps"]})],
        "Finish split with explicit reference repair",
    )
    a["steps"][-1]["component_ids"] = ["policy"]
    apply(
        [delete("formatter"), update("scenarios", "business-A", {"steps": a["steps"]})],
        "Merge formatter into policy without deleting steps",
    )
    apply([update("components", "application", {"parent_id": "policy"})], "Reject parent cycle", "PARENT_CYCLE")
    b["transitions"].append(
        {
            "source_id": "business-B-price",
            "target_id": "business-B-quote",
            "kind": "loop",
            "condition": "User requests another quote; hypothetical external repetition, not a source call",
        }
    )
    b["claim"]["issues"] = ["Fixture has no caller loop; this transition is a proposed interaction."]
    apply(
        [update("scenarios", "business-B", {"transitions": b["transitions"], "claim": b["claim"]})],
        "Save explicitly hypothetical business loop",
    )
    responses = race(model, output, revision)
    revision += 1
    after_race = cli(*prefix, "read")["model"]
    assert after_race["revision"] == revision
    winner = next(
        response["result"]["diff"]["changes"]["components"]["policy"]["after"]["name"]
        for response in responses
        if response["ok"]
    )
    assert next(item for item in after_race["components"] if item["id"] == "policy")["name"] == winner
    shutil.rmtree(fixture / "policies")
    apply(
        [
            update(
                "bindings",
                "bind-total",
                {"status": "missing", "reason": "Agent observed pricing.py deleted; historical location retained."},
            )
        ],
        "Keep missing source evidence",
    )
    reread = cli(*prefix, "read", "--scenario", "business-B")["model"]
    old = next(item for item in reread["bindings"] if item["id"] == "bind-total")
    assert old["status"] == "missing" and old["location"]["path"] == "policies/pricing.py"
    apply(
        [update("components", "policy", {"binding_ids": ["absent-binding"]})],
        "Reject internal missing binding",
        "DANGLING_REFERENCE",
    )
    report = {
        "status": "PASS",
        "final_revision": revision,
        "p0_symbols": 8,
        "p0_calls": 3,
        "p0_call_change_detected": True,
        "facts_did_not_modify_model": True,
        "race": responses,
        "stages": results,
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    write(output / "results.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("output", "node", "pyright", "tokei"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output.resolve(), args.node.resolve(), args.pyright.resolve(), args.tokei.resolve())
    print(json.dumps({key: value for key, value in report.items() if key not in ("stages", "race")}))


if __name__ == "__main__":
    main()
