# M2 P2 review fixes — 2026-11-04 (Asia/Shanghai)

This updates the same **Draft PR [#3](https://github.com/ZevaierZhan/CodeBoarding/pull/3)**
on `m2/source-maintenance`, base `main`. Start-of-round local and remote head were
the reviewed `a09f2033bd23ad3929f3d11070301e3bf926f708`; the workspace was clean,
with no later edits already covering either finding. Verified implementation:
`1294be7a66f7cbe7db51fe6a305a0476e2bfdccb`. The evidence follow-up changes docs only.

[Machine evidence](architecture-model-m2-p2-validation.json) records exact commands,
exits, timeouts, source/log hashes, regression categories, replay outputs and
compatibility checks. Earlier [M2 results](architecture-model-m2-results.md) and
their fact snapshots remain historical, not rewritten into current results.

## Fixes and coverage rules

**Current impact versus historical review:** source comparison still identifies a
binding, its original evidence and the target snapshot. Model coverage additionally
records `objects-v1` and per-object hashes of the complete affected components,
relations, scenarios and steps. Observation identity includes this interpretation
state. Source comparison results can be reused without freezing model impact or
transferring a historical confirmation to a new scenario.

The review unit is conservatively the whole affected set. Shared B or a changed
related explanation creates a new context; unrelated objects and revision metadata
do not. Unchanged A may be included again in the A/B context, while its old review
remains intact. Exact repeated contexts reuse existing outcomes, including a revert
to an identical previously confirmed definition set.

Ordinary model apply/preview and maintenance preview/refresh/query use the same
shared coverage helper. An ordinary interpretation edit persists new contexts in
the same locked revision/atomic write; B is queryable immediately, before refresh.
`current_coverage_ids` and `current_pending_ids` identify current definitions;
`pending_ids` retains all unresolved historical states and source targets.
Historical confirm closes only its selected scope. Resolve patches require a
current context and record before/result contexts in the same transaction; an
already confirmed resulting state retains its original author/reason. No old
resolution is widened with newly added objects.

**Version-only recovery:** rebind and M1 history protection now share the same
`snapshot_id / source_version / location` field set. A legal non-current binding
with a different declared version but unchanged snapshot/location can recover to
a valid candidate. The complete previous evidence and reason append to history;
the history prefix and binding ID remain. Identical evidence triples add no history.
Rebinding does not close business review, and failures preserve bytes/revision.

## Regression evidence

The initial command `uv run pytest tests/architecture_model/test_maintenance.py -q`
reproduced **7 failed / 27 passed**, 18.90s, before production changes. It caught
pending/confirmed A→B through both library and independent CLI processes,
same-ID explanation changes, and version-only recovery failing `HISTORY_REQUIRED`.

The final suite adds **14 cases**, all passing, covering:

- B added while A is pending; B added after A is confirmed; persisted scope visible
  immediately through ordinary apply and new CLI processes.
- Stable-ID component responsibility and scenario claim edits; historical
  author/reason/version/object coverage remains unchanged.
- No-op/repeated target and independent object creation do not reset a completed
  related context.
- Historical confirmation cannot close current B; stale interpretation patches
  fail intact; a revised return to a previously confirmed context preserves that
  original confirmation.
- Old preview/revision conflicts after model edits, old M2 coverage-unknown
  compatibility and historical review after explicit logical binding deletion.
- Version-only M1 recovery through library and CLI, complete previous evidence and
  history prefix, current-snapshot validation, repeat selection without duplicate
  history, pending review preservation, and failed candidate/save atomicity.

No original test assertion or coverage threshold was weakened. An intermediate
Black check found an unformatted new expression; formatting was corrected and the
entire final scoped check sequence was rerun successfully apart from the unchanged
Windows baseline type error below.

## Final checks on the implementation

| Check | Actual result |
|---|---|
| All M1/M2 tests with explicit real Node/Pyright/Tokei and module coverage ≥80 | **124 passed / 0 failed / 0 skipped**, pytest **148.45s**; **96.88%**, 992/1024 statements. Includes the original 110 plus 14 new cases. |
| Inspected local repository tests: call graph, ignore rules, registry metadata | **51 passed**, 23.18s. These exercise local objects/files and do not replay the blocked whole-suite path. |
| Real M2 continuous independent-CLI example | **PASS**, revision **24**. All twelve source-maintenance acceptance categories remain. Seven explicit review inputs replace the former four because revised explanation contexts on other targets require their own outcomes; no unconditional clearance. |
| Necessary M1/P0 continuous example | **PASS**, revision **10**, 8 callable symbols / 3 static calls, changed real call target and historical/model identity checks retained. |
| Standalone provider/native guard | **PASS**, 8 symbols/3 calls; zero forbidden provider/Python socket attempts, telemetry client absent, zero unfinished Python threads. This is not an OS sandbox for Node/LSP subprocesses. |
| Black and commit hook | **PASS**, 356 files, enabled hook. |
| Native Linux mypy in existing Debian WSL venv | **PASS**, 356 files. |
| Windows mypy | Exit 1, only the previously reproduced baseline `workspace_dependencies.py:78` SIGKILL attr-defined; 356 files checked. That source was not changed. |
| Offline wheel/schema/catalog/legacy verification | **PASS**. All **11** architecture modules byte-match wheel contents. Runtime JSON Schema matches the committed schema. Twelve real export files validate; nine imported catalogs retain original contents and IDs. A real pre-fix revision-21 M2 model reads with unchanged file bytes/revision/facts and preserved resolution fields. |

## Compatibility, limits and attribution

Fact export, strict source inventory, provider-free tool configuration and
transaction design are unchanged from the review baseline. M1 files still read
directly. New optional coverage fields distinguish known content coverage from
legacy M2 observations. A pre-fix confirmation's actual object IDs, author, reason
and version remain; missing content hashes are not invented. A new current context
is derived read-only and persisted at the next successful write. Subsequent
identical contexts are idempotent. No historical fact catalog is upgraded/rehashed.

The two reviewed failures are **product defects reproduced and fixed here**. The
Windows SIGKILL error and previously documented upstream test failures are
**baseline issues**, not silently counted as passing. Earlier whole-suite failures
and the initial M1 race transient remain **historical/unattributed**; this round's
completed scoped tests contain no new unattributed failures.

The user's independent cloud whole-suite run was **blocked by automatic approval
review after unexpected GitHub egress**, without a final coverage report. That is
a user-reported environment/approval result, not a locally reproduced final run.
The exact failing test/URL/payload was not supplied or identified here. This round
did **not** blindly replay that path, disable approvals or bypass the restriction;
only the scoped checks above were run. **Whole-repository 80% remains unconfirmed**,
and private `CodeBoarding-tests` integration was not run. Investigating that egress
requires identifying the specific test, destination and transmitted content before
an authorized replay; fixing all upstream tests is outside these two P2 fixes.

Scope remains M2/Python, complete provider-free re-export, file-byte comparisons
and conservative interpretation cohorts. Large-repository performance/history
growth and complete dependency/environment fingerprints are unverified. M3, MCP
and background scanning remain later work. Review completion records an Agent
decision and its actual scope, not an engine proof of business correctness.

See the [protocol](../architecture-model.md#interpretation-coverage-after-model-edits)
and [continuous guide](../../examples/architecture_model/README.md). Replays used
fresh ignored `temp/m2-p2-demo` and `temp/m2-p2-m1-demo`; original P0 experiments
and source templates were preserved.
