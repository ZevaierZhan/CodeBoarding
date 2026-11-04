"""Replay M3 with real source exports, shared IDs and independent CLI processes."""

import argparse
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from examples.architecture_model.demo import ROOT, claim, cli, component, materialize, scenario, write


def run(output: Path, node: Path, pyright: Path, tokei: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    materialize(ROOT / "examples/architecture_model/fixture", source)
    model = output / "architecture-model.json"
    prefix = ("model", "--file", str(model))
    tools = ("--node", str(node), "--pyright", str(pyright), "--tokei", str(tokei))
    project = write(
        output / "project.json",
        {
            "id": "orders",
            "name": "Orders · shared architecture",
            "boundary": "Purchase and quotation; save formats an ID, with no database or server execution.",
        },
    )
    cli(*prefix, "init", "--project", str(project), "--author", "business-agent")
    stages = []
    fact_runs: dict[str, dict] = {}

    def read() -> dict:
        return cli(*prefix, "read")["model"]

    def apply(label: str, operations: list[dict]) -> None:
        revision = read()["revision"]
        patch = write(
            output / f"patch-{label}.json", {"author": "business-agent", "summary": label, "operations": operations}
        )
        cli(*prefix, "apply", "--patch", str(patch), "--expected-revision", str(revision))

    def export_facts(label: str) -> tuple[Path, dict]:
        path = output / f"facts-{label}.json"
        arguments = ["facts", "export", "--repo", str(source), "--project-id", "orders", "--output", str(path), *tools]
        response = cli(*arguments)
        fact_runs[label] = {
            "command": json.dumps([sys.executable, "-m", "architecture_model", *arguments]),
            "environment": f"Python {platform.python_version()} / {platform.platform()}",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "result": response,
        }
        import_value = json.loads(path.read_text(encoding="utf-8"))
        return path, import_value

    def document(label: str) -> None:
        before = model.read_bytes()
        response = cli(*prefix, "export-html", "--output", str(output / f"{label}.html"), "--source-root", str(source))
        assert model.read_bytes() == before
        stages.append(
            {
                "stage": label,
                "export": response,
                "maintenance": cli(*prefix, "maintenance"),
                "model_sha256": hashlib.sha256(before).hexdigest(),
            }
        )
        (output / f"model-{label}.json").write_bytes(before)

    def create(collection: str, value: dict) -> dict:
        return {"action": "create", "collection": collection, "id": value["id"], "value": value}

    _, facts = export_facts("s0")
    bindings = [
        {
            "id": f"bind-{location['symbol'].rsplit('.', 1)[-1]}",
            "snapshot_id": facts["id"],
            "source_version": facts["source"]["digest"],
            "location": location,
            "status": "current",
        }
        for location in facts["symbols"].values()
    ]
    purchase = scenario(
        "business-A",
        [
            ("validate", "entry", "bind-buy"),
            ("price", "policy", "bind-total"),
            ("save", "storage", "bind-save"),
            ("reject", "entry", "bind-buy"),
            ("abandon", "entry", "bind-buy"),
        ],
    )
    purchase["name"] = "A · Purchase and validation"
    purchase["steps"][0]["claim"] = claim(
        "bind-buy",
        "buy rejects quantity <= 0 before total and save. Branch conditions describe that code; the player does not evaluate quantity.",
    )
    purchase["steps"][3]["claim"] = claim(
        "bind-buy",
        "ValueError ends this invocation. A user may retry in a new invocation; the retry loop is a demonstration hypothesis, not an internal loop.",
    )
    purchase["steps"][3]["claim"]["kind"] = "intent_hypothesis"
    purchase["steps"][3]["claim"]["issues"] = ["No caller retry or cancel implementation exists in this fixture."]
    purchase["steps"][4]["claim"] = claim(
        "bind-buy", "Abandoning after rejection is a modeled caller intention; no cancellation handler is implemented."
    )
    purchase["steps"][4]["claim"]["kind"] = "intent_hypothesis"
    purchase["order"] = [
        "business-A-save",
        "business-A-validate",
        "business-A-reject",
        "business-A-price",
        "business-A-abandon",
    ]
    purchase["transitions"] = [
        {
            "source_id": "business-A-validate",
            "target_id": "business-A-price",
            "kind": "branch",
            "condition": "quantity > 0; described guard, not evaluated",
        },
        {
            "source_id": "business-A-validate",
            "target_id": "business-A-reject",
            "kind": "branch",
            "condition": "quantity <= 0; ValueError before pricing",
        },
        {
            "source_id": "business-A-price",
            "target_id": "business-A-save",
            "kind": "next",
            "condition": "total returns normally to buy",
        },
        {
            "source_id": "business-A-reject",
            "target_id": "business-A-validate",
            "kind": "loop",
            "condition": "Hypothetical caller retries with a new invocation; no retry implementation",
        },
        {
            "source_id": "business-A-reject",
            "target_id": "business-A-abandon",
            "kind": "return",
            "condition": "Hypothetical caller abandons after rejection; no cancellation handler",
        },
    ]
    apply(
        "establish-purchase",
        [
            create("facts", facts),
            *[create("bindings", b) for b in bindings],
            *[
                create("components", component(identity, binding, parent))
                for identity, binding, parent in [
                    ("application", "bind-start", ""),
                    ("entry", "bind-buy", "application"),
                    ("policy", "bind-total", "application"),
                    ("storage", "bind-save", "application"),
                ]
            ],
            create(
                "relations",
                {
                    "id": "entry-pricing",
                    "source_id": "entry",
                    "target_id": "policy",
                    "meaning": "Purchase and quotation call shared pricing",
                    "claim": claim("bind-buy", "buy invokes total before save; quote invokes the same total."),
                },
            ),
            create(
                "relations",
                {
                    "id": "entry-storage",
                    "source_id": "entry",
                    "target_id": "storage",
                    "meaning": "Purchase formats the order after pricing",
                    "claim": claim("bind-buy", "buy passes total's result to save."),
                },
            ),
            create("scenarios", purchase),
            create(
                "verifications",
                {
                    "id": "planned-purchase",
                    "status": "planned",
                    "object_ids": ["business-A"],
                    "command": 'python -c "from delivery.orders import buy; assert buy(2)"',
                    "environment": "Fixture Python; proposed, not executed",
                    "inputs": "quantity=2; business assertion remains planned",
                    "source_version": facts["source"]["digest"],
                },
            ),
            create(
                "verifications",
                {
                    "id": "executed-export",
                    "status": "executed",
                    "object_ids": ["application"],
                    "command": fact_runs["s0"]["command"],
                    "environment": fact_runs["s0"]["environment"],
                    "inputs": "Complete fixture source tree, static export only; no business invocation",
                    "source_version": facts["source"]["digest"],
                    "executor": "viewer_demo",
                    "executed_at": fact_runs["s0"]["executed_at"],
                    "exit_code": 0,
                    "result": "Native fact export completed. Does not verify business explanations or hypothetical retry.",
                },
            ),
        ],
    )
    document("01-purchase")
    original = read()
    quotation = scenario("business-B", [("quote", "entry", "bind-quote"), ("price", "policy", "bind-total")])
    quotation["name"] = "B · Quotation"
    apply("add-quotation-reusing-policy", [create("scenarios", quotation)])
    shared = read()
    assert shared["components"] == original["components"] and shared["scenarios"][0] == original["scenarios"][0]
    document("02-shared-businesses")
    pricing = source / "policies/pricing.py"
    pricing.write_text(pricing.read_text().replace("* 10", "* 12"), encoding="utf-8")
    target_path, _ = export_facts("s1")
    preview = cli(*prefix, "maintenance-preview", "--facts", str(target_path))
    cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(target_path),
        "--token",
        preview["token"],
        "--author",
        "business-agent",
        "--expected-revision",
        str(read()["revision"]),
    )
    pending = cli(*prefix, "maintenance", "--binding", "bind-total")
    item = next(o for o in pending["observations"] if o["id"] in pending["current_pending_ids"])
    assert item["scenario_ids"] == ["business-A", "business-B"]
    document("03-source-pending")
    historical_pending_id = item["id"]
    apply(
        "clarify-shared-boundary",
        [
            {
                "action": "update",
                "collection": "components",
                "id": "policy",
                "value": {
                    "rationale": "Both buy and quote call total; share this pricing responsibility while keeping entry and formatting separate."
                },
            }
        ],
    )
    pending = cli(*prefix, "maintenance", "--binding", "bind-total")
    item = next(o for o in pending["observations"] if o["id"] in pending["current_pending_ids"])
    assert item["id"] != historical_pending_id and historical_pending_id in pending["pending_ids"]
    cli(
        *prefix,
        "maintenance-rebind",
        "--item",
        item["id"],
        "--candidate",
        "policies/pricing.py|policies.pricing.total",
        "--author",
        "business-agent",
        "--reason",
        "Inspected multiplier 12; same pricing responsibility",
        "--expected-revision",
        str(read()["revision"]),
    )
    review = write(
        output / "review.json",
        {
            "author": "business-agent",
            "reason": "Inspected new multiplier and both consumers. Boundaries and explicit flow still hold; no runtime correctness claim.",
            "outcome": "confirmed",
            "source_version": item["target_source_version"],
        },
    )
    cli(
        *prefix,
        "maintenance-resolve",
        "--item",
        item["id"],
        "--review",
        str(review),
        "--expected-revision",
        str(read()["revision"]),
    )
    apply(
        "record-session-feedback",
        [
            create(
                "opinions",
                {
                    "id": "feedback-pricing",
                    "author": "example-user",
                    "stance": "question",
                    "text": "Please explain why pricing is shared. Agent reply: both buy and quote import total; responsibility remains an interpretation.",
                    "object_ids": ["policy", item["id"]],
                },
            )
        ],
    )
    (source / "unrelated.py").write_text(
        "def memo():\n    return 'unrelated to purchase and quotation'\n", encoding="utf-8"
    )
    latest_path, _ = export_facts("s2")
    latest_preview = cli(*prefix, "maintenance-preview", "--facts", str(latest_path))
    cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(latest_path),
        "--token",
        latest_preview["token"],
        "--author",
        "business-agent",
        "--expected-revision",
        str(read()["revision"]),
    )
    final_review = cli(*prefix, "maintenance", "--binding", "bind-total")
    assert historical_pending_id in final_review["pending_ids"]
    assert historical_pending_id not in final_review["current_coverage_ids"]
    assert item["id"] in final_review["current_coverage_ids"] and item["id"] not in final_review["current_pending_ids"]
    assert item["target_snapshot_id"] != final_review["latest_target_snapshot_id"]
    document("04-reviewed")
    final = read()
    assert len(final["components"]) == 4 and len(final["scenarios"]) == 2
    assert final["bindings"] != original["bindings"] and final["bindings"][0]["id"] == original["bindings"][0]["id"]
    result = {"revision": final["revision"], "model": str(model), "stages": stages, "fact_exports": fact_runs}
    write(output / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("output", "node", "pyright", "tokei"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.node.resolve(), args.pyright.resolve(), args.tokei.resolve())


if __name__ == "__main__":
    main()
