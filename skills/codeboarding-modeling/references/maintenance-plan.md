# Resume cross-root maintenance

Inputs: MODEL, PLAN (optional), engine locator, explicit local root mapping, and
the requested maintenance boundary. Save these locators in the handoff, outside
source directories. Read the existing complete model using the context helper;
reuse existing component, relation, binding, scenario and step IDs.

## Establish the next safe action

1. Capture the complete model and its bounded summary/index. Inspect schema and
   current revision. Keep Operation/Comparison and facet fields intact.
2. If PLAN exists, run `model --file MODEL maintenance-plan-check --plan PLAN`.
   `stale` requires a new complete read and a new plan. Inspect the structured
   reasons; increasing expected-revision alone does not repair stale context.
   A v1 plan is a read-only audit artifact: check returns `stale` with
   `legacy_item_states_require_replan`. Generate v2 before choosing any action.
   `unknown` requires investigation. A top-level `blocked` reports maintenance
   risks; it does not block independent `ready` investigations in a current v2 plan.
3. Generate a fresh plan outside mapped source directories:

   ```text
   codeboarding-model model --file MODEL maintenance-plan --source-map MAP --output NEW_PLAN
   ```

   Add repeated `--facts REAL_FACTS` to propose at most one new snapshot per root.
   `--root ID` focuses the requested work; other roots remain visible for overlap
   and impact checks. Omitting source-map creates a blocked, read-only plan.
4. Use the helper's bounded plan index, then query only relevant fields:

   ```text
   python model_context.py plan --report NEW_PLAN --collection roots --limit 5
   python model_context.py plan --report NEW_PLAN --collection items --search ROOT_ID --limit 5
   python model_context.py plan --report NEW_PLAN --collection items --id ITEM_ID --pointer /hard_prerequisites
   python model_context.py plan --report NEW_PLAN --pointer /pending
   ```

   Collections: items, roots, files, overlaps, contracts, observations, issues,
   unattributed_bindings. Index rows contain JSON pointers. For a large detail,
   select its pointer and `--output DETAIL_FILE`, then query narrower pointers.
   Each response is at most 4096 characters. Keep full plans out of the prompt.
   Query `/ready_item_ids` and `/confirmation_item_ids` or filter item index pages
   by status. Check each chosen item's reasons and `unmet_hard_prerequisites`.
5. Read source for affected bindings and both interface-contract sides. A physical
   overlap identifies a shared local file, not shared roots or interchangeable
   extraction scopes. Matching bytes do not establish semantic synchronization.
   Review the root's extraction descriptor and differences from binding baselines.
   Missing/unavailable provenance and ambiguous candidates require investigation.
6. Before a high-impact model write, present the actual root, facts, affected IDs,
   pending/history consequences and proposed interpretation changes for explicit
   user confirmation. Plan generation/checking never grants that authorization.

## Execute one authorized root operation

Use [the existing maintenance protocol](protocol.md) for exact arguments.
Export real facts explicitly with the intended root/scope and prepared tools;
plan generation never runs exporters, LSPs or installers. Preserve every old facts
snapshot and history record. A file-only export cannot replace Native facts.

Read MODEL again. Generate a plan with `--facts REAL_FACTS`. Matching facts satisfy
the export input; this does not assert an export command was executed. With those
actual facts, run `maintenance-preview --facts REAL_FACTS` and save its complete
CLI response outside mapped source directories. Inspect observations, target and
revision. Generate a new plan with the same facts and `--preview RESPONSE_FILE`.
The planner validates that response against the existing canonical preview for
the exact current model/revision/target. A valid preview input is `satisfied`;
refresh becomes `requires-confirmation`, never automatically authorized.

Immediately before a confirmed refresh, check the current plan and use the token
and revision from that actual fresh response in
`maintenance-refresh --facts REAL_FACTS --token FRESH_TOKEN --expected-revision CURRENT_REVISION --author AUTHOR`.
Plans contain response locators/hashes, not tokens. Receipt matching proves current
input compatibility, not command execution time or user approval. Never copy a
token from an old session. If any input/revision changes, discard that response,
replan and run preview again. Missing/incorrect responses leave refresh waiting.

