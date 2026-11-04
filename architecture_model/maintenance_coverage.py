from collections.abc import Callable

from architecture_model.schema import Maintenance, Model
from architecture_model.validation import digest


def capture_coverage(model: Model, item: Maintenance, impact_of: Callable[[Model, Model], dict]) -> Maintenance:
    marked = model.model_copy(deep=True)
    binding = next(entry for entry in marked.bindings if entry.id == item.binding_id)
    binding.reason += " [maintenance impact]"
    impact = impact_of(model, marked)
    step_ids = [
        step.id
        for scenario in model.scenarios
        for step in scenario.steps
        if item.binding_id in step.binding_ids + step.claim.binding_ids
        or set(step.component_ids).intersection(impact["component_ids"])
    ]
    ids = set(impact["component_ids"] + impact["relation_ids"] + impact["scenario_ids"] + step_ids)
    objects = [
        entry.model_dump()
        for collection in (model.components, model.relations, model.scenarios)
        for entry in collection
    ]
    objects.extend(step.model_dump() for scenario in model.scenarios for step in scenario.steps)
    versions = {entry["id"]: digest(entry) for entry in objects if entry["id"] in ids}
    updated = item.model_copy(deep=True)
    updated.component_ids = impact["component_ids"]
    updated.relation_ids = impact["relation_ids"]
    updated.scenario_ids = impact["scenario_ids"]
    updated.step_ids = sorted(step_ids)
    updated.coverage_version = "objects-v1"
    updated.object_versions = versions
    updated.compared_revision = model.revision
    updated.resolution = None
    updated.id = "maintenance-" + digest({"comparison": comparison_key(item), "objects-v1": versions})
    return updated


def maintained_observations(model: Model, impact_of: Callable[[Model, Model], dict]) -> list[Maintenance]:
    observations = list(model.maintenance)
    existing = {item.id for item in observations}
    bindings = {item.id for item in model.bindings}
    comparisons = {comparison_key(item): item for item in observations if item.binding_id in bindings}
    for template in comparisons.values():
        current = capture_coverage(model, template, impact_of)
        if current.id not in existing:
            observations.append(current)
            existing.add(current.id)
    return observations


def comparison_key(item: Maintenance) -> str:
    return digest({"binding": item.binding_id, "basis": item.basis.model_dump(), "target": item.target_snapshot_id})
