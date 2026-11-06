"""Derive reviewable cross-root work without acquiring write credentials."""

import logging
import os
from pathlib import Path

from architecture_model.coverage import coverage_report
from architecture_model.errors import ModelError
from architecture_model.file_inventory import DEFAULT_EXCLUDES, MAX_ENTRIES, file_digest, safe_file
from architecture_model.maintenance import preview, query, root_targets
from architecture_model.schema import Facts, Model
from architecture_model.store import load_json
from architecture_model.validation import digest, parse, validate_facts
from architecture_model.verification import referenced_bindings, verification_scope

PROTOCOL = "cross-root-maintenance-plan-v1"
LIMITS = [
    "Independent roots retain independent extraction scopes and maintenance transactions.",
    "Ready permits inspection of prerequisites, not execution or user approval.",
    "Completed describes a recorded maintenance action only; it is not runtime or interpretation proof.",
    "Any changed revision requires replanning; obtain a new preview token immediately before refresh.",
    "Checks are advisory and cannot prevent callers from invoking the existing CLI directly.",
    "No cross-root atomic commit, automatic rebind, contract promotion or verification update is provided.",
    "Workspace manifests cover saved file bytes; directory metadata detects additions, not extraction completeness.",
]


def generate_plan(
    model: Model, source_map: Path | None, facts_paths: list[Path], roots: list[str], model_path: Path | None = None
) -> dict:
    inputs = {
        "source_map": str(source_map.absolute()) if source_map else "",
        "facts": [str(path.absolute()) for path in facts_paths],
        "roots": sorted(set(roots)),
        "model_path": str(model_path.absolute()) if model_path else "",
    }
    mapping, targets, external, input_issues = _inputs(inputs)
    catalog = {snapshot.id: snapshot for snapshot in model.facts}
    known_roots = {snapshot.source_root_id for snapshot in model.facts}
    for target in targets:
        validate_facts(target)
        if target.project_id != model.project.id or target.source_root_id not in known_roots:
            raise ModelError(
                "FACTS_MISMATCH", "/facts", "Proposed facts must belong to this project and an existing root"
            )
        if target.id in catalog and catalog[target.id] != target:
            raise ModelError("FACTS_MISMATCH", "/facts", "Immutable snapshot identity contradicts stored facts")
        catalog[target.id] = target
    if set(mapping) - known_roots or set(roots) - known_roots:
        raise ModelError("USAGE_ERROR", "/root", "Unknown mapping or selected root")
    workspace, usable, source_issues = _workspace(mapping)
    issues = input_issues + source_issues
    maintenance = query(model)
    try:
        coverage = coverage_report(model, usable, [], targets, [], maintenance)
    except (OSError, ModelError) as error:
        logging.exception("Plan source coverage could not establish physical identity")
        issues.append({"code": "source_observation_failed", "detail": str(error)})
        coverage = coverage_report(model, {}, [], targets, [], maintenance)
    pending = set(maintenance["pending_ids"])
    latest = set(maintenance.get("latest_observation_ids", [item["id"] for item in maintenance["observations"]]))
    current = set(maintenance["current_coverage_ids"]) & latest
    affected = {
        identity for row in coverage["files"] if row["workspace_content"] != "same" for identity in row["binding_ids"]
    }
    affected.update(
        identity
        for overlap in coverage["overlaps"]
        if overlap["saved_content"] == "different_versions"
        for identity in overlap["binding_ids"]
    )
    affected.update(item["binding_id"] for item in maintenance["observations"] if item["id"] in pending)
    items: list[dict] = []
    observations = []
    for row in coverage["roots"]:
        root = row["source_root_id"]
        selected = catalog.get(row["selected_snapshot_id"])
        basis = {
            "snapshot_id": row["selected_snapshot_id"],
            "source_digest": row["selected_source_version"],
            "extraction": row["extraction"],
        }
        root_files = [entry for entry in coverage["files"] if entry["source_root_id"] == root]
        blockers = []
        if root not in usable:
            blockers.append("missing_or_unavailable_mapping")
        if selected is None:
            blockers.append("ambiguous_snapshot_selection")
        if row["extraction"]["status"] != "declared_complete":
            blockers.append("untrusted_extraction_scope")
        if any(entry["physical_identity"] != "confirmed_local_file" for entry in root_files):
            blockers.append("unavailable_physical_identity")
        if any(entry["workspace_content"] == "different" for entry in root_files):
            blockers.append("workspace_differs_from_selected_facts")
        if issues:
            blockers.append("incomplete_input_observation")
        if selected and row["extraction"]["status"] == "declared_complete":
            try:
                proposed_observations = [
                    item for item in maintenance["observations"] if item["target_snapshot_id"] == selected.id
                ]
                compared_bindings = {
                    item["binding_id"]
                    for item in proposed_observations
                    if item["basis"]["snapshot_id"]
                    == next((entry.snapshot_id for entry in model.bindings if entry.id == item["binding_id"]), "")
                }
                needs_comparison = any(
                    entry.snapshot_id != selected.id and entry.id not in compared_bindings
                    for entry in model.bindings
                    if entry.snapshot_id in catalog and catalog[entry.snapshot_id].source_root_id == root
                )
                if selected.id in {entry.id for entry in targets} or needs_comparison:
                    proposed_observations = preview(model, selected)["observations"]
                observations.extend(proposed_observations)
                if any(
                    item["disposition"] in ("ambiguous", "missing", "indeterminate") and item["resolution"] is None
                    for item in proposed_observations
                ):
                    blockers.append("candidate_or_baseline_requires_review")
            except ModelError as error:
                logging.exception("Plan comparison could not establish an extraction baseline")
                blockers.append("comparison_unavailable")
                issues.append({"code": "comparison_unavailable", "root_id": root, "detail": str(error)})
        inspect = _item(
            items,
            root,
            "inspect-source",
            basis,
            [],
            "blocked" if blockers else "ready",
            blockers,
            "Confirm explicit mapping, physical files and independent extraction scope",
            "Observation only; recheck before export",
        )
        export = _item(
            items,
            root,
            "reexport",
            basis,
            [inspect],
            "blocked" if blockers else "ready",
            blockers,
            "Export this root explicitly if source differs or completeness is unknown",
            "Supply real facts from the intended scope; matching saved bytes do not check new files",
        )
        baseline = _item(
            items,
            root,
            "establish-baseline",
            basis,
            [inspect],
            "blocked" if row["descriptor_differences"] else "ready",
            ["indeterminate_extraction_comparison"] if row["descriptor_differences"] else [],
            "Inspect descriptor differences and explicitly choose a comparable baseline",
            "Agent decision required; extractor changes preserve indeterminate comparisons",
        )
        compare = _item(
            items,
            root,
            "maintenance-preview",
            basis,
            [baseline, export] if "workspace_differs_from_selected_facts" in blockers else [baseline],
            "blocked" if blockers else "ready",
            blockers,
            "Obtain a fresh single-root preview against the current model",
            "Preview is ephemeral; this plan contains no preview token",
        )
        recorded = selected is not None and root_targets(model).get(root) == selected.id
        update = _item(
            items,
            root,
            "maintenance-refresh",
            basis,
            [compare],
            "completed" if recorded else "blocked" if blockers else "ready",
            [] if recorded else blockers,
            "Record only this root's maintenance target with explicit authorization",
            "Completion requires the current recorded target to equal the selected snapshot",
            True,
        )
        inspect_candidates = _item(
            items,
            root,
            "inspect-candidates",
            basis,
            [update],
            "ready",
            [],
            "Read affected evidence and choose candidates without guessing",
            "Multiple candidates require an Agent decision; source inspection remains external",
        )
        root_bindings = [
            entry
            for entry in model.bindings
            if entry.snapshot_id in catalog and catalog[entry.snapshot_id].source_root_id == root
        ]
        rebound = (
            selected is not None
            and recorded
            and bool(root_bindings)
            and all(entry.snapshot_id == selected.id and entry.status == "current" for entry in root_bindings)
        )
        rebind_item = _item(
            items,
            root,
            "maintenance-rebind",
            basis,
            [inspect_candidates],
            "completed" if rebound else "ready",
            [],
            "Rebind each selected observation through the existing atomic operation",
            "Agent must select a real candidate and reread revision before each write",
            True,
        )
        reviewed = recorded and row["review_coverage_status"] == "established" and not row["pending_ids"]
        review = _item(
            items,
            root,
            "maintenance-resolve",
            basis,
            [update],
            "completed" if reviewed else "ready",
            [],
            "Review affected interpretations and resolve exact observations",
            "Current and historical pending are separate obligations; resolution requires real evidence",
            True,
        )
        _item(
            items,
            root,
            "runtime-verification",
            basis,
            [],
            "unknown",
            ["execution_not_established"],
            "Retain unexecuted Verification as planned",
            "Plan and coverage checks never prove runtime behavior",
        )
        row["requested"] = not roots or root in roots
        row["blocking_reasons"] = blockers
        row["independent_transactions_of_roots"] = sorted(known_roots - {root})
        row["cross_root_order"] = "unknown_requires_agent_decision; no inferred priority"
        row["recommended_after"] = []
        row["next_review_item_id"] = review
        recorded_snapshot = catalog.get(row["latest_recorded_maintenance_target"])
        row["recorded_target"] = (
            {
                "snapshot_id": recorded_snapshot.id,
                "source_digest": recorded_snapshot.source.digest,
                "extraction": recorded_snapshot.tools.get("maintenance_scope", ""),
            }
            if recorded_snapshot
            else {"status": "unknown"}
        )
        next(item for item in items if item["id"] == review)["recommended_after"] = [inspect_candidates, rebind_item]
    for item in observations:
        if item["disposition"] != "unchanged":
            affected.add(item["binding_id"])
    impact = _impact(model, affected)
    contracts = _contracts(model, coverage, impact)
    if coverage["unattributed_bindings"]:
        issues.append(
            {
                "code": "unattributed_bindings",
                "binding_ids": [item["binding_id"] for item in coverage["unattributed_bindings"]],
            }
        )
    for entry in model.bindings:
        missing_history = [location.snapshot_id for location in entry.history if location.snapshot_id not in catalog]
        if missing_history:
            issues.append(
                {"code": "unattributed_binding_history", "binding_id": entry.id, "snapshot_ids": missing_history}
            )
    binding = {
        "model_id": model.id,
        "project_id": model.project.id,
        "revision": model.revision,
        "model_digest": digest(model.model_dump()),
        "root_targets": root_targets(model),
        "facts": {identity: digest(snapshot.model_dump()) for identity, snapshot in sorted(catalog.items())},
        "external": external,
        "mapping": {key: str(value.absolute()) for key, value in sorted(mapping.items())},
        "workspace": workspace,
        "file_observations": coverage["files"],
        "engine_digest": _engine_digest(),
    }
    status = (
        "blocked"
        if issues or any(row["blocking_reasons"] for row in coverage["roots"])
        else "ready" if coverage["roots"] else "unknown"
    )
    body = {
        "protocol": PROTOCOL,
        "model_id": model.id,
        "project_id": model.project.id,
        "base_revision": model.revision,
        "committed": False,
        "status": status,
        "inputs": inputs,
        "validity": binding,
        "roots": coverage["roots"],
        "overlaps": coverage["overlaps"],
        "files": coverage["files"],
        "unattributed_bindings": coverage["unattributed_bindings"],
        "affected": impact,
        "contracts": contracts,
        "observations": list({item["id"]: item for item in observations}.values()),
        "pending": {
            "current_ids": sorted(pending & current),
            "historical_ids": sorted(pending - current),
            "total": len(pending),
        },
        "issues": issues,
        "items": items,
        "requires_confirmation": True,
        "summary": {
            **coverage["summary"],
            "items": len(items),
            "current_pending": len(pending & current),
            "historical_pending": len(pending - current),
            "issues": len(issues),
            "blocked_roots": sum(bool(row["blocking_reasons"]) for row in coverage["roots"]),
        },
        "limits": LIMITS,
    }
    for path, hashed in external.items():
        if file_digest(Path(path))[0] != hashed:
            raise ModelError("SOURCE_CHANGED", "/inputs", "Plan input changed during observation")
    if _workspace(mapping)[0] != workspace:
        raise ModelError("SOURCE_CHANGED", "/source-map", "Workspace changed during observation")
    return {"plan_id": digest(body), **body}


