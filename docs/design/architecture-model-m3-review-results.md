# PR #4 review corrections — 2026-11-05 (Asia/Shanghai)

Review baseline and start-of-round local/remote head:
`edf00712ffd3c605794c1ce76345aab7094f917c`. The worktree was clean, with no later
changes to preserve. This continues `codex/m3-interactive-browser` and the same
[Draft PR #4](https://github.com/ZevaierZhan/CodeBoarding/pull/4), base `main`.
The original P3 derived-maintenance-ID fix remains unchanged. M3 scope is unchanged.

## P2: physical source lines

The viewer decoded UTF-8 before str.splitlines, which treats U+2028/U+2029 and
NEL as additional line breaks. An exact file hash therefore did not guarantee
correct snippet boundaries. Before fixing production code, 18 LF/CRLF/CR ×
Unicode separator × final-newline cases and three real native-export cases
failed on exact numbered contents. The minimal U+2028 case returned a blank
line 3 and `def target():` on line 4, omitting `return 42`, despite verified status.
The failure log is preserved in the evidence directory.

The viewer now splits original bytes first and decodes each byte line. This is
the same boundary rule as facts_worker's file-level range calculation. Facts,
locations and original-byte hashes are not rewritten. Unsupported UTF-8, missing
files, mismatch, line bounds and 2 MB guards retain their behavior.

Afterward **32 viewer tests passed**, including the 18 matrix cases and three
actual Node/Pyright/Tokei exports. All three native newline variants returned
function start/end **3/4** and file start/end **1/4**, with matching SHA-256, and
both function/file projection contents include numbered `return 42` on line 4.
The native test was then strengthened with an HTML export, a source-bound component
and script-closing text inside the actual Unicode Python string; these **three
native cases passed again**. No source positions were manually manufactured.

`unicode-facts.json`, `unicode-source.py.txt`, the ready-to-open
`examples/architecture_model/interactive/unicode.html` and `unicode-source.png`
retain the real export/content proof. The extension `.py.txt` preserves exact
source bytes without adding a runnable project module.

## P2: binding-level opinions and checks

The selected-object record query excluded associated binding IDs, and code evidence
offered no record query of its own. A validated model could thus export successfully
while a binding opinion and planned/executed checks were unreadable. Before fixing
the runtime, the real local browser assertion found **0 readable binding-opinion
disclosures, expected 1**. Embedded JSON was deliberately not accepted as success.

Each binding's code disclosure now includes **Binding opinions & verification**.
Both code evidence and the metadata binding index can open a direct binding
inspector. A per-inspection registry renders a multi-target record once, with
labeled buttons at other matching targets; those buttons open ancestors, scroll
to the original disclosure and focus its summary. Original object_ids, versions,
status, command, inputs, environment and results are displayed unchanged.
Binding checks never imply component/business verification and do not change claims.

The real replay now includes a binding-only opinion and planned check, a real
executed static-export record targeting application and bind-total, a policy-only
control opinion and a multi-target opinion. Browser interactions from **component,
step and metadata → direct binding** open actual record disclosures and assert
their visible contents. S0 source_version remains S0 in the final S1-bound model;
the executed check retains exactly `[application, bind-total]` and static-only
inputs. The shared opinion retains `[policy, bind-total, bind-buy]`, appears in
full once and has a working reference button. The policy claim remains inference.
Four binding-path screenshots include the reviewed model's older verification.

## P3: shared component projection

Rendering rebuilt a full component Map inside each ancestry lookup and recomputed
every visible node's hidden count by scanning all rows. The fix computes one
byId index, memoized visibleById map, hiddenCounts pass and parentIds set per
render. The tree, active components, nodes and projected edges share this view.
IDs, domain objects, layout positions and edge provenance remain intact.

The reproducible `benchmark_projection.cjs` loads the exact reviewed baseline
engine from Git and runs old/new node/hidden-count computation on the same fully
expanded star input in one Node process. It also checks node/count and edge-reference
equivalence. Windows 10.0.26100, Intel i5-12400, Node v24.20.0:

| Components | Baseline ms | Shared projection ms |
|---:|---:|---:|
| 100 | 48.2303 | 0.3783 |
| 200 | 286.4531 | 0.2237 |
| 400 | 2582.3178 | 0.3145 |
| 800 | 21468.3743 | 0.4991 |

These are **one sample per size of an isolated computation**, not whole-browser
performance or cross-machine timing gates. A separate pre-edit baseline observation
was 43.557/308.513/2647.245/21719.565 ms. The paired comparison above is the
reported before/after result. Node tests additionally cover collapsed forests,
out-of-order parents, unchanged original references and a 2000-node chain. No
virtualization framework, layout engine or schema change was introduced.

## Actual validation

| Check | Result |
|---|---|
| Architecture model suite, explicit real tools, Windows Python 3.12.13 | **159 passed**, no skips, 332.61s |
| Architecture-model module coverage, unchanged 80% threshold | **97.08%**, 1063/1095 statements; viewer.py **100%** |
| Viewer focused tests | **32 passed**, 19.56s; strengthened real source/HTML cases **3 passed**, 26.64s |
| Node projection/player suite | **6 passed**, retaining original 4 playback/identity cases |
| Real independent-CLI M3 replay | **PASS**, revision **8**, S0/S1/S2 native exports, unchanged A/B identity and maintenance assertions |
| Black | **PASS**, 359 files; commit hook enabled |
| Linux mypy, existing Debian WSL Python 3.12.13 venv | **PASS**, 359 files |
| Windows mypy | Only existing workspace_dependencies.py:78 SIGKILL attr-defined; not counted as passing |
| Author local Chrome 138.0.7204.184 | **PASS**, offline file URLs, 1500×1050 and 390×844; no page errors/external requests; model bytes/revision unchanged |

The original derived-ID regressions, explicit branch/loop/return and actual-path
Back, entry-versus-display-order distinction, collapse/focus/A-B location retention,
historical/current explanation and old/latest target distinction remain passing.
The final browser driver also checks Unicode source contents and inert source/model
script-closing text. Final sample HTML files embed the current engine/viewer source;
their frozen model data and records validate separately.

The principal reviewer independently reported the **earlier baseline** Linux
138 tests / 96.99%, Node 4 and Black/mypy 359, plus revision-8 replay. Its Browser
tool **denied file: URLs**, so it did not independently validate browser interaction.
Those are separate facts from the **author's authorized local Chrome/Playwright
checks** here. The denied principal-review path was not retried with another
protocol, tool or browser. No author-local policy denial occurred or was bypassed.

## Reproduce and inspect

```powershell
$env:M1_NODE = (Get-Command node).Source
$env:M1_PYRIGHT = (Resolve-Path temp/p0-tools/node_modules/pyright/langserver.index.js).Path
$env:M1_TOKEI = (Resolve-Path temp/p0-tools/tokei.exe).Path
uv run pytest tests/architecture_model -q --cov=architecture_model --cov-report=term-missing --cov-fail-under=80
node --test tests/architecture_model/viewer_engine.test.cjs
node examples/architecture_model/benchmark_projection.cjs temp/projection-new.json
uv run python -m examples.architecture_model.viewer_demo --output temp/m3-replay-new `
  --node $env:M1_NODE --pyright $env:M1_PYRIGHT --tokei $env:M1_TOKEI
$env:PLAYWRIGHT_MODULE = 'C:/path/to/node_modules/playwright'
node examples/architecture_model/check_viewer.cjs temp/m3-replay-new
uv run black .
uv run mypy .
```

The native regression command and optional Unicode browser artifact are documented
in the example README. Actual local replay output is ignored `temp/m3-review-final`;
the committed evidence directory is `architecture-model-m3-review-evidence/` beside
this report. It includes failures before fixing, the final suite log, performance
JSON, real Unicode facts/source, replay/browser machine records and screenshots.
The original acceptance record remains historical, rather than being relabeled
as principal-reviewer browser approval.

**Still unconfirmed:** whole-repository tests, repository-wide 80% coverage and
private integration. The earlier cloud suite's unidentified GitHub egress was
not blindly replayed or bypassed. Other browsers, large whole-UI benchmarks,
unsupported filesystems and full historical-body recovery remain outside these
fixes. No next-stage product features were started.
