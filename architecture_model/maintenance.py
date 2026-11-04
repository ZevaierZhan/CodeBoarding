import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from architecture_model.errors import ModelError
from architecture_model.maintenance_coverage import capture_coverage, comparison_key, maintained_observations
from architecture_model.schema import (
    Binding,
    Facts,
    HistoricalLocation,
    Maintenance,
    MaintenanceCandidate,
    MaintenanceResolution,
    Model,
    Strict,
    Text,
)
from architecture_model.store import (
    BINDING_EVIDENCE_FIELDS,
    ModelStore,
    candidate,
    model_diff,
    patched_model,
    revision_candidate,
)
from architecture_model.validation import digest, parse, validate_facts, validate_model


class ExtractionScope(Strict):
    protocol: Literal["python-file-v1"]
    complete: Literal[True]
    implementation: Text
    patterns: list[str]
    tools: list[Text]
    configuration: dict[str, Text]


class Review(Strict):
    author: Text
    reason: Text
    outcome: Literal["confirmed", "revised"]
    source_version: Text
    operations: list[dict] = Field(default_factory=list)


def preview(model: Model, target: Facts) -> dict:
    validate_facts(target)
    if target.project_id != model.project.id:
        raise ModelError("FACTS_MISMATCH", "/project", "Comparison project differs from model")
    maintained = maintained_observations(model, model_diff)
    saved = {item.id: item for item in maintained}
    observations = []
    for binding in model.bindings:
        observation = _compare(model, binding, target)
        observations.append(saved.get(observation.id, observation))
    body = {
        "model_id": model.id,
        "revision": model.revision,
        "project_id": model.project.id,
        "target_snapshot_id": target.id,
        "target_source_version": target.source.digest,
        "target_git_commit": target.source.git_commit,
        "granularity": "Exact containing-file bytes and incident static call endpoints; no function-body hash",
        "pending_ids": [
            item.id
            for item in {entry.id: entry for entry in [*maintained, *observations]}.values()
            if item.disposition != "unchanged" and item.resolution is None
        ],
        "observations": [item.model_dump() for item in observations],
    }
    return body | {"token": digest(body), "committed": False}


def refresh(store: ModelStore, target: Facts, expected_revision: int, token: str, author: str) -> dict:
    def build(current: Model) -> tuple[Model, dict]:
        report = preview(current, target)
        if report["token"] != token:
            raise ModelError("PREVIEW_CONFLICT", "/token", "Preview does not match this model and target")
        proposed = current.model_copy(deep=True)
        proposed.maintenance_target_snapshot_id = target.id
        if target.id not in {item.id for item in proposed.facts}:
            proposed.facts.append(target)
        existing = {item.id for item in proposed.maintenance}
        proposed.maintenance.extend(
            parse(Maintenance, value) for value in report["observations"] if value["id"] not in existing
        )
        return revision_candidate(current, validate_model(proposed.model_dump()), author, "Record source maintenance")

    return store.commit(expected_revision, build)


def rebind(store: ModelStore, item_id: str, key: str, expected_revision: int, author: str, reason: str) -> dict:
    def build(current: Model) -> tuple[Model, dict]:
        item = _item(current, item_id)
        choice = next((entry for entry in item.candidates if entry.key == key), None)
        if choice is None:
            raise ModelError("CANDIDATE_INVALID", "/candidate", "Select a candidate from this observation")
        binding = next((entry for entry in current.bindings if entry.id == item.binding_id), None)
        if binding is None:
            raise ModelError("NOT_FOUND", "/bindings", item.binding_id)
        history = [entry.model_dump() for entry in binding.history]
        target_evidence = {
            "snapshot_id": item.target_snapshot_id,
            "source_version": item.target_source_version,
            "location": choice.location.model_dump(),
        }
        previous = binding.model_dump()
        if any(previous[field] != target_evidence[field] for field in BINDING_EVIDENCE_FIELDS):
            history.append(
                parse(
                    HistoricalLocation,
                    {
                        "snapshot_id": binding.snapshot_id,
                        "source_version": binding.source_version,
                        "location": binding.location.model_dump(),
                        "reason": reason,
                    },
                ).model_dump()
            )
        return candidate(
            current,
            {
                "author": author,
                "summary": reason,
                "operations": [
                    {
                        "action": "update",
                        "collection": "bindings",
                        "id": binding.id,
                        "value": {
                            "snapshot_id": item.target_snapshot_id,
                            "source_version": item.target_source_version,
                            "location": choice.location.model_dump(),
                            "status": "current",
                            "reason": reason,
                            "history": history,
                        },
                    }
                ],
            },
        )

    return store.commit(expected_revision, build)


