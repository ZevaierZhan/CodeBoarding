import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from collections.abc import Callable

from filelock import FileLock, Timeout

from architecture_model.errors import ModelError
from architecture_model.maintenance_coverage import maintained_observations
from architecture_model.schema import Maintenance, Model, Patch, Project, Revision
from architecture_model.validation import COLLECTIONS, parse, validate_model

BINDING_EVIDENCE_FIELDS = ("snapshot_id", "source_version", "location")


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
    except (ValueError, UnicodeError) as error:
        raise ModelError("JSON_INVALID", str(path), str(error)) from error
    except OSError as error:
        raise ModelError("IO_ERROR", str(path), str(error)) from error


def atomic_write(path: Path, value: object) -> None:
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError) as error:
        raise ModelError("SAVE_FAILED", str(path), str(error)) from error
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def model_diff(before: Model, after: Model) -> dict:
    changes: dict[str, dict] = {}
    affected: set[str] = set()
    for collection in COLLECTIONS:
        old = {item.id: item.model_dump() for item in getattr(before, collection)}
        new = {item.id: item.model_dump() for item in getattr(after, collection)}
        changed = {
            identity: {"before": old.get(identity), "after": new.get(identity)}
            for identity in old.keys() | new.keys()
            if old.get(identity) != new.get(identity)
        }
        if changed:
            changes[collection] = changed
            affected.update(changed)
    component_ids = set(changes.get("components", {}))
    binding_ids = set(changes.get("bindings", {}))
    relation_ids = set(changes.get("relations", {}))
    maintenance_scenarios: set[str] = set()
    for change in changes.get("maintenance", {}).values():
        for item in (change["before"], change["after"]):
            if item is not None and item["disposition"] != "unchanged":
                component_ids.update(item["component_ids"])
                relation_ids.update(item["relation_ids"])
                maintenance_scenarios.update(item["scenario_ids"])
    for model in (before, after):
        for component in model.components:
            if binding_ids.intersection(component.binding_ids + component.claim.binding_ids):
                component_ids.add(component.id)
        for relation in model.relations:
            if relation.id in relation_ids or binding_ids.intersection(relation.claim.binding_ids):
                relation_ids.add(relation.id)
                component_ids.update((relation.source_id, relation.target_id))
    for model in (before, after):
        relation_ids.update(
            relation.id
            for relation in model.relations
            if component_ids.intersection((relation.source_id, relation.target_id))
        )
    scenarios = set(changes.get("scenarios", {})) | maintenance_scenarios
    record_targets: set[str] = set()
    for collection in ("opinions", "verifications"):
        for change in changes.get(collection, {}).values():
            for record in (change["before"], change["after"]):
                if record is not None:
                    record_targets.update(record["object_ids"])
    for model in (before, after):
        for scenario in model.scenarios:
            if (
                scenario.id in record_targets
                or binding_ids.intersection(scenario.claim.binding_ids)
                or any(
                    step.id in record_targets
                    or component_ids.intersection(step.component_ids)
                    or binding_ids.intersection(step.binding_ids + step.claim.binding_ids)
                    for step in scenario.steps
                )
            ):
                scenarios.add(scenario.id)
    return {
        "model_id": before.id,
        "revision": before.revision,
        "changes": changes,
        "object_ids": sorted(affected),
        "component_ids": sorted(component_ids),
        "relation_ids": sorted(relation_ids),
        "scenario_ids": sorted(scenarios),
    }


def candidate(current: Model, patch_value: object, maintenance: list[Maintenance] | None = None) -> tuple[Model, dict]:
    proposed, patch = patched_model(current, patch_value, maintenance)
    return revision_candidate(current, proposed, patch.author, patch.summary)


def patched_model(
    current: Model, patch_value: object, maintenance: list[Maintenance] | None = None
) -> tuple[Model, Patch]:
    patch = parse(Patch, patch_value)
    value = current.model_dump()
    if maintenance is not None:
        value["maintenance"] = [item.model_dump() for item in maintenance]
    reserved = {item.id for collection in COLLECTIONS for item in getattr(current, collection)}
    reserved.update(step.id for scenario in current.scenarios for step in scenario.steps)
    reserved.update((current.id, current.project.id))
    for index, operation in enumerate(patch.operations):
        location = f"/operations/{index}"
        items = value[operation.collection]
        existing = next((item for item in items if item["id"] == operation.id), None)
        if operation.collection == "facts" and operation.action != "create":
            raise ModelError("IMMUTABLE", location, "Fact snapshots are append-only")
        if "id" in operation.value and operation.value["id"] != operation.id:
            raise ModelError("IMMUTABLE", location, "Object ID cannot change")
        if operation.action == "create":
            if operation.id in reserved:
                raise ModelError("DUPLICATE_ID", location, "Create cannot overwrite an existing object")
            reserved.add(operation.id)
            items.append(operation.value | {"id": operation.id})
        else:
            if existing is None:
                raise ModelError("NOT_FOUND", location, "Update/delete requires an existing object")
            if operation.action == "update":
                existing.update(operation.value)
            else:
                if operation.value:
                    raise ModelError("SCHEMA_INVALID", location, "Delete value must be empty")
                items.remove(existing)
    return validate_model(value), patch


