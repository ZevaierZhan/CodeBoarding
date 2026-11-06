"""Evaluate plan action gates and hard dependencies without executing them."""

from architecture_model.errors import ModelError
from architecture_model.validation import digest


def root_items(root: str, basis: dict, state: dict) -> list[dict]:
    source_blocks = [] if state["source_available"] else ["missing_or_unavailable_mapping"]
    scope_blocks = [] if state["descriptor_supported"] else ["untrusted_extraction_scope"]
    source_waits = [] if state["workspace_matches"] else ["facts_matching_observed_source_required"]
    selection_waits = [] if basis["snapshot_id"] else ["selected_snapshot_required"]
    comparison_blocks = [] if state["comparison_available"] else ["comparison_unavailable"]
    baseline_decisions = ["extraction_baseline_selection_required"] if state["descriptor_differences"] else []
    export_blocks = source_blocks + scope_blocks + state["source_errors"]
    preview_blocks = export_blocks + comparison_blocks
    snapshot_evidence = {"root_id": root, "target_snapshot_id": basis["snapshot_id"]}
    recorded_evidence = {"kind": "recorded-model-state", "revision": state["revision"], **snapshot_evidence}
    items: list[dict] = []
    _action(
        items,
        root,
        "inspect-mapping",
        basis,
        "read-only",
        [],
        [],
        [],
        [],
        "Inspect model root locators and missing or unsafe local mappings",
        "Inspection is external and is not recorded as completed",
    )
    inspect = _action(
        items,
        root,
        "inspect-source",
        basis,
        "read-only",
        [],
        source_blocks,
        [],
        [],
        "Inspect changed, missing or unchanged source under the explicit mapping",
        "Source drift is a reason to inspect, not a blocker",
    )
    baseline = _action(
        items,
        root,
        "establish-baseline",
        basis,
        "agent-decision",
        [],
        [],
        [],
        ["extraction_baseline_selection_required"] if scope_blocks or state["descriptor_differences"] else [],
        "Inspect extraction descriptions and decide an explicit baseline when necessary",
        "A baseline decision is external; descriptor comparability is observed separately",
    )
    supplied = state["proposed_facts"] and state["workspace_matches"] and not export_blocks
    export = _action(
        items,
        root,
        "reexport",
        basis,
        "external-export",
        [],
        export_blocks,
        selection_waits,
        ["export_scope_and_tools_selection_required"],
        "Explicitly export this root with the intended scope and tools",
        "Supplied matching facts satisfy an input requirement, not proof that an export command ran",
        {"kind": "proposed-facts-input", **snapshot_evidence} if supplied else {},
    )
    items[-1]["recommended_after"] = [inspect, baseline]
    preview_dependencies = [export] if state["proposed_facts"] or not state["workspace_matches"] else []
    receipt = state["preview_verified"] and not (preview_blocks or source_waits or selection_waits)
    compare = _action(
        items,
        root,
        "maintenance-preview",
        basis,
        "read-only",
        preview_dependencies,
        preview_blocks,
        selection_waits + source_waits,
        [],
        "Obtain a fresh existing single-root CLI preview and save its full response",
        "A validated current response satisfies the preview input; no token is stored in this plan",
        {"kind": "validated-preview-response", "revision": state["revision"], **snapshot_evidence} if receipt else {},
    )
    items[-1]["recommended_after"] = [baseline]
    items[-1]["input_diagnostics"] = state["preview_reasons"]
    refresh = _action(
        items,
        root,
        "maintenance-refresh",
        basis,
        "model-write",
        [] if state["recorded"] else [compare],
        preview_blocks,
        [] if receipt else ["fresh_preview_response_required"],
        ["explicit_user_confirmation_required"] + baseline_decisions,
        "Record this root and exact target using the verified current preview response and user confirmation",
        "Only the model's exact recorded root target proves this action completed; workspace synchronization is separate",
        {**recorded_evidence, "operation": "maintenance-refresh"} if state["recorded"] else {},
    )
    candidates = _action(
        items,
        root,
        "inspect-candidates",
        basis,
        "read-only",
        [refresh],
        [],
        [] if state["observation_ids"] else ["maintenance_observations_required"],
        [],
        "Inspect candidates from recorded maintenance for this root and target",
        "Reading candidates and choosing one are external actions; neither is inferred from a plan",
    )
    items[-1]["observation_ids"] = state["observation_ids"]
    rebind_waits = selection_waits + source_waits
    if not state["candidate_ids"]:
        rebind_waits.append("candidate_evidence_required")
    rebind = _action(
        items,
        root,
        "maintenance-rebind",
        basis,
        "model-write",
        [refresh],
        scope_blocks + comparison_blocks + source_blocks,
        rebind_waits,
        ["candidate_selection_required", "explicit_user_confirmation_required"]
        + baseline_decisions
        + (["ambiguous_candidates_require_agent_selection"] if state["ambiguous_candidates"] else []),
        "Select actual candidate evidence, then explicitly rebind through the existing CLI",
        "Only current bindings at the exact recorded target prove completion",
        (
            {**recorded_evidence, "operation": "maintenance-rebind", "binding_ids": state["binding_ids"]}
            if state["rebound"]
            else {}
        ),
    )
    items[-1]["recommended_after"] = [candidates]
    items[-1]["candidate_observation_ids"] = state["candidate_ids"]
    resolve_waits = selection_waits + source_waits
    if not state["review_ids"]:
        resolve_waits.append(
            "historical_review_requires_explicit_target_scope"
            if state["historical_pending_ids"]
            else "current_review_context_required"
        )
    if not state["review_established"] and not state["review_ids"]:
        resolve_waits.append("interpretation_coverage_not_established")
    review = _action(
        items,
        root,
        "maintenance-resolve",
        basis,
        "model-write",
        [refresh],
        scope_blocks + comparison_blocks + source_blocks,
        resolve_waits,
        ["interpretation_review_required", "explicit_user_confirmation_required"] + baseline_decisions,
        "Review exact current observations before resolving through the existing CLI",
        "Completion requires established coverage and no root pending, including historical pending",
        (
            {**recorded_evidence, "operation": "maintenance-resolve", "observation_ids": state["coverage_ids"]}
            if state["reviewed"]
            else {}
        ),
    )
    items[-1]["recommended_after"] = [candidates, rebind]
    items[-1]["review_observation_ids"] = state["review_ids"]
    items[-1]["historical_pending_ids"] = state["historical_pending_ids"]
    _action(
        items,
        root,
        "runtime-verification",
        basis,
        "runtime-execution",
        [],
        [],
        [],
        [],
        "Retain unexecuted Verification as planned",
        "Source maintenance cannot establish execution",
    )
    items[-1]["unknown_reasons"] = ["execution_not_established"]
    for item in items:
        item["recommended_after"] = list(dict.fromkeys(item["recommended_after"]))
        item["workspace_matches_selected_manifest"] = state["workspace_matches"]
        item["external_execution_observed"] = False
    return items


