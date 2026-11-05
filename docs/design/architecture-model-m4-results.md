# M4 acceptance — 2026-11-05 (Asia/Shanghai)

The [M4 P2 follow-up](architecture-model-m4-p2-results.md) formalizes large-model
context and engine/target separation. PR #4 has since merged; PR #5 now targets
main. The original acceptance and 0–13 evidence below remain historical.

M4 delivers an executable external-Agent workflow and actual continuing model,
not an internal business-analysis Agent. Start was a clean checkout of reviewed
M3 head `34b4e48f2388049eeaf180efcbf285029d7b384b`. Remote PR #4 was checked at
start and before delivery: still OPEN at that head. This work uses separate branch
`codex/m4-external-agent-skill` and stacks its Draft PR on
`codex/m3-interactive-browser`. Existing PRs were not merged or modified.

The [implementation/story mapping](architecture-model-m4.md),
[actual model guide](../../examples/architecture_model/codeboarding/README.md),
[fresh Agent report](../../examples/architecture_model/codeboarding/03-agent-session.md)
and [machine results](architecture-model-m4-evidence/validation.json) accompany
the repository-owned [Skill](../../skills/codeboarding-modeling/SKILL.md).

## Actual continuous use

One persistent model, `ba06c25c-e8de-4781-8a09-e7643b9e4721`, evolves from revision
0 through **13**. Complete revision records remain contiguous. Stage snapshots
retain old explanation bodies in addition to the model's own revision/maintenance
metadata; the viewer does not reconstruct past prose from fingerprints.

| Stage | Actual result |
|---|---|
| A, revision 1 | Real subsystem facts imported; 7 components, 26 stable evidence bindings and 5 relations. Responsibility, rationale and inference assumptions saved. Logical maintenance spans maintenance.py and maintenance_coverage.py. |
| B, revision 2 | `read-to-html`: 7 explicit steps cover dispatch, validated read, frozen projection, maintenance view, source snippets, non-overwriting publication and response. Nested returns/unsupported browser scope are explicit. |
| C, revision 3 | Separate Agent with `fork_turns:none` reads the Skill and complete model, inspects real code, then adds `agent-submits-patch` with 11 steps and preview/apply/conflict/rejection/output-recovery paths. It reuses cli/store/validation, 14 bindings and existing relations; no components/facts/bindings were duplicated. |
| D, revision 4 | Preset feedback is labeled rehearsal, not user acceptance. One opinion preserves its text/targets. Store/viewer rationale is revised in place; both scenarios remain exactly equal to revision 3. A genuinely executed revision-3 structural validation is saved separately from the planned business/human check. |
| E, revisions 5–11 | Only an isolated viewer.py diagnostic changes. New real facts drive preview/refresh; 3 same-symbol candidates are explicitly chosen and re-bound. Rebinding leaves explanation review open; 3 independent confirmations follow. |
| E, revisions 12–13 | Later viewer rationale names the hard-link prerequisite. This changes content coverage and retains old confirmations. The export explanation is confirmed for the new content; `e-projection` and `e-snippet` retain **2 current pending contexts**. Original verification source versions remain original. |

The fresh Agent actually received the Skill path, repository path, model locator,
task and execution-scope instructions; it did not inherit parent conversation.
One later message requested that authored JSON remain canonical and script be
labeled an authoring transcript. Both exact messages are in its report. Source
inspection, commands, actual responses and preservation assertions are retained.
This is distinct from both separate CLI processes and the deterministic replay.

## Real-source boundary and maintenance limits

Original extraction: **12 Python files, 88 symbols, 153 static calls**, exported
through the real StaticAnalyzer/PythonAdapter/Pyright pipeline. Only
`architecture_model/*.py` was copied to `temp/m4-source`, preserving repository
paths. Every original file SHA-256 matched production; this equality was rechecked
after the experiment. No handwritten facts, LLM-generated ownership or invented
calls were used. Viewer assets, other packages, dependencies and runtime behavior
are excluded. Their references can remain external/unresolved.

Original source digest:
`ea441b5103ee08ec854f05c62873bb798cabb6b57ff9f32b1d02608b57e01001`.
Controlled-copy digest:
`ae6414d6a204eb199be1dd20de745730478f2bd286d2e740085d6935214e4125`.
Both have 88 symbols/153 calls. Their manifests differ only at
`architecture_model/viewer.py`. Git context is the enclosing checkout's HEAD,
even inside this copy without its own .git; it is not a content identity.
[scope.json](../../examples/architecture_model/codeboarding/scope.json) records
this distinction. The exact [controlled patch](../../examples/architecture_model/codeboarding/controlled-source.patch)
adds hard-link filesystem guidance to a failure message and never enters product
Python. Copied code is analyzed, not installed as the executing exporter.