def check_plan(model: Model, value: object) -> dict:
    if not isinstance(value, dict) or value.get("protocol") != PROTOCOL:
        raise ModelError("PLAN_INVALID", "/plan", "Unsupported maintenance plan protocol")
    body = {key: entry for key, entry in value.items() if key != "plan_id"}
    if digest(body) != value.get("plan_id"):
        raise ModelError("PLAN_INVALID", "/plan", "Plan content differs from its identity; regenerate")
    _validate_envelope(value)
    old = value["validity"]
    reasons: list[dict] = []
    if old["model_id"] != model.id or old["project_id"] != model.project.id:
        reasons.append({"code": "model_identity_changed"})
    if old["revision"] != model.revision:
        reasons.append({"code": "model_revision_changed", "before": old["revision"], "after": model.revision})
    if old["model_digest"] != digest(model.model_dump()):
        reasons.append({"code": "model_content_changed"})
    try:
        inputs = value["inputs"]
        fresh = generate_plan(
            model,
            Path(inputs["source_map"]) if inputs["source_map"] else None,
            [Path(path) for path in inputs["facts"]],
            inputs["roots"],
            Path(inputs["model_path"]) if inputs["model_path"] else None,
        )
    except (ModelError, OSError) as error:
        logging.exception("Plan prerequisites could not be reobserved")
        reasons.append({"code": "prerequisites_unavailable", "detail": str(error)})
        return {
            "protocol": PROTOCOL,
            "plan_id": value["plan_id"],
            "status": "stale",
            "reasons": reasons,
            "committed": False,
            "requires_replan": True,
        }
    for key in ("root_targets", "facts", "external", "mapping", "workspace", "file_observations", "engine_digest"):
        if old[key] != fresh["validity"][key]:
            change: dict = {"code": key + "_changed"}
            before, after = old[key], fresh["validity"][key]
            if isinstance(before, dict) and isinstance(after, dict):
                changed_keys = sorted(
                    identity for identity in before.keys() | after.keys() if before.get(identity) != after.get(identity)
                )
                change.update(changed_keys=changed_keys[:5], changed_count=len(changed_keys))
            if key == "file_observations":
                previous = {(row["source_root_id"], row["path"]): row for row in before}
                observed = {(row["source_root_id"], row["path"]): row for row in after}
                changed_files = sorted(
                    identity
                    for identity in previous.keys() | observed.keys()
                    if previous.get(identity) != observed.get(identity)
                )
                change.update(
                    changed_files=[{"root_id": root, "path": path} for root, path in changed_files[:3]],
                    changed_count=len(changed_files),
                )
            reasons.append(change)
    status = "stale" if reasons else fresh["status"]
    changed = bool(reasons)
    if not reasons:
        reasons = [
            {
                "code": "prerequisites_unchanged",
                "input_issue_codes": sorted({issue["code"] for issue in fresh["issues"]})[:5],
            }
        ]
        blocked = [
            {"root_id": row["source_root_id"], "reasons": row["blocking_reasons"]}
            for row in fresh["roots"]
            if row["blocking_reasons"]
        ]
        if blocked:
            reasons.append({"code": "root_prerequisites_blocked", "roots": blocked[:5], "total": len(blocked)})
        if not fresh["roots"]:
            reasons.append({"code": "no_evidence_roots"})
    return {
        "protocol": PROTOCOL,
        "plan_id": value["plan_id"],
        "status": status,
        "model_id": model.id,
        "revision": model.revision,
        "committed": False,
        "reasons": reasons,
        "requires_replan": changed,
        "summary": fresh["summary"],
        "recorded_completed_items": sum(item["status"] == "completed" for item in fresh["items"]),
        "notice": "Completed actions do not authorize remaining stale steps. Replan and reacquire revision/preview for every write.",
    }


