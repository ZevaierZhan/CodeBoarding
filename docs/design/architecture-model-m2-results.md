# M2 source maintenance validation — 2026-11-04 (Asia/Shanghai)

Historical initial M2 evidence. The current P2 fixes, coverage rules and final
validation are recorded in [M2 P2 results](architecture-model-m2-p2-results.md).

Draft PR [#3](https://github.com/ZevaierZhan/CodeBoarding/pull/3) targets fork
`main` from `m2/source-maintenance`. PR #2 was already merged at
`d265acc51968cfcdbfc827a394dba522e6c56512`, including reviewed M1
`df5b692034a97b9a855e333541d9a9a57e654f72`; there is no outstanding PR dependency.
The initial workspace was clean. Original P0 experiments and existing work remain.

The final source commit is `4530239d06e1e3f6e5d60a1e4fdb8fdea4b924b9`.
The subsequent documentation/evidence commit does not change that source.
[Machine evidence](architecture-model-m2-validation.json) records source and log
SHA-256 values, exact commands, actual exits/timeouts, stage dispositions and
affected scenarios. Detailed logs, exports and generated models remain ignored
under `temp/`; the checked-in evidence is a summary, not a replacement fact graph.

## Delivered behavior

The shared operations library and independent-process JSON CLI provide read-only
maintenance preview, revision/token-checked atomic refresh, binding/component/
scenario queries, explicit candidate rebinding with append-only M1 history, and
version-specific confirmed/revised explanation outcomes. Rebinding alone leaves
review pending. Refresh never changes explanations, opinions or old verifications.
Repeated pairs reuse observations and completed outcomes; successful no-op refresh
consumes one revision, matching M1 apply. Earlier unresolved versions survive new
targets and source reverts.

Each binding compares its own immutable baseline. File byte hash is the judgement
granularity; incident call endpoints and before/after locations/sites are reported.
The engine does not claim function-body precision or business correctness.
Scope/configuration fingerprints and an independent strict source inventory prevent
native unreadable-directory skips from becoming successful deletions. Traversal,
stat/read errors, parser/tool errors and discovery disagreement fail export.

## Final verification

| Check | Actual final result |
|---|---|
| `uv run pytest tests/architecture_model -q --cov=architecture_model --cov-report=term-missing --cov-fail-under=80` with real tool paths | **110 passed, 0 failed, 0 skipped**, pytest 116.92s, driver 119.64s; **96.67%**, 928/960 statements. Includes 26 M2 cases, independent CLI processes, all 84 M1 tests, real extraction, explicit-tool failures and provider guards. |
| Strict-inventory regression | Isolated real worker probe rejects unreadable admitted directories and native discovery disagreement before extraction/publication; parent's environment/native registry remains unchanged. |
| Real M2 continuous CLI replay | **PASS**, revision **21**, all twelve requested acceptance categories. Twelve valid exported files; nine unique immutable catalogs imported. Four exact-version interpretation outcomes are saved; twelve later pending observations intentionally remain. |
| M1/P0 continuous replay on final source | **PASS**, revision **10**; **8 callables / 3 calls**, real changed call target, shared A/B identities, structural changes, one-winner revision race and historical missing binding retained. |
| Standalone native/provider guard | **PASS**, 8 symbols/3 calls; zero forbidden provider/socket attempts, telemetry client absent, zero unfinished Python threads. This Python guard is not an OS network sandbox for Node/LSP processes. |
| `uv run black .` and final `--check` | **PASS**, 355 files; both implementation commits ran the enabled Black commit hook. No assertions or coverage thresholds were weakened. |
| Native Debian WSL `uv run mypy .` | **PASS**, 355 files, CPython 3.12.13, existing separate Linux venv/cache. |
| Windows `uv run mypy .` | Exit 1: only `static_analyzer/workspace_dependencies.py:78` SIGKILL attr-defined. Reproduced on pristine current `main` (352 files). |
| Wheel/schema/catalog verification | Isolated `uv build --wheel` succeeds. All **10 architecture modules** in the wheel byte-match source; generated strict JSON Schema equals runtime; imported catalogs exactly match independently exported JSON and keep unique IDs. |
| Final whole-repository `uv run pytest --cov=. --cov-report=term --cov-fail-under=80` | **2809 collected**, bounded at **300s**, owned process tree terminated, test exit **1**, driver elapsed **300.20s**. Reached `test_edge_builder.py` (~69%). Failures observed; no final coverage report. **Repository-wide 80% remains unconfirmed.** |

All Python execution uses `uv run` and CPython 3.12.13. The repository `.env` is
absent; this explicit provider-free path deliberately does not need or read it.
Node, Pyright JS and Tokei were already installed and passed explicitly. No native
tool download or LLM/provider bootstrap was introduced.

## Attribution and limits

On an archive of unmodified current fork main `d265acc5`, selected registry and
renderer files produce **8 failed / 143 passed / 4 skipped**. The failures are:

- Embedded-npm selection, non-executable Node rejection, mocked embedded Node
  installation and gzip chmod (four registry cases).
- Scope-context group/boundary/call inclusion, compact JSON defaults, over-budget
  single examples and bordering-file pruning (four renderer cases).

The separate registry-only baseline is **4 failed / 131 passed / 4 skipped**.
These eight tests and the Windows SIGKILL type error are **baseline-reproduced**.
Other whole-suite failures remain **unattributed**, with no complete summary before
the bounded stop. Private `CodeBoarding-tests` integration was not run.

An initial concurrent M1 replay failed its error-code assertion without recording
the response. Diagnostics now include responses without weakening either assertion.
Five further synchronized writer races and two complete M1 reruns passed; the
initial transient remains **unattributed**, not declared fixed or a baseline issue.
Final M2 stale-preview and atomic failure regressions pass. A non-isolated wheel
attempt lacked `setuptools.build_meta`; isolated `uv build` succeeded without
changing runtime requirements. Earlier 360s/300s whole-suite attempts are historical;
the final-source attempt above is the release evidence.

M1 files load directly with default empty maintenance fields; the first successful
M2 write adds those fields while preserving identities, history and explanations.
Older M1 binaries reject the new optional fields. Historical facts retain original
schema/content/digests; absent legacy extraction descriptors yield indeterminate,
requiring explicit inspection/rebinding/review to establish a new baseline.

Remaining scope: Python, complete re-export, explicitly bound file evidence and
incident calls, conservative file granularity and heuristic candidates. Complete
installed dependencies/external libraries/environment are not fingerprinted. Large
repository performance/history growth, transitive semantic impact, private
integration, MCP, background scanning and M3 UI/playback remain unverified or out of
scope. A completed review records the Agent's decision, not an engine proof.

Reproduce with the [example guide](../../examples/architecture_model/README.md)
and [protocol](../architecture-model.md#m2-source-maintenance), using fresh output
directories and real explicit tools. Final replay outputs used
`temp/m2-demo-release` and `temp/m2-m1-demo-release`; source edits stay inside these
temporary copies.