Containing-file hashing conservatively marks all 3 viewer bindings changed, even
though the success path and static endpoints remain unchanged. Impact can include
both scenarios through shared components/relations; this is conservative reference
impact, not proof that both businesses changed at runtime. Rebind histories retain
the prior snapshot/location/hash. Old review object fingerprints and old executed
verification remain visible. Two pending interpretation contexts are intentional
and are not converted into “latest business verified.”

## Execution and engineering checks

All Python commands use `uv run`, Python **3.12.13** and the repository venv.
`.env` is absent; this explicit provider-free path does not read it. Existing
Node **24.20.0**, Pyright **1.1.400** and Tokei executables were supplied explicitly;
tool paths, argv and extraction descriptors are in the real facts catalogs.
No global Agent configuration, native-tool installation or provider was introduced.

| Check | Actual result |
|---|---|
| Architecture suite with real explicit tools | **159 passed**, 300.87s; **97.08%**, 1063/1095 statements, unchanged 80% threshold; viewer.py 100% |
| New M4 artifact/template regression file | **4 passed**, 2.41s: stage identity/business preservation, catalog/history semantics, HTML consistency, all 3 templates expanded into a valid incremental candidate without writing |
| Native Node engine suite | **6 passed** |
| Skill validator | **PASS**; fresh Agent actually loaded the explicit repository path, used templates/protocol and continued the model |
| Mechanical replay | **PASS**, new UUID, revision 13; authored components/scenarios/bindings preserved. Replay exports real facts and reruns structural verification with its own execution details. It is not a second fresh-Agent test. |
| Black | **PASS**, 361 Python files; enabled commit hook required at commit |
| Windows mypy | Exit 1, only previously recorded `static_analyzer/workspace_dependencies.py:78` SIGKILL attr-defined; 361 files, no M4 errors |
| Whole repository requested command | 2858 collected; **300s bound reached**, owned process tree terminated, exit 1, observed failures; no final coverage report. Full-suite success and repository-wide 80% remain **unconfirmed**. New M4 tests were added after this collection and ran separately. |
| Private integration | Not run; private CodeBoarding-tests unavailable |

The first 159-test run passed its tests but reported 6.21% coverage because a
concurrent full-suite process polluted the shared coverage data. That report was
discarded. The reported final module run uses its own
`COVERAGE_FILE=temp/m4-module-isolated.coverage`. No threshold/omission changed.
Full-suite failures were not all triaged and are not labeled baseline-only.
Linux results from M3 are historical; no new Linux M4 pass is claimed.

Full logs, command indexes, raw compressed transcripts and machine metadata make
the exact execution scope reviewable. The replay refuses different product bytes
and existing output directories; authored business decisions live in JSON patches,
not helper code. Its regenerated executed check identifies the new actual model,
inputs/environment and time instead of reassigning the original result.

## Interactive verification

The required in-app Browser execution tool was absent from the active inventory.
After reading its skill and checking tools, the author used the available local
Playwright package with a new headless Chrome **138.0.7204.184** over an ephemeral
loopback HTTP server. No `file:` navigation or previously denied path was retried.
The independent stage-C Agent did not run a browser; its report says so.

[Browser results](architecture-model-m4-evidence/browser/results.json) and three
actual screenshots record the final revision-13 document:

- 2 businesses render; embedded model identity/revision equal the persistent file.
- Hierarchy collapses to one node and expands to all 7; identities remain stable.
- Business switching retains position; explicit next and automatic playback follow
  saved transitions to the modeled export endpoint.
- Viewer rationale and exact hash-matched source are readable; older source bodies
  are withheld, while maintenance/review history and record disclosures remain.
- Mobile has no page-wide overflow. No page errors or external requests occurred.
  Model SHA-256 before/after browsing is unchanged.

The localhost test is not a new independent test of file-protocol opening. The HTML
is self-contained by the existing M3 implementation; no changes to that runtime
were needed. This trial does not claim all patch error branches executed, human
acceptance, whole-repository understanding or runtime business correctness.