def _inputs(inputs: dict) -> tuple[dict[str, Path], list[Facts], dict, list[dict]]:
    mapping = {}
    external = {}
    issues = []
    for path in [inputs["source_map"], *inputs["facts"]]:
        if not path:
            continue
        external[path] = file_digest(Path(path))[0]
        value = load_json(Path(path))
        if path == inputs["source_map"]:
            if not isinstance(value, dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()
            ):
                raise ModelError("USAGE_ERROR", "/source-map", "Expected root ID to absolute local directory mapping")
            mapping = {key: Path(entry) for key, entry in value.items()}
    targets = [parse(Facts, load_json(Path(path))) for path in inputs["facts"]]
    if not inputs["source_map"]:
        issues.append({"code": "missing_source_map"})
    return mapping, targets, external, issues


def _validate_envelope(value: dict) -> None:
    inputs = value.get("inputs")
    validity = value.get("validity")
    if not isinstance(inputs, dict) or not isinstance(validity, dict):
        raise ModelError("PLAN_INVALID", "/plan", "Plan inputs and validity must be objects")
    for key in ("source_map", "model_path"):
        if not isinstance(inputs.get(key), str):
            raise ModelError("PLAN_INVALID", "/inputs", "Plan locators must be strings")
    for key in ("facts", "roots"):
        if not isinstance(inputs.get(key), list) or any(not isinstance(item, str) for item in inputs[key]):
            raise ModelError("PLAN_INVALID", "/inputs", "Facts locators and roots must be string arrays")
    expected = {
        "model_id": str,
        "project_id": str,
        "revision": int,
        "model_digest": str,
        "root_targets": dict,
        "facts": dict,
        "external": dict,
        "mapping": dict,
        "workspace": dict,
        "file_observations": list,
        "engine_digest": str,
    }
    if any(type(validity.get(key)) is not kind for key, kind in expected.items()):
        raise ModelError("PLAN_INVALID", "/validity", "Incomplete or invalid plan validity binding")