def resolve(store: ModelStore, item_id: str, review_value: object, expected_revision: int) -> dict:
    review = parse(Review, review_value)

    def build(current: Model) -> tuple[Model, dict]:
        item = _item(current, item_id)
        if item.disposition == "unchanged" or item.resolution is not None:
            raise ModelError("REVIEW_INVALID", "/maintenance", "Observation needs no review or is already resolved")
        if review.source_version != item.target_source_version:
            raise ModelError("REVIEW_INVALID", "/source_version", "Review must name the observation's target version")
        if any(
            operation.get("collection") not in ("components", "relations", "scenarios", "opinions", "verifications")
            for operation in review.operations
        ):
            raise ModelError("REVIEW_INVALID", "/operations", "Review operations must revise interpretations")
        maintenance = [entry.model_copy(deep=True) for entry in maintained_observations(current, model_diff)]
        object_ids = sorted(set(item.component_ids + item.relation_ids + item.scenario_ids + item.step_ids))
        if review.operations:
            if (
                item.binding_id not in {binding.id for binding in current.bindings}
                or item.id != capture_coverage(current, item, model_diff).id
            ):
                raise ModelError(
                    "REVIEW_INVALID", "/operations", "Interpretation edits require current review coverage"
                )
            proposed, _ = patched_model(
                current,
                {"author": review.author, "summary": review.reason, "operations": review.operations},
                maintenance,
            )
        else:
            proposed = current.model_copy(deep=True)
            proposed.maintenance = maintenance
        difference = model_diff(current, proposed)
        changed = {
            identity
            for collection in ("components", "relations", "scenarios")
            for identity in difference["changes"].get(collection, {})
        }
        if review.outcome == "revised" and not changed.intersection(object_ids):
            raise ModelError("REVIEW_INVALID", "/operations", "Revised requires a change to an affected interpretation")
        proposed.maintenance = maintained_observations(proposed, model_diff)
        reviewed_ids = {item.id}
        if review.operations:
            reviewed_ids.add(capture_coverage(proposed, item, model_diff).id)
        timestamp = datetime.now(timezone.utc).isoformat()
        for updated in proposed.maintenance:
            if updated.id in reviewed_ids and updated.resolution is None:
                updated.resolution = MaintenanceResolution(
                    outcome=review.outcome,
                    author=review.author,
                    reason=review.reason,
                    source_version=review.source_version,
                    timestamp=timestamp,
                    object_ids=sorted(
                        set(updated.component_ids + updated.relation_ids + updated.scenario_ids + updated.step_ids)
                    ),
                    object_versions=dict(updated.object_versions),
                )
        return revision_candidate(current, proposed, review.author, review.reason)

    return store.commit(expected_revision, build)


def query(model: Model, binding_id: str = "", component_id: str = "", scenario_id: str = "") -> dict:
    for identity, collection in (
        (binding_id, model.bindings),
        (component_id, model.components),
        (scenario_id, model.scenarios),
    ):
        if identity and identity not in {entry.id for entry in collection}:
            raise ModelError("NOT_FOUND", "/scope", identity)
    items = [
        item
        for item in maintained_observations(model, model_diff)
        if (not binding_id or item.binding_id == binding_id)
        and (not component_id or component_id in item.component_ids)
        and (not scenario_id or scenario_id in item.scenario_ids)
    ]
    bindings = {binding.id for binding in model.bindings}
    comparisons = {comparison_key(item): item for item in items if item.binding_id in bindings}
    current_ids = {capture_coverage(model, item, model_diff).id for item in comparisons.values()} & {
        item.id for item in items
    }
    return {
        "model_id": model.id,
        "revision": model.revision,
        "pending_ids": [item.id for item in items if item.disposition != "unchanged" and item.resolution is None],
        "current_coverage_ids": sorted(current_ids),
        "current_pending_ids": [
            item.id
            for item in items
            if item.id in current_ids and item.disposition != "unchanged" and item.resolution is None
        ],
        "latest_target_snapshot_id": model.maintenance_target_snapshot_id,
        "observations": [item.model_dump() for item in items],
    }


def _item(model: Model, identity: str) -> Maintenance:
    item = next((entry for entry in maintained_observations(model, model_diff) if entry.id == identity), None)
    if item is None:
        raise ModelError("NOT_FOUND", "/maintenance", identity)
    return item


def _scope(facts: Facts) -> ExtractionScope | None:
    value = facts.tools.get("maintenance_scope", "")
    if not value:
        return None
    try:
        return parse(ExtractionScope, json.loads(value))
    except (ValueError, ModelError) as error:
        raise ModelError("COMPARISON_INVALID", "/tools/maintenance_scope", "Invalid extraction descriptor") from error