def evaluate_dependencies(items: list[dict]) -> None:
    index = {item["id"]: item for item in items}
    if len(index) != len(items):
        raise ModelError("PLAN_DEPENDENCY_INVALID", "/items", "Duplicate plan item IDs")
    visiting: set[str] = set()
    evaluated: set[str] = set()
    for identity in index:
        _evaluate(identity, index, visiting, evaluated)


def _action(
    items: list[dict],
    root: str,
    action: str,
    basis: dict,
    kind: str,
    dependencies: list[str],
    blocks: list[str],
    waits: list[str],
    decisions: list[str],
    purpose: str,
    completion: str,
    evidence: dict | None = None,
) -> str:
    identity = digest({"root": root, "action": action})
    items.append(
        {
            "id": identity,
            "root_id": root,
            "action": action,
            "purpose": purpose,
            "basis": basis,
            "kind": kind,
            "hard_prerequisites": dependencies,
            "recommended_after": [],
            "conditions": {"blocking": blocks, "waiting": waits, "confirmation": decisions},
            "evidence": evidence or {},
            "completion": completion,
            "why": "This root's observed inputs and exact recorded target determine eligibility; another root cannot satisfy it",
            "requires_user_confirmation": "explicit_user_confirmation_required" in decisions,
            "requires_agent_review": any(reason != "explicit_user_confirmation_required" for reason in decisions),
            "execution": "external_only; recheck plan and explicit decisions before calling the existing CLI",
        }
    )
    return identity


def _evaluate(identity: str, index: dict[str, dict], visiting: set[str], evaluated: set[str]) -> None:
    if identity in evaluated:
        return
    if identity in visiting:
        raise ModelError("PLAN_DEPENDENCY_INVALID", "/items", "Hard prerequisite cycle")
    visiting.add(identity)
    item = index[identity]
    for dependency in item["hard_prerequisites"]:
        if dependency not in index or index[dependency]["root_id"] != item["root_id"]:
            raise ModelError("PLAN_DEPENDENCY_INVALID", "/items", "Missing or cross-root hard prerequisite")
        _evaluate(dependency, index, visiting, evaluated)
    evidence = item["evidence"]
    if evidence and (
        evidence["root_id"] != item["root_id"] or evidence["target_snapshot_id"] != item["basis"]["snapshot_id"]
    ):
        raise ModelError("PLAN_DEPENDENCY_INVALID", "/evidence", "Evidence belongs to another root or target")
    conditions = item["conditions"]
    unmet = [dependency for dependency in item["hard_prerequisites"] if not index[dependency]["prerequisite_satisfied"]]
    reasons = list(conditions["blocking"] + conditions["waiting"] + conditions["confirmation"])
    if evidence.get("kind") == "recorded-model-state":
        status = "completed"
        unmet = []
        reasons = ["exact_root_target_operation_recorded"]
    elif unmet or conditions["blocking"]:
        blocked = bool(conditions["blocking"]) or any(index[dependency]["status"] == "blocked" for dependency in unmet)
        status = "blocked" if blocked else "waiting"
        if unmet:
            reasons.append("unsatisfied_hard_prerequisites")
    elif conditions["waiting"]:
        status = "waiting"
    elif evidence:
        status, reasons = "satisfied", ["validated_input_available; external_execution_not_inferred"]
    elif conditions["confirmation"]:
        status = "requires-confirmation"
    elif item.get("unknown_reasons"):
        status, reasons = "unknown", item["unknown_reasons"]
    else:
        status = "ready"
    if status == "ready" and item["kind"] not in ("read-only", "agent-decision"):
        raise ModelError("PLAN_DEPENDENCY_INVALID", "/status", "A write/export cannot be ready without confirmation")
    item.update(
        status=status,
        reasons=list(dict.fromkeys(reasons)),
        unmet_hard_prerequisites=unmet,
        prerequisite_satisfied=status in ("completed", "satisfied"),
        can_execute_without_confirmation=status == "ready",
        can_request_confirmation=status == "requires-confirmation",
        stop_when=["Plan stale or unknown", *conditions["blocking"], *conditions["waiting"]],
    )
    visiting.remove(identity)
    evaluated.add(identity)