def _engine_digest() -> str:
    engine = Path(__file__).resolve().parent.parent
    files = list((engine / "architecture_model").glob("*.py"))
    for directory, children, names in os.walk(engine / "static_analyzer"):
        children[:] = [name for name in children if name not in (*DEFAULT_EXCLUDES, "servers")]
        files.extend(Path(directory) / name for name in names if name.endswith(".py"))
    files.append(engine / "infra/repo_utils/ignore.py")
    return digest({path.relative_to(engine).as_posix(): file_digest(path)[0] for path in sorted(files)})


def _workspace(mapping: dict[str, Path]) -> tuple[dict, dict[str, Path], list[dict]]:
    observations = {}
    usable = {}
    issues = []
    cached: dict[str, dict] = {}
    for root, directory in sorted(mapping.items()):
        try:
            if not directory.is_absolute() or not directory.is_dir():
                raise ModelError(
                    "MAPPING_UNAVAILABLE", "/source-map", "Mapping must name an existing absolute directory"
                )
            directory = directory.resolve()
            key = os.path.normcase(str(directory))
            if key not in cached:
                entries: list[tuple] = []
                pending = [directory]
                while pending:
                    parent = pending.pop()
                    with os.scandir(parent) as children:
                        for child in children:
                            if child.name in DEFAULT_EXCLUDES:
                                continue
                            if len(entries) >= MAX_ENTRIES:
                                raise ModelError(
                                    "INVENTORY_LIMIT", "/source-map", "Workspace observation exceeds entry limit"
                                )
                            path = safe_file(directory, Path(child.path).relative_to(directory).as_posix())
                            info = path.stat()
                            entries.append(
                                (
                                    path.relative_to(directory).as_posix(),
                                    info.st_dev,
                                    info.st_ino,
                                    info.st_size,
                                    info.st_mtime_ns,
                                )
                            )
                            if path.is_dir():
                                pending.append(path)
                info = directory.stat()
                cached[key] = {
                    "identity": [info.st_dev, info.st_ino, key],
                    "entries_digest": digest(sorted(entries)),
                    "entries": len(entries),
                }
            observations[root] = cached[key]
            usable[root] = directory
        except (OSError, ModelError) as error:
            logging.exception("Plan mapping could not be observed for root %s", root)
            observations[root] = {"status": "unavailable", "reason": str(error)}
            issues.append({"code": "mapping_unavailable", "root_id": root, "detail": str(error)})
    return observations, usable, issues


