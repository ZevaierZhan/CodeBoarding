# M6-B: cross-root maintenance planning

## Baseline and decision

Fork PR #9 was merged at `e82ad6cf7e917b348af801991a2ca47349ed3d3d`
on 2026-11-06. The development base is that same latest `origin/main` commit;
branch: `m6/cross-root-maintenance-planning`. The reviewed compatibility head was
`0490e9162893a3ed41f3ddb0d9ff007ab5e6a509`. This work targets the fork's main.

Keep plans outside the persistent domain schema. `maintenance_plan.py` observes
the complete legal model, M6-A coverage and existing maintenance queries/previews.
It never exports facts, calls an LSP, installs tools or commits a model. No new
refresh, rebind, resolve, verification or transaction implementation is introduced.
Operation/Comparison, facet answers and historical review payloads pass through
the existing engine unchanged. No GUI or runtime orchestration is added.

## Interfaces

```text
codeboarding-model model --file MODEL maintenance-plan --source-map MAP --output PLAN
codeboarding-model model --file MODEL maintenance-plan --facts NEW_FACTS --root ROOT --source-map MAP --output NEW_PLAN
codeboarding-model model --file MODEL maintenance-plan --facts NEW_FACTS --preview CURRENT_RESPONSE --source-map MAP --output CONFIRMATION_PLAN
codeboarding-model model --file MODEL maintenance-plan-check --plan PLAN
```

`--facts`, `--root` and `--preview` may repeat. At most one proposed snapshot and
one saved preview response per root are accepted. Preview inputs must be full
responses from the existing CLI; the planner reuses its canonical comparison and
validates exact response content against the current model, revision and target.
No token is copied into the plan. At most one proposed snapshot per root is
accepted. Proposed facts must validate, belong to the model project and an existing
root, and preserve immutable identities. Invalid input fails specifically instead
of inventing evidence. Missing mapping, inaccessible sources and unsupported
extraction scopes produce blocked plans with explicit issues. Source observation
errors retain traceback logs and never become empty successful coverage.

`--root` marks requested work while retaining other roots for overlap and impact
analysis. It does not hide dependencies or invent a priority. Save plans outside
mapped source directories so publication cannot invalidate its own observation.
Existing files, including MODEL, are never overwritten. CLI stdout contains only
identity, status, counts and an absolute output path; complete details are on disk.

## `cross-root-maintenance-plan-v2`

P2 changes item eligibility semantics and therefore emits v2. A valid v1 artifact
can still be checked, but always returns read-only `stale` with
`legacy_item_states_require_replan`; it is never silently upgraded or executed.
The context helper rejects v1 continuation and requests regeneration. Original
v1 files remain unchanged for audit. The persistent domain schema is unchanged.

| Field | Meaning |
| --- | --- |
| `plan_id` | SHA-256 of canonical plan content excluding this field; integrity identity, not authorization |
| `model_id`, `project_id`, `base_revision` | Exact model identity and revision used for analysis |
| `inputs` | Absolute model, mapping, proposed-facts and preview-response locators; requested roots |
| `validity` | Model content hash, revision, per-root recorded targets, all snapshot hashes, input file hashes, mapping, workspace and saved-file observations, engine hash |
| `roots` | Selected snapshot/digest/scope, recorded target/digest/scope, extraction differences, pending groups, source observation and requested focus |
| `overlaps`, `files` | M6-A physical identity, saved versus observed content, separate root scope and binding references |
| `affected` | Binding, component, relation, scenario and step IDs through existing evidence traversal |
| `contracts` | Saved contract status, separate caller/receiver evidence and targets, reexport/pending state, historical Verification scope |
| `observations` | Existing read-only maintenance preview results; no preview token |
| `pending` | Current target-and-content coverage versus historical pending, with independent IDs |
| `items` | Stable root/action ID, kind, gates, evidence, hard prerequisites, unmet dependency IDs, recommended order, status, reasons and completion/confirmation limits |
| `ready_item_ids`, `confirmation_item_ids` | Read-only actions currently allowed versus actions eligible to request decisions |
| `issues`, `limits` | Explicit blockers, unknown provenance and limits of the observation |

