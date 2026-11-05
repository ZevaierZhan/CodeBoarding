import hashlib
import json

from pydantic import ValidationError

from architecture_model.errors import ModelError
from architecture_model.schema import Facts, Model, Opinion, Strict, Verification

COLLECTIONS = ("facts", "bindings", "components", "relations", "scenarios", "opinions", "verifications", "maintenance")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def parse[T: Strict](schema: type[T], value: object) -> T:
    try:
        return schema.model_validate(value)
    except ValidationError as error:
        detail = error.errors()[0]
        code = "UNSUPPORTED_VERSION" if "schema_version" in detail["loc"] else "SCHEMA_INVALID"
        raise ModelError(code, "/" + "/".join(map(str, detail["loc"])), detail["msg"]) from error


def validate_facts(facts: Facts) -> None:
    body = facts.model_dump(exclude={"id"})
    if facts.id != digest(body) or facts.source.digest != digest(facts.source.files):
        raise ModelError("FACTS_MISMATCH", "/facts", "Snapshot or source manifest digest does not match")
    for key, location in facts.symbols.items():
        if (
            key != f"{location.path}|{location.symbol}"
            or facts.source.files.get(location.path) != location.content_hash
        ):
            raise ModelError("FACTS_MISMATCH", f"/facts/{facts.id}/symbols/{key}", "Symbol contradicts source manifest")
    for path, location in facts.file_locations.items():
        if (
            location.path != path
            or location.symbol
            or location.kind != "FILE"
            or location.start != 1
            or facts.source.files.get(path) != location.content_hash
        ):
            raise ModelError("FACTS_MISMATCH", f"/facts/{facts.id}/file_locations/{path}", "File contradicts manifest")
    names = (
        set(facts.symbols) if facts.schema_version == 2 else {location.symbol for location in facts.symbols.values()}
    )
    for call in facts.calls:
        if call.source not in names or call.target not in names:
            raise ModelError("DANGLING_REFERENCE", "/facts/calls", "Call endpoint absent from snapshot")
        if any(site.path not in facts.source.files for site in call.sites):
            raise ModelError("DANGLING_REFERENCE", "/facts/calls/sites", "Call site absent from manifest")