def _item(
    items: list[dict],
    root: str,
    action: str,
    basis: dict,
    dependencies: list[str],
    status: str,
    blockers: list[str],
    purpose: str,
    completion: str,
    authorization: bool = False,
) -> str:
    identity = digest({"root": root, "action": action})
    items.append(
        {
            "id": identity,
            "root_id": root,
            "action": action,
            "purpose": purpose,
            "basis": basis,
            "hard_prerequisites": dependencies,
            "recommended_after": [],
            "status": status,
            "reasons": blockers,
            "stop_when": ["Plan stale or unknown", *blockers],
            "why": "Derived from this root's saved scope, local observation and maintenance records; other roots cannot complete it",
            "execution": "external_only; validate hard prerequisites and request confirmation at execution time",
            "completion": completion,
            "requires_user_confirmation": authorization,
            "requires_agent_review": True,
        }
    )
    return identity


def _impact(model: Model, binding_ids: set[str]) -> dict:
    objects = {
        f"{collection[:-1]}_ids": sorted(
            item.id for item in getattr(model, collection) if referenced_bindings(model, [item.id]) & binding_ids
        )
        for collection in ("components", "relations", "scenarios")
    }
    objects["step_ids"] = sorted(
        step.id
        for scenario in model.scenarios
        for step in scenario.steps
        if referenced_bindings(model, [step.id]) & binding_ids
    )
    return {"binding_ids": sorted(binding_ids), **objects}


