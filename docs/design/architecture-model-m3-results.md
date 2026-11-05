# M3 acceptance — 2026-11-05 (Asia/Shanghai)

This is the original author acceptance record for edf00712. The subsequent PR #4
review fixes and new evidence are recorded separately in
[M3 review corrections](architecture-model-m3-review-results.md). The principal
reviewer's independent Linux results and its denied file-protocol browser check
are distinct from the author's local Chrome results below.

Baseline: clean `origin/main` d4ace08b, with M2 PR #3 merged and reviewed
713cca1f included. New branch: `codex/m3-interactive-browser`, base `main`.
P3 compatibility repair is independent commit `8bc2754c`. No existing PR was
modified or merged by this work.

## Automated verification

| Check | Actual result |
|---|---|
| M1/M2/M3 architecture suite, explicit real Node/Pyright/Tokei | **138 passed**, no skips, 204.28s, Windows Python 3.12.13 |
| Module coverage with unchanged 80% threshold | **97.08%**, 1063/1095 statements; viewer.py **100%** |
| Final focused maintenance/export rerun | **54 passed**, 141.91s, after the test type annotation correction |
| Native Node state/projection suite | **4 passed**, explicit edge order, identity preservation, branch/return/loop/back and cycle stopping |
| Real independent-process M3 replay | **PASS**, revision **8**, S0/S1/S2 real native fact exports; A/B share exactly four component IDs |
| Black | **PASS**, 359 Python files; commit hook enabled |
| Linux mypy | **PASS**, 359 files, existing Debian WSL Python 3.12.13 venv |
| Windows mypy | Exit 1, only baseline `static_analyzer/workspace_dependencies.py:78` SIGKILL attr-defined |
| Distribution | `uv build --wheel` **PASS**; all 12 architecture Python modules and four viewer assets byte-match wheel; isolated-directory installed-wheel export **PASS** |

The initial `python -m build --no-isolation` attempt failed because the local venv
lacks setuptools.build_meta. The normal isolated `uv build` succeeded. A first
build exposed a new namespace-package warning; explicitly listing viewer_assets
as a package removed it. No runtime dependency was added.

P3 was reproduced before the fix through independent full read and maintenance
processes followed by ordinary apply: DANGLING_REFERENCE. Both regression paths
now pass, including cross-process final read, failed-patch byte equality, stale
revision conflict, historical observation preservation and immutable fact equality.
Existing dedicated resolve regressions remain passing.

New export regressions cover frozen model/query revision consistency, export/model
read-only bytes, output collision and failed publication cleanup, verified snippets,
missing roots/files, mismatched hashes, oversized/invalid UTF-8/out-of-range source,
escaping resolved paths, script-closing payloads and provider/telemetry-free imports.
Maintenance projection regression explicitly retains a current confirmation for
an older source target while the latest target has separate pending work.

## Real browser acceptance

Google Chrome **138.0.7204.184**, Playwright with `offline:true`, `file:` URLs,
1500×1050 desktop and 390×844 mobile. No server, CDN or external runtime dependency.
The repeatable driver is `examples/architecture_model/check_viewer.cjs`.

- Actual SVG and component nodes render; all SVG labels fit their drawable bounds.
- Explicit entry differs from first display-order step. Relations and scenario
  explanations are selectable in the same inspector.
- Expanding, collapsing and focusing preserve the current business/step. A collapsed
  ancestor identifies the original internal step. Switching A/B restores each
  browsing position and reuses the same policy node ID.
- Branches pause until selection. Explicit loop entry, loop pause, return/exit,
  actual-path Back, Reset and automatic sole-next traversal work. Missing edges
  stop with an endpoint/gap explanation.
- Exact hash-matched source text is visible. Changed source withholds the body.
  Pending observations, historical pending, actual author/reason/content coverage
  and current confirmation against an older source target are independently visible.
- Adversarial script-closing text and javascript URLs remain inert text. No injected
  script executes and no executable link is created.
- Mobile has no document-level horizontal overflow. The diagram has an explicit
  scroll instruction, visible focus and working ArrowRight scrolling.
- No page errors, no external requests, and identical model hashes before/after
  the browser session. Revision stays **8**. Export stage assertions also compare
  original model bytes before/after every document generation.

The adversarial document is produced from a validated copy of the final model
using `export_html`, replacing a component name with a script-closing/script/link
payload and its explanation with an image error-handler payload. The original
persisted model is untouched. The browser driver includes this negative check
when `untrusted.html` exists in the replay output.

Independent Impeccable finish review initially returned **fix** for clipped graph
labels and insufficient mobile diagram navigation. Both were repaired and
recaptured; the same reviewer scored both **resolved**, no resulting regressions,
disposition **ship** at that fix scope. The manual detector's flat-type warning
read the unexpanded template as 16/16/16px; actual CSS and screenshots show
14px body / 27px h1 / 16px h2. The reviewer confirmed the warning is inconsistent
with the rendered type. The documented design system reflects actual source.

## Artifacts and limits

Committed ready-to-open example: `examples/architecture_model/interactive/index.html`,
source-pending stage `pending.html`, persisted model `model.json`. Frozen documents
embed snippets and do not require a local source checkout. Screenshots and machine
browser results are under `docs/design/architecture-model-m3-evidence/`.
Full replay outputs are local ignored `temp/m3-complete/` with all explicit patches,
facts, per-stage model snapshots, HTML documents and results.json.

H5–H9 and A5–A6 are covered by the design, implementation and replay. No standalone
MCP server, chat Agent, model editor, background scan or new fact engine was added.
Large-model performance and other browsers are unmeasured. Source embedding is
UTF-8, exact-file-hash and 2 MB limited. Output publication requires hard links;
unsupported filesystems fail explicitly. In-memory browsing state resets on reload.
Old source/interpretation bodies are not reconstructed from metadata.

**Not confirmed:** full repository test results, repository-wide 80% coverage and
private CodeBoarding-tests integration. Prior cloud whole-suite GitHub egress was
reported blocked by automatic approval review; the exact original test/request
was not identified here. Searches found mocked GitHub URL/install paths but did
not establish the original egress source. The whole suite was not blindly rerun
or the restriction bypassed. The successful 97.08% number applies only to
architecture_model. Windows SIGKILL is a baseline issue, not counted as a pass.