def revision_candidate(current: Model, proposed: Model, author: str, summary: str) -> tuple[Model, dict]:
    proposed.maintenance = maintained_observations(proposed, model_diff)
    previous_bindings = {binding.id: binding.model_dump() for binding in current.bindings}
    for binding in proposed.bindings:
        if binding.id in previous_bindings:
            _preserve_binding_history(previous_bindings[binding.id], binding.model_dump(), f"/bindings/{binding.id}")
    difference = model_diff(current, proposed)
    proposed.revision += 1
    proposed.revisions.append(
        parse(
            Revision,
            {
                "revision": proposed.revision,
                "author": author,
                "summary": summary,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "object_ids": difference["object_ids"],
                "scenario_ids": difference["scenario_ids"],
            },
        )
    )
    return validate_model(proposed.model_dump()), difference


class ModelStore:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.lock = FileLock(str(self.path) + ".lock", timeout=30)

    def initialize(self, project: object, author: str) -> Model:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock:
            if self.path.exists():
                raise ModelError("ALREADY_EXISTS", str(self.path), "Initialization never overwrites an existing file")
            model = Model(
                id=str(uuid4()),
                project=parse(Project, project),
                revisions=[
                    parse(
                        Revision,
                        {
                            "revision": 0,
                            "author": author,
                            "summary": "Initialize architecture model",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "object_ids": [],
                            "scenario_ids": [],
                        },
                    )
                ],
            )
            validate_model(model.model_dump())
            atomic_write(self.path, model.model_dump())
            return model

    def read(self) -> Model:
        return validate_model(load_json(self.path))

    def preview(self, patch: object) -> tuple[Model, dict]:
        return candidate(self.read(), patch)

    def apply(self, expected_revision: int, patch: object) -> dict:
        return self.commit(expected_revision, lambda current: candidate(current, patch))

    def commit(self, expected_revision: int, build: Callable[[Model], tuple[Model, dict]]) -> dict:
        try:
            with self.lock:
                current = self.read()
                if current.revision != expected_revision:
                    raise ModelError(
                        "REVISION_CONFLICT", "/revision", f"Expected {expected_revision}, found {current.revision}"
                    )
                proposed, difference = build(current)
                result = {"committed": True, "revision": proposed.revision, "diff": difference}
                atomic_write(self.path, proposed.model_dump())
                return result
        except Timeout as error:
            raise ModelError("LOCK_TIMEOUT", str(self.path), "Model lock timed out") from error

    def read_scope(self, component_id: str = "", scenario_id: str = "") -> dict:
        model = self.read()
        model.maintenance = maintained_observations(model, model_diff)
        value = model.model_dump()
        scope = {"component_id": component_id, "scenario_id": scenario_id}
        if not (component_id or scenario_id):
            return {"complete": True, "scope": scope, "model_id": model.id, "revision": model.revision, "model": value}
        components = {component_id} if component_id else set()
        scenarios = [scenario for scenario in model.scenarios if scenario.id == scenario_id]
        if scenario_id and not scenarios:
            raise ModelError("NOT_FOUND", "/scenarios", scenario_id)
        for scenario in scenarios:
            components.update(identity for step in scenario.steps for identity in step.component_ids)
        if component_id and component_id not in {component.id for component in model.components}:
            raise ModelError("NOT_FOUND", "/components", component_id)
        value["components"] = [item for item in value["components"] if item["id"] in components]
        value["scenarios"] = [item.model_dump() for item in scenarios]
        value["relations"] = [
            item for item in value["relations"] if item["source_id"] in components or item["target_id"] in components
        ]
        return {"complete": False, "scope": scope, "model_id": model.id, "revision": model.revision, "model": value}


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    value: dict = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _preserve_binding_history(old: dict, update: dict, location: str) -> None:
    if update.get("history", old["history"])[: len(old["history"])] != old["history"]:
        raise ModelError("HISTORY_REQUIRED", location, "Binding history is append-only")
    if any(key in update and update[key] != old[key] for key in BINDING_EVIDENCE_FIELDS):
        history = update.get("history", [])
        previous = {key: old[key] for key in BINDING_EVIDENCE_FIELDS}
        if not any(all(entry.get(key) == item for key, item in previous.items()) for entry in history):
            raise ModelError("HISTORY_REQUIRED", location, "Rebinding requires the previous version and location")