def _contracts(model: Model, coverage: dict, impact: dict) -> list[dict]:
    snapshots = {item.id: item for item in model.facts}
    bindings = {item.id: item for item in model.bindings}
    targets = {row["source_root_id"]: row["selected_snapshot_id"] for row in coverage["roots"]}
    root_rows = {row["source_root_id"]: row for row in coverage["roots"]}
    rows = []
    for relation in model.relations:
        if relation.contract is None:
            continue
        sides = {}
        for side, ids in (
            ("caller", relation.contract.caller_binding_ids),
            ("receiver", relation.contract.receiver_binding_ids),
        ):
            evidence = []
            for identity in ids:
                binding = bindings[identity]
                snapshot = snapshots.get(binding.snapshot_id)
                root = snapshot.source_root_id if snapshot else ""
                target = targets.get(root, "") if snapshot else ""
                evidence.append(
                    {
                        "binding_id": identity,
                        "root_id": root,
                        "snapshot_id": binding.snapshot_id,
                        "target_snapshot_id": target,
                        "status": (
                            "unknown"
                            if not target
                            else "at_target" if target == binding.snapshot_id else "older_binding"
                        ),
                        "target_recorded": bool(target) and root_targets(model).get(root) == target,
                        "root_reexport": root_rows.get(root, {}).get("reexport", "unknown"),
                        "pending_ids": root_rows.get(root, {}).get("pending_ids", []),
                        "source_digest": snapshot.source.digest if snapshot else "",
                    }
                )
            sides[side] = evidence
        contract_ids = set(relation.contract.caller_binding_ids + relation.contract.receiver_binding_ids)
        checks = []
        for record in model.verifications:
            if not referenced_bindings(model, record.object_ids) & contract_ids:
                continue
            scope = verification_scope(model, record)
            checks.append(
                {
                    "id": record.id,
                    "status": record.status,
                    "scope": scope,
                    "older_target_evidence": any(
                        targets.get(entry["source_root_id"]) != entry["snapshot_id"] for entry in scope["evidence"]
                    ),
                }
            )
        rows.append(
            {
                "relation_id": relation.id,
                "saved_status": relation.contract.status,
                **sides,
                "review": "requires-review" if relation.id in impact["relation_ids"] else "not_established_by_plan",
                "verification": checks,
                "evidence_kind": "static_candidates_only; no automatic contract promotion",
            }
        )
    return rows