The item states mean:

| State | Allowed next action |
| --- | --- |
| `ready` | Perform this read-only inspection now; every hard prerequisite is satisfied |
| `requires-confirmation` | Obtain the named Agent selection/review and any explicit user confirmation before execution |
| `waiting` | Acquire the named facts, current preview, recorded target, candidate or review context; do not execute the action |
| `blocked` | Investigate the untrusted input or blocked dependency; use independently ready mapping/source inspections |
| `satisfied` | A supplied facts/preview input has been validated; this is not persistent action completion |
| `completed` | The current model proves this operation for this root and exact target only |
| `unknown` | External execution cannot be inferred; retain planned checks |

Hard prerequisites use only `prerequisite_satisfied` evidence (`satisfied` input or
`completed` recorded operation). Source/candidate reading and Agent decisions have
no persistent completion record; their recommended order is separate from hard
prerequisites. Reading a candidate does not satisfy a rebind decision. A waiting or
blocked predecessor propagates to every strict dependent, including candidates,
rebind and resolve. Different roots can investigate independently.

After **each** write, capture the model again and regenerate the remaining plan.
A successful refresh/rebind/resolve increases revision and makes the old plan stale.
On a conflict, reread changes and recompute; do not simply increment revision.
Rebind only a candidate selected after source inspection, through
`maintenance-rebind`. Resolve exact observations with genuine `confirmed` or
`revised` review through `maintenance-resolve`. An unchanged binding may not need
rebind; the plan's recommended ordering is distinct from hard prerequisites.

## Observation cost and trust

Plan generation and checking use exact content observation. Every command reads
the selected manifest's raw bytes and verifies them again at its closing boundary;
mtime, size and filesystem identity are change hints, not content proof. Shared
physical files can share a hash within one boundary, while each root retains its
own snapshot, descriptor and saved hash. Closing scans use a fresh context.
There is no persistent observation cache or fast advisory CLI mode. A new process
performs exact verification again. Missing, corrupt or deleted local artifacts
require regeneration or input repair; they never grant ready status. A future
metadata-only diagnostic would require exact verification before treating a plan
as current. Git HEAD alone does not account for dirty or untracked bytes.

Source observation establishes current bytes, not correctness of the architectural
interpretation. Review current and historical pending independently even when all
saved files match. When checks report stale or unknown, inspect bounded reasons,
repair the named inputs, and generate a new plan before resuming.

Keep full model/plan artifacts on disk. Use the plan index and the existing ID,
root/status search and JSON-pointer queries above to obtain the next maintenance
item; retain the 4096-character response boundary. The helper parses the complete
JSON locally, so bounded output does not imply constant memory or partial disk
reads. Reuse locators across sessions, then recheck; old chat context and cached
query responses do not establish current prerequisites.

## Completion and handoff

Check the new plan, root targets, candidate state and current/historical pending
separately. Item `completed` is computed from the current model: recorded target,
bindings at that target, or established review coverage with no pending reviews.
No editable checkbox establishes completion. Preview, source inspection, export
selection and runtime proof cannot be reconstructed from model state alone; retain
their stated uncertainty. Recompute item states from current inputs; never mark
external inspections done manually. A ready item allows only the stated read-only
operation, while ready plan inputs grant no write approval. An old recorded refresh
can remain completed after workspace drift; export/preview/write gates still name
that newer drift. Empty pending without established coverage is not completed review.

Preserve unresolved historical pending even when current coverage is reviewed.
Report both contract sides and Verification scope; leave unexecuted checks planned.
Comparison/facet order describes reading, never business execution order.

Save MODEL/PLAN/MAP/engine locators, current revision, facts locators, completed
recorded actions, unresolved item IDs and their reasons for the next Agent. Give
only those locators and the task: “Continue this model's source maintenance plan;
check current state first, without reanalyzing the whole repository.” A new CLI
process alone does not verify independent Agent continuation.

Checks observe local state at a point in time. Existing CLI revision/token checks
remain the atomic write boundary. Plan checks cannot enforce global approval or
stop another caller bypassing them; multiple root writes are independent commits.
