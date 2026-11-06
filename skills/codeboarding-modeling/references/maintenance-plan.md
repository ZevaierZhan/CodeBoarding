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
   `unknown` requires investigation; `blocked` names missing evidence or choices.
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

Read MODEL again. With the actual newly exported facts path, obtain
`maintenance-preview --facts REAL_FACTS` and save its full response. Inspect its
observations, target and revision. Immediately before a confirmed refresh, check
the current plan and use that fresh preview's token and revision in
`maintenance-refresh --facts REAL_FACTS --token FRESH_TOKEN --expected-revision CURRENT_REVISION --author AUTHOR`.
If export introduced a new facts input, regenerate the plan including that path
before acquiring the preview. Never copy a token from an old session.

After **each** write, capture the model again and regenerate the remaining plan.
A successful refresh/rebind/resolve increases revision and makes the old plan stale.
On a conflict, reread changes and recompute; do not simply increment revision.
Rebind only a candidate selected after source inspection, through
`maintenance-rebind`. Resolve exact observations with genuine `confirmed` or
`revised` review through `maintenance-resolve`. An unchanged binding may not need
rebind; the plan's recommended ordering is distinct from hard prerequisites.

## Completion and handoff

Check the new plan, root targets, candidate state and current/historical pending
separately. Item `completed` is computed from the current model: recorded target,
bindings at that target, or established review coverage with no pending reviews.
No editable checkbox establishes completion. Preview, source inspection, export
selection and runtime proof cannot be reconstructed from model state alone; retain
their stated uncertainty. A ready plan means its observed inputs remain usable,
not that its suggested writes have been approved or executed.

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
