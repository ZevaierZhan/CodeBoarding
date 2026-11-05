import gzip
import json
import re
from pathlib import Path

from architecture_model.validation import validate_model

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/design/architecture-model-m4-p2-evidence"


def test_large_separated_trial_preserves_every_existing_business_and_shared_object() -> None:
    before = validate_model(json.loads(gzip.decompress((EVIDENCE / "before.archive.json.gz").read_bytes())))
    after = validate_model(json.loads(gzip.decompress((EVIDENCE / "after.archive.json.gz").read_bytes())))
    assert before.id == after.id
    assert (before.revision, after.revision) == (2, 3)
    assert after.revisions[:-1] == before.revisions
    assert after.scenarios[:-1] == before.scenarios
    assert len(before.scenarios) == 129 and len(after.scenarios) == 130
    for collection in (
        "project",
        "facts",
        "bindings",
        "components",
        "relations",
        "opinions",
        "verifications",
        "maintenance",
    ):
        assert getattr(after, collection) == getattr(before, collection)
    scenario = after.scenarios[-1]
    used = {identity for step in scenario.steps for identity in step.component_ids}
    assert used == {"order-entry", "shared-pricing"}
    assert {identity for step in scenario.steps for identity in step.binding_ids} <= {
        binding.id for binding in before.bindings
    }


def test_separated_document_and_real_facts_match_the_final_persistent_revision() -> None:
    model = json.loads(gzip.decompress((EVIDENCE / "after.archive.json.gz").read_bytes()))
    html = gzip.decompress((EVIDENCE / "quotation-r3.html.gz").read_bytes()).decode("utf-8")
    match = re.search(r'<script type="application/json" id="model-data">(.*?)</script>', html, re.DOTALL)
    assert match
    payload = json.loads(match[1])
    assert payload["model"] == model
    assert payload["maintenance"]["revision"] == model["revision"]
    assert all(entry[0]["status"] == "verified" for entry in payload["snippets"].values())
    initial = json.loads((EVIDENCE / "facts-initial.json").read_text(encoding="utf-8"))
    fresh = json.loads((EVIDENCE / "facts-fresh.json").read_text(encoding="utf-8"))
    assert initial == fresh == model["facts"][0]
    assert len(fresh["source"]["files"]) == 4
    assert all("architecture_model" not in path for path in fresh["source"]["files"])


def test_trial_records_external_temporary_context_and_unchanged_target_environment() -> None:
    record = json.loads((EVIDENCE / "trial.json").read_text(encoding="utf-8"))
    assert record["persistent_model_bytes_before"] > 10 * record["original_m4_model_bytes"]
    assert record["capture_metadata"]["read-001"]["read.json"]["bytes"] > 2000 * 4096
    assert record["fresh_agent"]["fork_turns"] == "none"
    assert record["no_target_environment_configuration_before"]
    assert record["no_target_environment_configuration_after"]
    assert record["source_unchanged"]
    assert record["engine"] != record["target"]
    assert " " in record["target"] and " " in record["cache_root"]
    assert not (EVIDENCE / "read.json").exists() and not (EVIDENCE / "index.json").exists()
    journal = json.loads((EVIDENCE / "bounded-command-journal.json").read_text(encoding="utf-8"))
    assert journal and all(entry["exit"] == 0 for entry in journal)
    assert all(
        entry["cwd"].replace("\\", "/").casefold() == record["target"].replace("\\", "/").casefold()
        for entry in journal
    )