def _compare(model: Model, binding: Binding, target: Facts) -> Maintenance:
    old = next((item for item in model.facts if item.id == binding.snapshot_id), None)
    basis = HistoricalLocation(
        snapshot_id=binding.snapshot_id,
        source_version=binding.source_version,
        location=binding.location,
        reason="Evidence at comparison time",
    )
    choices = _candidates(binding, target)
    old_names = (
        (
            {binding.location.symbol}
            if binding.location.symbol
            else {entry.symbol for entry in old.symbols.values() if entry.path == binding.location.path}
        )
        if old
        else set()
    )
    old_calls = [call for call in old.calls if old_names.intersection((call.source, call.target))] if old else []
    new_names = {choice.location.symbol for choice in choices if choice.location.symbol}
    if not binding.location.symbol:
        paths = {choice.location.path for choice in choices}
        new_names = {entry.symbol for entry in target.symbols.values() if entry.path in paths}
    new_calls = [call for call in target.calls if new_names.intersection((call.source, call.target))]
    disposition: Literal["unchanged", "changed", "missing", "ambiguous", "indeterminate"]
    reasons = []
    old_scope = _scope(old) if old else None
    target_scope = _scope(target)
    key = f"{binding.location.path}|{binding.location.symbol}" if binding.location.symbol else binding.location.path
    exact = next((choice for choice in choices if choice.key == key), None)
    original = (old.symbols.get(key) if binding.location.symbol else old.file_locations.get(key)) if old else None
    if old is None or old.source.digest != binding.source_version or original != binding.location:
        disposition = "indeterminate"
        reasons.append("Original evidence catalog is unavailable or contradicts binding version")
    elif old.id == target.id:
        disposition = "unchanged"
        reasons.append("Same immutable snapshot and evidence")
    elif old_scope is None or old_scope != target_scope:
        disposition = "indeterminate"
        reasons.append("Extraction scope/configuration evidence absent or different; absence cannot establish deletion")
    elif exact:
        before_edges = {(call.source, call.target) for call in old_calls}
        after_edges = {(call.source, call.target) for call in new_calls}
        changed = binding.location.content_hash != exact.location.content_hash or before_edges != after_edges
        disposition = "changed" if changed else "unchanged"
        reasons.append(
            "Containing-file bytes or incident call endpoints changed"
            if changed
            else "File bytes and incident call endpoints unchanged"
        )
        if binding.location != exact.location:
            reasons.append("Location metadata changed; content judgement uses whole-file bytes")
    elif choices:
        disposition = "ambiguous" if len(choices) > 1 else "changed"
        reasons.append("Original location absent; candidate adoption requires explicit Agent selection")
    else:
        disposition = "missing"
        reasons.append(
            "Original location absent from complete export under matching extraction rules; no plausible candidate"
        )
    identity = digest({"binding": binding.id, "basis": basis.model_dump(), "target": target.id})
    observation = Maintenance(
        id=f"maintenance-{identity}",
        binding_id=binding.id,
        basis=basis,
        target_snapshot_id=target.id,
        target_source_version=target.source.digest,
        compared_revision=model.revision,
        disposition=disposition,
        reasons=reasons,
        candidates=choices,
        component_ids=[],
        relation_ids=[],
        scenario_ids=[],
        step_ids=[],
        call_changes={"before": old_calls, "after": new_calls},
    )
    return capture_coverage(model, observation, model_diff)


def _candidates(binding: Binding, target: Facts) -> list[MaintenanceCandidate]:
    location = binding.location
    catalog = target.symbols if location.symbol else target.file_locations
    key = f"{location.path}|{location.symbol}" if location.symbol else location.path
    if key in catalog:
        return [MaintenanceCandidate(key=key, location=catalog[key], reasons=["Exact path and symbol identity"])]
    choices = []
    for candidate_key, candidate_location in sorted(catalog.items()):
        if candidate_location.kind != location.kind:
            continue
        reasons = []
        if candidate_location.content_hash == location.content_hash:
            reasons.append("Identical containing-file bytes at another location")
        if location.symbol and candidate_location.symbol.rsplit(".", 1)[-1] == location.symbol.rsplit(".", 1)[-1]:
            reasons.append("Same terminal symbol name and kind")
        if location.symbol and candidate_location.path == location.path:
            reasons.append("Same file and symbol kind; possible rename, requires source inspection")
        if reasons:
            choices.append(MaintenanceCandidate(key=candidate_key, location=candidate_location, reasons=reasons))
    return choices