def validate_model(value: object) -> Model:
    model = parse(Model, value)
    objects: dict[str, object] = {model.id: model}
    _register(objects, model.project.id, "/project/id")
    for collection in COLLECTIONS:
        for item in getattr(model, collection):
            _register(objects, item.id, f"/{collection}/{item.id}")
    for scenario in model.scenarios:
        for step in scenario.steps:
            _register(objects, step.id, f"/scenarios/{scenario.id}/steps/{step.id}")
    facts = {item.id: item for item in model.facts}
    if model.maintenance_target_snapshot_id:
        _references([model.maintenance_target_snapshot_id], set(facts), "/maintenance_target_snapshot_id")
    for root_id, snapshot_id in model.maintenance_targets.items():
        if snapshot_id not in facts or facts[snapshot_id].source_root_id != root_id:
            raise ModelError("FACTS_MISMATCH", "/maintenance_targets", "Target belongs to another source root")
    for snapshot in model.facts:
        validate_facts(snapshot)
        if snapshot.project_id != model.project.id:
            raise ModelError("FACTS_MISMATCH", f"/facts/{snapshot.id}", "Project identity differs")
    bindings = {item.id for item in model.bindings}
    components = {item.id: item for item in model.components}
    for binding in model.bindings:
        if binding.status == "current":
            snapshot = facts.get(binding.snapshot_id)
            key = f"{binding.location.path}|{binding.location.symbol}"
            expected = (
                (
                    snapshot.symbols.get(key)
                    if binding.location.symbol
                    else snapshot.file_locations.get(binding.location.path)
                )
                if snapshot
                else None
            )
            if snapshot is None or snapshot.source.digest != binding.source_version or expected != binding.location:
                raise ModelError("BINDING_MISMATCH", f"/bindings/{binding.id}", "Current binding contradicts snapshot")
    for component in model.components:
        location = f"/components/{component.id}"
        _references(component.binding_ids, bindings, location + "/binding_ids")
        _references(component.claim.binding_ids, bindings, location + "/claim/binding_ids")
        seen = {component.id}
        parent = component.parent_id
        while parent:
            _references([parent], set(components), location + "/parent_id")
            if parent in seen:
                raise ModelError("PARENT_CYCLE", location + "/parent_id", "Component hierarchy must be acyclic")
            seen.add(parent)
            parent = components[parent].parent_id
    for relation in model.relations:
        location = f"/relations/{relation.id}"
        _references([relation.source_id, relation.target_id], set(components), location)
        _references(relation.claim.binding_ids, bindings, location + "/claim")
        if relation.contract:
            contract = relation.contract
            evidence = contract.caller_binding_ids + contract.receiver_binding_ids + contract.matching_binding_ids
            _references(evidence, bindings, location + "/contract")
            if not set(evidence).issubset(relation.claim.binding_ids):
                raise ModelError("CONTRACT_INVALID", location, "Contract evidence must be included in its claim")
            for component_id, side in (
                (relation.source_id, contract.caller_binding_ids),
                (relation.target_id, contract.receiver_binding_ids),
            ):
                component = components[component_id]
                if not set(side).issubset(component.binding_ids + component.claim.binding_ids):
                    raise ModelError("CONTRACT_INVALID", location, "Each endpoint must own its side of the evidence")
            if contract.status == "evidenced" and (
                not contract.matching_binding_ids or relation.claim.kind != "code_fact" or contract.uncertainties
            ):
                raise ModelError(
                    "CONTRACT_INVALID",
                    location,
                    "Evidenced contract requires explicit matching code evidence without unresolved uncertainty",
                )
            if contract.status != "evidenced" and not contract.uncertainties:
                raise ModelError("CONTRACT_INVALID", location, "Unconfirmed contract requires explicit uncertainty")
    for scenario in model.scenarios:
        location = f"/scenarios/{scenario.id}"
        steps = {step.id for step in scenario.steps}
        if len(scenario.order) != len(steps) or set(scenario.order) != steps:
            raise ModelError("STEP_ORDER", location + "/order", "Order must contain every step exactly once")
        _references([scenario.entry_step_id], steps, location + "/entry_step_id")
        _references(scenario.claim.binding_ids, bindings, location + "/claim")
        _references(scenario.relation_ids, {item.id for item in model.relations}, location + "/relation_ids")
        for step in scenario.steps:
            _references(step.component_ids, set(components), location + f"/steps/{step.id}/component_ids")
            _references(step.binding_ids + step.claim.binding_ids, bindings, location + f"/steps/{step.id}/bindings")
        for transition in scenario.transitions:
            _references([transition.source_id, transition.target_id], steps, location + "/transitions")
    records: list[Opinion | Verification] = [*model.opinions, *model.verifications]
    for record in records:
        _references(record.object_ids, set(objects), f"/records/{record.id}/object_ids")
    versions = {snapshot.source.digest for snapshot in model.facts}
    for verification in model.verifications:
        _references([verification.source_version], versions, f"/verifications/{verification.id}/source_version")
    for item in model.maintenance:
        location = f"/maintenance/{item.id}"
        _references([item.target_snapshot_id], set(facts), location)
        target = facts[item.target_snapshot_id]
        if item.target_source_version != target.source.digest or item.compared_revision > model.revision:
            raise ModelError("MAINTENANCE_INVALID", location, "Target version/revision contradicts model")
        for choice in item.candidates:
            expected = target.symbols.get(choice.key) or target.file_locations.get(choice.key)
            if choice.location != expected:
                raise ModelError("MAINTENANCE_INVALID", location, "Candidate contradicts target snapshot")
        if item.resolution and (
            item.resolution.source_version != item.target_source_version or item.disposition == "unchanged"
        ):
            raise ModelError("MAINTENANCE_INVALID", location, "Resolution must address a changed target version")
        if item.coverage_version:
            covered = set(item.component_ids + item.relation_ids + item.scenario_ids + item.step_ids)
            if set(item.object_versions) != covered:
                raise ModelError(
                    "MAINTENANCE_INVALID", location, "Coverage must fingerprint every affected interpretation"
                )
            if item.resolution and (
                set(item.resolution.object_ids) != covered or item.resolution.object_versions != item.object_versions
            ):
                raise ModelError(
                    "MAINTENANCE_INVALID", location, "Resolution must retain the reviewed interpretation state"
                )
    if [revision.revision for revision in model.revisions] != list(range(model.revision + 1)):
        raise ModelError("REVISION_INVALID", "/revisions", "Revision history must run from zero to current revision")
    return model


def _register(objects: dict, identity: str, location: str) -> None:
    if identity in objects:
        raise ModelError("DUPLICATE_ID", location, f"ID already exists: {identity}")
    objects[identity] = True


def _references(references: list[str], known: set[str], location: str) -> None:
    for reference in references:
        if reference not in known:
            raise ModelError("DANGLING_REFERENCE", location, f"Unknown ID: {reference}")