The file is a derived work artifact. Editing a status or setting `done=true` does
not establish completion. A modified file fails its content identity check; even
recomputing that public checksum grants no write authority. Check recomputes state
from the actual complete model and current sources. Plan locators refer to local
inputs that the invoking Agent must trust; plans are not signed capabilities.

## Dependency and influence rules

Physical overlap comes exclusively from M6-A's live local identity checks. Same
filename/hash in different directories is not physical overlap. Root selection
uses explicit proposed facts, the saved root target, or the sole snapshot, never
catalog ordering. Missing selection is unknown. A root with mismatching workspace
bytes requires export investigation; another root's matching bytes cannot satisfy
its maintenance obligations. Matching recorded bytes does not check additions or
establish extraction completeness or semantic equivalence.

Per root, normal source drift keeps mapped source investigation available and
export eligible for scope/tool selection. Missing maps still allow inspection of
model root locators. Missing/unsupported scope blocks reliable export/comparison,
not source reading or baseline investigation. A pending export input prevents a
new-version preview; supplied matching proposed facts satisfy that input without
claiming the exporter ran. An actual current CLI preview response satisfies the
refresh prerequisite. User confirmation remains required.

Candidate inspection, rebind and resolve depend on this root's recorded refresh
for the selected target. Rebind also needs actual candidate evidence and Agent
selection; resolve needs actual current review observations. Historical pending
uses explicit historical target context and cannot disappear into current review.
Reading source/candidates and deciding baselines are external actions with no
persistent completion record, so their order is recommended rather than an
unprovable hard dependency. No lexical/language priority is inferred across roots.

`maintenance_plan_states.py` evaluates local trust/input/decision gates and then
walks a validated dependency DAG. Missing edges, cycles and accidental cross-root
hard dependencies fail specifically. Unmet hard prerequisites yield waiting or
blocked, never executable ready or confirmation eligibility. Only evidence with
the matching root and target can satisfy a prerequisite. Recorded completed
operations do not reconstruct their old ephemeral preview history.

Affected evidence includes workspace differences, differing overlap versions,
unresolved maintenance, and non-unchanged preview results. `referenced_bindings`
walks components, relation endpoints, scenarios and steps. The plan conservatively
reports these IDs; it does not rewrite their explanations. Each contract keeps
both sides, recorded target state and historical Verification evidence. One side
at a refreshed target leaves the opposite side independently unassessed. Static
candidates cannot promote a saved contract or imply complete interface validation.

Extractor configuration changes retain existing `indeterminate` semantics.
Unsupported/missing descriptors, missing historical snapshot provenance, missing
files or ambiguous candidates block confident continuation. They never imply
deletion. Cross-root descriptor differences are expected independent scopes;
within-root descriptor differences require a baseline decision.

## Checking and completion

The checker returns structured reasons with these meanings:

| Status | Meaning |
| --- | --- |
| item `ready` | This read-only action is allowed now and all hard prerequisites are satisfied |
| item `requires-confirmation` | Facts/dependencies permit requesting explicit Agent choices/review and user confirmation |
| item `waiting` | Required facts, preview, target, candidate/review context or hard prerequisite is not yet available |
| item `blocked` | An input is untrusted or a strict prerequisite is blocked; independent investigations remain possible |
| item `satisfied` | An actual supplied facts/preview input is validated, without asserting external execution |
| `stale` | Revision, model content/identity, root targets, snapshot/input file, mapping, source observation or engine changed; regenerate |
| `unknown` | No evidence roots or no support for determining an action's completion |
| item `completed` | Current recorded state satisfies the named maintenance action only |

