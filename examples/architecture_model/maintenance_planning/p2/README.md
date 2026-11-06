# P2: action eligibility and hard dependencies

Reviewed head: `b21098289949d0e975e8fc9948861efd5ac7e06e`, continuing fork PR #10.
Only derived plan eligibility, preview response inputs, context queries and Skill
guidance change. Persistent architecture models and maintenance transactions remain
unchanged. No executor or business-code change is introduced.

## Red evidence

`red-items.json` is actual output from the reviewed engine and the existing public
real Native TypeScript/file-inventory demo, loaded through ModelStore. Its model
was copied without rewriting facts, and the two roots point to the same copied
public source. Only Native had been refreshed after `rules.ts` changed.

The old engine blocked source inspection/export for normal drift, while reporting
8 ready actions with unmet hard prerequisites. The first regression test failed
on `inspect-source: blocked != ready`. Complete original output is preserved in
the local reproduction directory; the committed extraction contains every item's
status, hard prerequisites and reasons without environment-specific locators.

## Green evidence

`green-items.json` records the same model/source bytes under v2. All dependency
checks pass. The main operation states are:

| Action | All-files | Native TypeScript |
| --- | --- | --- |
| inspect-mapping | ready | ready |
| inspect-source | ready | ready |
| establish-baseline | ready | ready |
| reexport | requires-confirmation | requires-confirmation (optional investigation/export choice) |
| maintenance-preview | waiting for matching facts | ready |
| maintenance-refresh | waiting for actual preview | completed for recorded target |
| inspect-candidates | waiting for recorded refresh | ready |
| maintenance-rebind | waiting for target/candidates | requires-confirmation |
| maintenance-resolve | waiting for target/review context | requires-confirmation |
| runtime-verification | unknown | unknown |

`ready` permits a read-only action now. `requires-confirmation` permits requesting
the named Agent choice/review and any explicit user confirmation, not executing
automatically. `waiting` identifies missing inputs/dependencies. `blocked` names
untrusted inputs or a blocked strict dependency. Matching proposed facts and a
validated actual preview response become `satisfied` inputs, not completed commands.
`completed` is limited to a model-proven operation for one exact root and target.

Source inspection and mapping investigation need no assertion that an earlier
external inspection finished. Their order before writes is recommended. Hard
dependencies instead bind verifiable inputs and recorded target state. The common
DAG evaluator checks references/cycles/root isolation and propagates every blocked
or unsatisfied dependency before allowing ready/confirmation eligibility.

## Actual preview input and compatibility

Run the existing CLI preview with actual matching facts and save its full response
outside mapped sources. Supply that response as `maintenance-plan --preview FILE`
together with its `--facts FILE`. Validation reuses the existing canonical preview
for the exact current model/revision/target. It stores no token in the plan and
never performs refresh. A valid response makes refresh eligible for confirmation;
a changed, incorrect, missing or stale response leaves it waiting. Every committed
write still requires a new complete read, plan and preview.

Response matching cannot prove command execution time or user approval. The Skill
requires a newly obtained response before writing; ModelStore's existing token and
revision checks remain authoritative. No approval is persisted or globally enforced.

New plans emit `cross-root-maintenance-plan-v2`. Valid v1 plans check as stale with
`legacy_item_states_require_replan`. The helper refuses to interpret v1 ready
states for continuation. Original artifacts are never migrated or overwritten.

## Verification and limits

Run `uv run pytest tests/architecture_model/test_plan_dependencies.py -q` for the
P2 matrix. Tests directly inspect item states, reasons, evidence and hard edges,
including missing/changed scope/mapping, proposed facts and real saved previews,
ambiguous/missing candidates, current/historical pending, later workspace drift,
missing review coverage, stale plans and invalid graphs. Model writes in tests
use disposable synthetic stores only.

The validation summary/logs record exact focused/full gates and the independent
no-history Agent continuation result. Known Windows baseline failures and the prior
load-sensitive CFG timeout remain separately tracked; no timeout, assertion, skip
or coverage threshold is changed. Kotlin is not installed. Real business source
and existing architecture models are not modified; private readonly re-evaluation,
if performed, is recorded only as sanitized aggregate counts.

Completed validation:

- P2 matrix adds 23 tests; P2 plus original planner tests: **52 passed**.
- M1–M6-Compat architecture-model focused run: **332 passed, 10 existing optional
  environment skips**. Native tools are enabled in the separate broad run.
- Q1 related: **51 passed, 4 existing host skips**. Node: **8 passed**.
- Native-enabled broad run: **3040 passed, 5 failed, 55 skipped**, **41.19%**
  coverage against unchanged **80%**. All five failures match the Windows baseline.
  The prior CFG timeout was not reproduced; its isolated module also passed 2 tests.
  It is retained as a historical load-sensitive observation, not declared fixed.
- Black, mypy (393 files) and pre-commit pass. Canonical maintenance/store/schema/
  Verification code and timeout/coverage/skip policies are unchanged from review.

Independent Agent continuation found zero eligibility/dependency violations and
correctly distinguished legacy-stale plans, ready investigations, validated inputs,
recorded completion and confirmation-only writes. Its model and four source files
remained byte-identical. The helper enforced its 4096-character guard, but one
manual selected-field query exceeded that budget before the Agent narrowed it.
Strict per-response discipline is therefore recorded as **not fully maintained**.
The Agent did not inspect candidate source suitability or execute new-target
refresh; automated tests cover that transition with actual saved CLI responses.

Real revision 38 readonly re-evaluation: **3 roots, 30 items**, **0 eligible
dependency violations**, **0 current / 20 historical pending**, and **8 planned
Verifications**. Model and **16,209 source files** retain identical hashes. Private
plan/hash inventories stay private; no real export, refresh, rebind, review or
runtime verification was executed. Those operations remain outside this P2 scope.
