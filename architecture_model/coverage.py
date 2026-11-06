"""Observe independent evidence roots without reconciling their histories."""

import os
from collections import Counter
from pathlib import Path

from architecture_model.errors import ModelError
from architecture_model.file_inventory import MAX_FILES, file_digest
from architecture_model.maintenance import extraction_differences, extraction_status, query, root_targets
from architecture_model.observation import PathObservation
from architecture_model.schema import Facts, Model
from architecture_model.validation import validate_facts
from architecture_model.verification import referenced_bindings


def coverage_report(
    model: Model,
    mapping: dict[str, Path],
    snapshots: list[str],
    targets: list[Facts],
    root_ids: list[str],
    maintenance_report: dict | None = None,
) -> dict:
    catalog = {item.id: item for item in model.facts}
    for target in targets:
        validate_facts(target)
        if target.project_id != model.project.id:
            raise ModelError("FACTS_MISMATCH", "/project", "Coverage target belongs to another project")
        catalog[target.id] = target
    roots = {item.source_root_id for item in catalog.values()}
    if set(mapping) - roots or set(root_ids) - roots:
        raise ModelError("USAGE_ERROR", "/source-map", "Mapping or root filter names an unknown source root")
    selected = {}
    for identity in snapshots + [target.id for target in targets]:
        if identity not in catalog:
            raise ModelError("NOT_FOUND", "/snapshot", identity)
        snapshot = catalog[identity]
        if snapshot.source_root_id in selected:
            raise ModelError("USAGE_ERROR", "/snapshot", "Select at most one snapshot per root")
        selected[snapshot.source_root_id] = snapshot
    recorded = root_targets(model)
    maintenance = query(model) if maintenance_report is None else maintenance_report
    if maintenance["model_id"] != model.id or maintenance["revision"] != model.revision:
        raise ModelError("REVISION_CONFLICT", "/maintenance", "Coverage requires maintenance from this model revision")
    observations = maintenance["observations"]
    coverage_ids = set(maintenance["current_coverage_ids"])
    pending_ids = set(maintenance["pending_ids"])
    groups: dict[tuple, list[dict]] = {}
    fingerprints: dict[tuple, tuple[int, ...]] = {}
    files: list[dict] = []
    rows = []
    binding_index: dict[tuple[str, str], list[str]] = {}
    unattributed = []
    paths = PathObservation()
    for binding in model.bindings:
        basis = catalog.get(binding.snapshot_id)
        if basis is None:
            unattributed.append(
                {
                    "binding_id": binding.id,
                    "snapshot_id": binding.snapshot_id,
                    "status": binding.status,
                    "attribution": "unknown",
                    "reason": "snapshot_unavailable",
                }
            )
            continue
        root = basis.source_root_id
        binding_index.setdefault((root, binding.location.path), []).append(binding.id)
    object_evidence = {
        item.id: referenced_bindings(model, [item.id])
        for collection in (model.components, model.scenarios)
        for item in collection
    }
    for root in sorted(roots if not root_ids else set(root_ids)):
        root_observations = [
            item for item in observations if catalog[item["target_snapshot_id"]].source_root_id == root
        ]
        current = {
            item["id"]
            for item in root_observations
            if item["id"] in coverage_ids and item["target_snapshot_id"] == recorded.get(root)
        }
        root_pending = {item["id"] for item in root_observations if item["id"] in pending_ids}
        resolved = {item["id"] for item in root_observations if item["resolution"] is not None}
        root_bindings = {
            binding.id
            for binding in model.bindings
            if binding.snapshot_id in catalog and catalog[binding.snapshot_id].source_root_id == root
        }
        covered_bindings = {item["binding_id"] for item in root_observations if item["id"] in current}
        versions = [item for item in catalog.values() if item.source_root_id == root]
        choice = selected.get(root)
        selection = "explicit" if choice else "unknown"
        if choice is None and root in recorded:
            choice, selection = catalog[recorded[root]], "maintenance_target"
        if choice is None and len(versions) == 1:
            choice, selection = versions[0], "only_snapshot"
        scope = extraction_status(choice) if choice else {"status": "unknown_selection"}
        evidence = "unknown"
        if choice:
            protocol = scope.get("descriptor", {}).get("protocol", "")
            if protocol == "file-inventory-v1":
                evidence = "file_only"
            elif choice.symbols or protocol in ("python-file-v1", "multilanguage-file-v2"):
                evidence = "static_symbols_calls_bounded"
        row = {
            "source_root_id": root,
            "snapshot_ids": sorted(item.id for item in versions),
            "selected_snapshot_id": choice.id if choice else "",
            "selected_source_version": choice.source.digest if choice else "",
            "selection": selection,
            "latest_recorded_maintenance_target": recorded.get(root, ""),
            "maintenance_target_status": (
                "not_recorded"
                if root not in recorded
                else (
                    "selected_target_recorded"
                    if choice and choice.id == recorded[root]
                    else "selected_target_not_recorded"
                )
            ),
            "extraction": scope,
            "evidence": evidence,
            "limitations": (
                choice.limitations if choice else ["Select a snapshot explicitly; catalog order is not time"]
            ),
            "file_count": len(choice.source.files) if choice else 0,
            "mapping": "supplied" if root in mapping else "unknown",
            "reexport": "unknown",
            "architecture_review": "not_established_by_coverage",
            "pending_ids": sorted(root_pending),
            "current_coverage_ids": sorted(current),
            "current_pending_ids": sorted(root_pending & current),
            "historical_pending_ids": sorted(root_pending - current),
            "resolved_ids": sorted(resolved),
            "historical_resolved_ids": sorted(resolved - current),
            "unassessed_binding_ids": sorted(root_bindings - covered_bindings),
            "review_coverage_status": (
                "unknown_target"
                if root not in recorded
                else "established" if current and root_bindings <= covered_bindings else "unknown_coverage"
            ),
            "descriptor_differences": [],
        }
        bases = {
            binding.snapshot_id
            for binding in model.bindings
            if binding.snapshot_id in catalog and catalog[binding.snapshot_id].source_root_id == root
        }
        if choice:
            row["descriptor_differences"] = [
                {"basis_snapshot_id": identity, "reasons": reasons}
                for identity in sorted(bases)
                if (reasons := extraction_differences(catalog[identity], choice))
            ]
        rows.append(row)
        if choice is None:
            continue
        if len(files) + len(choice.source.files) > MAX_FILES:
            raise ModelError("COVERAGE_LIMIT", "/facts", "Select fewer roots; coverage exceeds 100000 file records")
        local = mapping.get(root)
        if local is not None:
            if not local.is_absolute() or not local.is_dir():
                raise ModelError("USAGE_ERROR", "/source-map", "Mappings must be existing absolute local directories")
            local = local.resolve()
        for path, saved in sorted(choice.source.files.items()):
            record = {
                "source_root_id": root,
                "snapshot_id": choice.id,
                "path": path,
                "saved_hash": saved,
                "physical_identity": "unknown_mapping",
                "workspace_content": "unknown",
                "binding_ids": sorted(binding_index.get((root, path), [])),
            }
            files.append(record)
            if local is None:
                continue
            physical = paths.file(local, path)
            try:
                info = physical.stat()
            except FileNotFoundError:
                record["physical_identity"] = "unavailable_file"
                continue
            if not physical.is_file():
                raise ModelError("UNSAFE_PATH", "/source-map", "Mapped manifest entry is not a regular file")
            physical_id = (info.st_dev, info.st_ino) if info.st_ino else (os.path.normcase(str(physical)),)
            groups.setdefault(physical_id, []).append(record)
            record["physical_identity"] = "confirmed_local_file"
            # Hash once per physical identity, even if several evidence roots share it.
            group = groups[physical_id]
            current = group[0].get("workspace_hash")
            observed = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            if current is None:
                current, _, fingerprint = file_digest(physical)
                if fingerprint != observed:
                    raise ModelError("SOURCE_CHANGED", "/source-map", "Mapped file identity changed during report")
                fingerprints[physical_id] = fingerprint
            elif fingerprints[physical_id] != observed:
                raise ModelError("SOURCE_CHANGED", "/source-map", "Shared physical file changed during report")
            record["workspace_hash"] = current
            record["workspace_content"] = "same" if saved == current else "different"
    paths.finish()
    overlaps = []
    affected = set()
    for group in groups.values():
        if len({entry["source_root_id"] for entry in group}) < 2:
            continue
        same = len({entry["saved_hash"] for entry in group}) == 1
        ids = sorted({identity for entry in group for identity in entry["binding_ids"]})
        affected.update(ids)
        overlaps.append(
            {
                "physical_overlap": "confirmed",
                "saved_content": "same_version" if same else "different_versions",
                "evidence_scope_sync": "independent_scopes; not_established_by_content_equality",
                "architecture_review": "not_established_by_coverage",
                "files": group,
                "binding_ids": ids,
            }
        )
    for row in rows:
        root_files = [entry for entry in files if entry["source_root_id"] == row["source_root_id"]]
        if any(entry["workspace_content"] == "different" for entry in root_files):
            row["reexport"] = "needed_workspace_differs"
        elif root_files and all(entry["workspace_content"] == "same" for entry in root_files):
            row["reexport"] = "recorded_files_match; additions_and_scope_not_checked"
    counts = Counter(item["saved_content"] for item in overlaps)
    return {
        "protocol": "source-coverage-v1",
        "model_id": model.id,
        "revision": model.revision,
        "committed": False,
        "summary": {
            "roots": len(rows),
            "file_records": len(files),
            "confirmed_overlaps": len(overlaps),
            "same_version": counts["same_version"],
            "different_versions": counts["different_versions"],
            "unknown_physical_identity": sum(entry["physical_identity"] != "confirmed_local_file" for entry in files),
            "unattributed_bindings": len(unattributed),
        },
        "roots": rows,
        "unattributed_bindings": unattributed,
        "overlaps": overlaps,
        "files": files,
        "affected": {
            "binding_ids": sorted(affected),
            **{
                f"{collection[:-1]}_ids": sorted(
                    item.id for item in getattr(model, collection) if object_evidence[item.id] & affected
                )
                for collection in ("components", "scenarios")
            },
        },
        "limits": [
            "Live local mappings establish identity only at observation time; files may change afterwards.",
            "Workspace checks cover saved files only, not new files or whole extraction completeness.",
            "Content equality, evidence scope synchronization and interpretation review are separate judgments.",
            "No root, binding, history, review or verification is modified; missing mappings remain unknown.",
        ],
    }
