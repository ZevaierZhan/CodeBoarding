"""Replay source maintenance with real exports and independent CLI processes."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from examples.architecture_model.demo import ROOT, cli, component, materialize, scenario, write


def run(output: Path, node: Path, pyright: Path, tokei: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    source = output / "source"
    materialize(ROOT / "examples/architecture_model/fixture", source)
    model = output / "architecture-model.json"
    prefix = ("model", "--file", str(model))
    project = write(
        output / "project.json", {"id": "orders", "name": "Orders", "boundary": "Local purchase and quotation"}
    )
    cli(*prefix, "init", "--project", str(project), "--author", "business-agent")
    tools = ("--node", str(node), "--pyright", str(pyright), "--tokei", str(tokei))
    stages: list[dict] = []

    def export(label: str, success: bool = True) -> tuple[Path, dict]:
        before = model.read_bytes()
        path = output / f"facts-{label}.json"
        response = cli(
            "facts",
            "export",
            "--repo",
            str(source),
            "--project-id",
            "orders",
            "--output",
            str(path),
            *tools,
            success=success,
        )
        assert model.read_bytes() == before
        if not success:
            assert response["code"] == "FACTS_FAILED" and not path.exists()
            stages.append({"stage": label, "error": response})
            return path, response
        return path, json.loads(path.read_text(encoding="utf-8"))

    def read() -> dict:
        return cli(*prefix, "read")["model"]

    def refresh(label: str, facts_path: Path) -> dict:
        before = model.read_bytes()
        report = cli(*prefix, "maintenance-preview", "--facts", str(facts_path))
        assert model.read_bytes() == before
        response = cli(
            *prefix,
            "maintenance-refresh",
            "--facts",
            str(facts_path),
            "--token",
            report["token"],
            "--expected-revision",
            str(report["revision"]),
            "--author",
            "business-agent",
        )
        stages.append({"stage": label, "preview": report, "commit": response})
        return {entry["binding_id"]: entry for entry in report["observations"]}

    def rebind(item: dict, suffix: str) -> None:
        selected = [choice for choice in item["candidates"] if choice["key"].endswith(suffix)]
        assert len(selected) == 1, selected
        before = read()
        cli(
            *prefix,
            "maintenance-rebind",
            "--item",
            item["id"],
            "--candidate",
            selected[0]["key"],
            "--expected-revision",
            str(before["revision"]),
            "--author",
            "business-agent",
            "--reason",
            "Inspected new source and explicit candidate",
        )
        after = read()
        binding = next(entry for entry in after["bindings"] if entry["id"] == "bind-total")
        assert binding["id"] == "bind-total" and binding["history"]
        assert item["id"] in cli(*prefix, "maintenance", "--binding", "bind-total")["pending_ids"]
        assert after["components"] == before["components"] and after["scenarios"] == before["scenarios"]

    initial_path, initial = export("s0")
    create = lambda collection, value: {"action": "create", "collection": collection, "id": value["id"], "value": value}
    bindings = [
        {
            "id": f"bind-{location['symbol'].rsplit('.', 1)[-1]}",
            "snapshot_id": initial["id"],
            "source_version": initial["source"]["digest"],
            "location": location,
            "status": "current",
        }
        for location in initial["symbols"].values()
    ]
    patch = write(
        output / "initial.json",
        {
            "author": "business-agent",
            "summary": "Startup, A and B share pricing",
            "operations": [
                create("facts", initial),
                *[create("bindings", entry) for entry in bindings],
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
                create(
                    "scenarios",
                    scenario("business-A", [("buy", "entry", "bind-buy"), ("price", "policy", "bind-total")]),
                ),
                create(
                    "scenarios",
                    scenario("business-B", [("quote", "entry", "bind-quote"), ("price", "policy", "bind-total")]),
                ),
            ],
        },
    )
    cli(*prefix, "apply", "--patch", str(patch), "--expected-revision", "0")
    baseline = read()
    repeat_path, repeat = export("repeat")
    assert initial == repeat
    refresh("initial refresh", initial_path)
    first_count = len(read()["maintenance"])
    refresh("same snapshot refresh", repeat_path)
    assert len(read()["maintenance"]) == first_count
    assert not cli(*prefix, "maintenance")["pending_ids"]
    pricing = source / "policies/pricing.py"
    pricing.write_text(pricing.read_text().replace("* 10", "* 12"))
    s1_path, _ = export("s1")
    s1 = refresh("shared implementation", s1_path)["bind-total"]
    assert s1["disposition"] == "changed" and s1["scenario_ids"] == ["business-A", "business-B"]
    assert read()["components"] == baseline["components"] and read()["scenarios"] == baseline["scenarios"]
    (source / "unrelated.py").write_text("def memo():\n    return 'unrelated'\n")
    s2_path, _ = export("s2")
    s2_items = refresh("unrelated source with pending shared change", s2_path)
    assert all(entry["disposition"] == "unchanged" for key, entry in s2_items.items() if key != "bind-total")
    assert s1["id"] in cli(*prefix, "maintenance", "--scenario", "business-A")["pending_ids"]
    pricing.write_text("\n\n" + pricing.read_text() + "\n\ndef auxiliary():\n    return 7\n")
    s3_path, _ = export("s3")
    s3 = refresh("line insertion and same-file function addition", s3_path)["bind-total"]
    assert (
        s3["disposition"] == "changed" and s3["candidates"][0]["location"]["start"] > s1["basis"]["location"]["start"]
    )
    rebind(s3, "|policies.pricing.total")
    pricing.write_text(pricing.read_text().replace("return 7", "return 9"))
    same_file_path, _ = export("same-file")
    same_file = refresh("only another function changes in the same file", same_file_path)["bind-total"]
    assert same_file["disposition"] == "changed"
    assert same_file["basis"]["location"]["start"] == same_file["candidates"][0]["location"]["start"]
    pending = cli(*prefix, "maintenance", "--binding", "bind-total")
    index = 0
    while pending["pending_ids"]:
        item = next(entry for entry in pending["observations"] if entry["id"] in pending["pending_ids"])
        review = {
            "author": "business-agent",
            "reason": "Inspected this target: A/B still share quantity pricing; rate is twelve",
            "outcome": "revised" if index == 0 else "confirmed",
            "source_version": item["target_source_version"],
        }
        if index == 0:
            review["operations"] = [
                {
                    "action": "update",
                    "collection": "components",
                    "id": "policy",
                    "value": {"responsibility": "Multiply quantity by twelve for purchase and quotation."},
                }
            ]
        path = write(output / f"review-{index}.json", review)
        cli(
            *prefix,
            "maintenance-resolve",
            "--item",
            item["id"],
            "--review",
            str(path),
            "--expected-revision",
            str(read()["revision"]),
        )
        index += 1
        pending = cli(*prefix, "maintenance", "--binding", "bind-total")
    assert not cli(*prefix, "maintenance", "--binding", "bind-total")["pending_ids"]
    refresh("resolved target repeat", s3_path)
    assert not cli(*prefix, "maintenance", "--binding", "bind-total")["pending_ids"]
    orders = source / "delivery/orders.py"
    moved = source / "policies/rates.py"
    pricing.rename(moved)
    orders.write_text(orders.read_text().replace("policies.pricing", "policies.rates"))
    move_path, _ = export("move")
    move = refresh("file move", move_path)["bind-total"]
    assert move["candidates"]
    rebind(move, "|policies.rates.total")
    moved.write_text(moved.read_text().replace("def total(", "def calculate("))
    orders.write_text(
        orders.read_text().replace("import total", "import calculate").replace("total(quantity)", "calculate(quantity)")
    )
    rename_path, _ = export("rename")
    rename = refresh("symbol rename", rename_path)["bind-total"]
    rebind(rename, "|policies.rates.calculate")
    for name in ("rates2.py", "rates3.py"):
        shutil.copyfile(moved, moved.with_name(name))
    moved.unlink()
    orders.write_text(orders.read_text().replace("policies.rates", "policies.rates2"))
    ambiguous_path, _ = export("ambiguous")
    ambiguous = refresh("multiple replacements", ambiguous_path)["bind-total"]
    assert ambiguous["disposition"] == "ambiguous" and len(ambiguous["candidates"]) >= 2
    rebind(ambiguous, "|policies.rates3.calculate")
    (source / "policies/rates2.py").unlink()
    (source / "policies/rates3.py").unlink()
    orders.write_text(
        orders.read_text().replace(
            "from policies.rates2 import calculate", "def calculate(quantity):\n    return quantity * 12"
        )
    )
    # Remove alternate source entirely so missing has no same-name replacement.
    orders.write_text(
        orders.read_text()
        .replace("def calculate(quantity):\n    return quantity * 12", "RATE = 12")
        .replace("calculate(quantity)", "quantity * RATE")
    )
    deleted_path, _ = export("deleted")
    missing = refresh("source deleted", deleted_path)["bind-total"]
    assert missing["disposition"] == "missing" and missing["basis"]["location"]["path"] == "policies/rates3.py"
    assert cli(*prefix, "read", "--scenario", "business-B")["model"]["scenarios"]
    scoped_before = model.read_bytes()
    (source / ".gitignore").write_text("delivery/\n")
    scope_path, scope_facts = export("scope")
    assert "delivery/orders.py" not in scope_facts["source"]["files"]
    scoped = cli(*prefix, "maintenance-preview", "--facts", str(scope_path))
    assert all(item["disposition"] == "indeterminate" for item in scoped["observations"])
    assert model.read_bytes() == scoped_before
    stages.append({"stage": "scope uncertainty", "preview": scoped})
    (source / ".gitignore").unlink()
    (source / "broken.py").write_text("def broken(:\n")
    export("failed", success=False)
    (source / "broken.py").unlink()
    rebuilt_path, rebuilt = export("rebuilt")
    assert rebuilt["id"] == json.loads(deleted_path.read_text())["id"]
    saved = read()
    report = cli(*prefix, "maintenance-preview", "--facts", str(rebuilt_path))
    refresh("full rebuild", rebuilt_path)
    assert read()["components"] == saved["components"] and read()["scenarios"] == saved["scenarios"]
    before_conflict = model.read_bytes()
    conflict = cli(
        *prefix,
        "maintenance-refresh",
        "--facts",
        str(rebuilt_path),
        "--token",
        report["token"],
        "--expected-revision",
        str(report["revision"]),
        "--author",
        "business-agent",
        success=False,
    )
    assert conflict["code"] == "REVISION_CONFLICT" and model.read_bytes() == before_conflict
    stages.append({"stage": "stale preview", "error": conflict})
    final = read()
    assert {entry["id"] for entry in final["bindings"]} == {entry["id"] for entry in baseline["bindings"]}
    assert final["scenarios"] == baseline["scenarios"]
    assert any(item["resolution"] for item in final["maintenance"])
    result = {
        "status": "PASS",
        "final_revision": final["revision"],
        "stages": stages,
        "pending_ids": cli(*prefix, "maintenance")["pending_ids"],
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
    }
    write(output / "results.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("output", "node", "pyright", "tokei"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.node.resolve(), args.pyright.resolve(), args.tokei.resolve())
    print(json.dumps({key: value for key, value in result.items() if key != "stages"}))


if __name__ == "__main__":
    main()