Overall ready/blocked describes maintenance risks, not global action eligibility
or completion. Inspect current item states to choose the first allowed action.
The CLI reports a bounded count of recomputed completed actions. Refresh completion
requires the saved target equal the selected snapshot. Rebind completion requires
the root's actual bindings point at that target. Review completion requires
established current coverage and no root pending observations, including historical
ones. Source inspection, export choice and ephemeral preview are not marked
completed merely because the plan recommends them. Runtime verification remains
unknown; actual saved Verification status and scope stay unchanged.

Ready cannot mean theoretically executable later. Hard dependencies are satisfied
only by validated-input or recorded-operation evidence. A completed refresh names
its exact saved target, and remains completed if the workspace later changes;
newer workspace drift still gates new facts/preview and further writes. No pending
without established interpretation coverage cannot complete review.

Preview response validation establishes equivalence to the current canonical
comparison, not when a command ran, a signed capability or user approval. Skills
require a newly obtained response before a real confirmed write; existing CLI
revision/token checks remain the authority at execution time.

Revision is always checked even if unrelated changes seem harmless. A committed
refresh increments revision, making the old plan stale. Check may report newly
recorded actions while still requiring a new plan for the remaining work. Old
preview tokens and expected revisions are never refreshed by arithmetic.

Local observation binds raw bytes of saved files and physical file identities.
Directory-entry metadata catches additions, removals and configuration changes;
it excludes the inventory's standard generated/dependency directories. Additional
file bytes outside saved manifests are not claimed as extracted evidence. Directory
and input observations are checked again before publication; a detected race fails
with `SOURCE_CHANGED`. Native extractor and model-engine Python implementation
files are hashed so an engine upgrade invalidates resumption. Native tool upgrades
still require explicit reexport and inspection of the supplied extraction descriptor.
Unchanged local metadata cannot establish full extraction completeness.

Checker reasons include bounded samples of changed input/root keys and source
paths, plus total change counts. Stable blocked results name root prerequisite
reasons directly instead of reporting only that inputs were unchanged.

Large-model observations reuse the existing maintenance query across coverage and
planning. Coverage impact marks clone the affected binding while sharing unchanged
collections; model diff skips collections with identical object identity. Existing
coverage fingerprints, transactions and histories remain authoritative. Query and
plan regressions verify that these observations leave all original objects intact.

## Authorization and existing write boundary

Generation/checking is read-only. An external Agent requests explicit user
confirmation immediately before high-impact refresh/rebind/review writes. The
confirmation names root, actual facts, affected IDs and intended interpretation.
Obtain a new complete read and preview, then call existing CLI operations with
that actual facts path, current revision and fresh token. After each write capture
the model again and regenerate the remaining plan. No long-lived credentials are
stored in a plan. Existing ModelStore transactions preserve snapshot/history and
revision checks; multiple root operations are separate atomic commits.

Plan checks are advisory. They cannot stop another caller directly invoking the
existing CLI, enforce global approval, or make independent refreshes atomic.
Reviewing explanations and executing the business remain distinct operations.

## Context and independent continuation

The portable Skill links `references/maintenance-plan.md` at the source-maintenance
branch. Its helper adds a `plan` index with compact IDs/pointers, root/action/status
filters and 4096-character pages. Query one ID or RFC 6901 pointer for detail;
oversized details go to a fresh file using `--output`. Full model/plan/source lists
stay on disk. The saved model/plan/mapping/engine locators replace chat memory.

The public real-export demo is in
`examples/architecture_model/maintenance_planning/demo.py`; it uses prepared Native
TypeScript tools and file inventory, then changes one file and refreshes Native
explicitly. Unit fixtures separately label synthetic static catalogs and historical
execution records as synthetic, never real runtime acceptance.

Validation evidence, independent Agent B results and sanitized private acceptance
metrics are recorded in that example directory. Private model/source/filename
inventories and detailed provenance remain exclusively in the private workspace.

## Remaining questions

Future work may add narrower source-observation caching, explicit extractor tool
observations, or supported export recipes reconstructed from descriptors. These
need their own design and evidence; M6-B does not infer commands from incomplete
descriptors, execute a plan, add a scheduler or start M6-C.
