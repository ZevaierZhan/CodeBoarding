"""Resolve verification evidence without promoting source coverage to execution proof."""

from architecture_model.errors import ModelError
from architecture_model.schema import Binding, HistoricalLocation, Model, Verification


def referenced_bindings(model: Model, object_ids: list[str]) -> set[str]:
    bindings = {binding.id for binding in model.bindings}
    objects = {
        item.id: item.model_dump()
        for collection in (model.components, model.relations, model.scenarios)
        for item in collection
    }
    objects.update({step.id: step.model_dump() for scenario in model.scenarios for step in scenario.steps})
    pending = list(object_ids)
    seen = set()
    evidence = set()
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        if identity in bindings:
            evidence.add(identity)
        elif identity in (model.id, model.project.id):
            evidence.update(bindings)
        elif identity in objects:
            item = objects[identity]
            pending.extend(item.get("binding_ids", []) + item.get("claim", {}).get("binding_ids", []))
            pending.extend(item.get("component_ids", []) + item.get("relation_ids", []))
            pending.extend(step["id"] for step in item.get("steps", []))
            pending.extend(item[key] for key in ("source_id", "target_id") if key in item)
            pending.extend(component.id for component in model.components if component.parent_id == identity)
    return evidence


def validate_verification(model: Model, record: Verification, require_scope: bool = False) -> None:
    facts = {snapshot.id: snapshot for snapshot in model.facts}
    bindings = {binding.id: binding for binding in model.bindings}
    relevant = referenced_bindings(model, record.object_ids)
    location = f"/verifications/{record.id}"
    if record.binding_snapshots:
        if not set(record.binding_snapshots).issubset(bindings):
            raise ModelError("VERIFICATION_SCOPE", location, "Verification scope references an unavailable binding")
        if require_scope and not set(record.binding_snapshots).issubset(relevant):
            raise ModelError("VERIFICATION_SCOPE", location, "Verification scope must belong to its target objects")
        versions = set()
        for binding_id, snapshot_id in record.binding_snapshots.items():
            binding = bindings[binding_id]
            snapshot = facts.get(snapshot_id)
            if snapshot is None:
                raise ModelError("VERIFICATION_SCOPE", location, "Verification snapshot is unavailable")
            catalog = snapshot.symbols | snapshot.file_locations
            entries: list[Binding | HistoricalLocation] = [binding, *binding.history]
            if not any(
                entry.snapshot_id == snapshot_id
                and entry.source_version == snapshot.source.digest
                and catalog.get(
                    f"{entry.location.path}|{entry.location.symbol}" if entry.location.symbol else entry.location.path
                )
                == entry.location
                for entry in entries
            ):
                raise ModelError(
                    "VERIFICATION_SCOPE", location, "Verification scope contradicts binding evidence/history"
                )
            versions.add(snapshot.source.digest)
        if record.source_version not in versions:
            raise ModelError(
                "VERIFICATION_SCOPE", location, "Verification legacy version anchor must occur in its declared scope"
            )
    else:
        for identity in set(record.object_ids).intersection(bindings):
            binding = bindings[identity]
            history: list[Binding | HistoricalLocation] = [binding, *binding.history]
            roots = {facts[entry.snapshot_id].source_root_id for entry in history if entry.snapshot_id in facts}
            if require_scope and not roots and any(snapshot.source_root_id for snapshot in model.facts):
                raise ModelError(
                    "VERIFICATION_SCOPE",
                    location,
                    "Verification root cannot be established from binding evidence/history",
                )
            if roots and not any(
                snapshot.source_root_id in roots and snapshot.source.digest == record.source_version
                for snapshot in model.facts
            ):
                raise ModelError("VERIFICATION_SCOPE", location, "Verification version belongs to another source root")
        if require_scope and any(
            facts[bindings[identity].snapshot_id].source_root_id
            for identity in relevant
            if identity not in record.object_ids and bindings[identity].snapshot_id in facts
        ):
            raise ModelError(
                "VERIFICATION_SCOPE",
                location,
                "Verification of v2 compound objects requires explicit binding_snapshots",
            )
    if not set(record.object_ids).intersection(bindings).issubset(record.binding_snapshots or record.object_ids):
        raise ModelError("VERIFICATION_SCOPE", location, "Verification scope must include directly targeted bindings")


def verification_scope(model: Model, record: Verification) -> dict:
    facts = {snapshot.id: snapshot for snapshot in model.facts}
    bindings = {binding.id: binding for binding in model.bindings}
    relevant = referenced_bindings(model, record.object_ids)
    declared = record.binding_snapshots
    implicit = {}
    if not declared:
        for identity in set(record.object_ids).intersection(bindings):
            binding = bindings[identity]
            root = facts.get(binding.snapshot_id)
            candidates = [
                snapshot
                for snapshot in model.facts
                if root
                and snapshot.source_root_id == root.source_root_id
                and snapshot.source.digest == record.source_version
            ]
            if len(candidates) == 1:
                implicit[identity] = candidates[0].id
    evidence = declared or implicit
    return {
        "scope_kind": (
            (
                "declared_historical"
                if set(declared) - relevant
                else "declared_referenced_evidence" if set(declared) == relevant else "declared_partial"
            )
            if declared
            else "implicit_direct_bindings" if implicit else "legacy_unscoped"
        ),
        "object_ids": record.object_ids,
        "uncovered_binding_ids": sorted(relevant - set(evidence)),
        "historical_binding_ids": sorted(set(declared) - relevant),
        "evidence": [
            {
                "binding_id": identity,
                "snapshot_id": snapshot_id,
                "source_root_id": facts[snapshot_id].source_root_id,
                "source_version": facts[snapshot_id].source.digest,
            }
            for identity, snapshot_id in sorted(evidence.items())
        ],
        "notice": "Source evidence scope only. Planned is not executed; partial or unscoped checks do not verify a whole contract/business. Source coverage is not runtime proof.",
    }
