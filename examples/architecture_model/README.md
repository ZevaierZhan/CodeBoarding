# Continuous architecture modeling

The fixture source templates are real Python once materialized. `app.start`
registers two callable routes; it does not run them or start a server. Purchase
`buy` rejects nonpositive quantity, calculates a total and formats an order ID.
Quotation `quote` calculates a total with the same `policies.pricing.total`.
`save` only formats a string: this example has no database. All responsibility
boundaries and scenario descriptions are explicit Agent interpretations.

Run from the repository root, using existing tools and a **new** output directory:

```powershell
uv run python examples/architecture_model/demo.py `
  --output temp/m1-demo `
  --node (Get-Command node).Source `
  --pyright temp/p0-tools/node_modules/pyright/langserver.index.js `
  --tokei temp/p0-tools/tokei.exe
```

Install Pyright 1.1.400 and a compatible Tokei/Node if these P0 tools are absent;
the script and production CLI do not download dependencies. Paths can point to
tools installed elsewhere. API-key variables are removed from each CLI invocation.

Every model/facts command launches a new `python -m architecture_model` process.
The script creates one explanation model, then:

1. Exports the original P0 fixture's eight callable symbols and three known edges;
   changes `place_order` to call `format_receipt` in a temporary source copy and
   exports again. It asserts the exact changed edge and different content version,
   and unchanged explanation bytes. Original P0 sources remain intact.
2. Exports this example's real source and copies the immutable fact catalog and
   bindings into the model together with startup components and explanation.
3. Adds purchase A and quotation B in successive processes, sharing `policy`.
4. Reads only A, revises the shared component, checks both affected scenarios in
   diff and exact preservation of B. Preview commands leave bytes unchanged.
5. Moves membership across policy/persistence directories, renames and reparents
   while retaining IDs, splits and merges with explicit reference repair. A delete
   omitting A's reference fails intact. A parent cycle fails; a hypothetical repeat
   quotation transition saves with its missing caller-loop evidence stated.
6. Uses ready/go files as an explicit barrier to launch two writers with the same
   expected revision. Exactly one commits, the loser conflicts, and the winner's
   full object is the only final value with exactly one revision increase.
7. Deletes the temporary pricing source, explicitly marks its binding missing,
   reads the historical explanation in another process and rejects an absent
   internal binding ID.

The final model is revision 10. Output contains every patch, immutable facts,
the single final model, and `results.json` with per-stage responses and real diffs.
The output directory is intentionally refused on repeat to prevent reading old
successful artifacts. Choose another fresh directory to repeat. Keep temporary
results ignored; do not add the entire output to Git.

Disk failure, schema/version, nested unknown field, duplicate ID and further
reference/CLI behavior tests live under `tests/architecture_model`:

```powershell
$env:M1_NODE = (Get-Command node).Source
$env:M1_PYRIGHT = (Resolve-Path temp/p0-tools/node_modules/pyright/langserver.index.js).Path
$env:M1_TOKEI = (Resolve-Path temp/p0-tools/tokei.exe).Path
uv run pytest tests/architecture_model -q --cov=architecture_model --cov-report=term-missing --cov-fail-under=80
```

Without those three environment paths, the real-engine test is explicitly skipped;
unit and independent-process model tests still run. With them it also executes a
standalone guarded native probe: provider setup/invocation and Python socket
attempts are forbidden, attempts are accumulated, telemetry is absent, and newly
created Python threads must settle. These guards are test-only and do not import
P0's experimental audit/atexit machinery into the production library. They are not
a network sandbox for third-party LSP subprocesses.

## M2: maintain interpretations after source changes

From the repository root, choose a fresh output directory and the same explicit
real tools (Python 3.12 through `uv run`; no provider or `.env` is required):

```powershell
uv run python -m examples.architecture_model.maintenance_demo `
  --output temp/m2-demo `
  --node (Get-Command node).Source `
  --pyright temp/p0-tools/node_modules/pyright/langserver.index.js `
  --tokei temp/p0-tools/tokei.exe
```

This is a second continuous example; the original M1/P0 experiment above remains
unchanged. It materializes the same real Python fixture in a temporary source
tree. All facts come from complete native StaticAnalyzer/Pyright exports; the
Agent's explanation patches are explicit inputs. Every model/facts command runs
in an independent process. A failed assertion stops the replay; existing output
directories are refused.

| Acceptance | Actual replay |
|---|---|
| No changes/repeated target | Export S0 twice with identical contents, refresh twice, assert no pending review or duplicate snapshot/observation |
| Shared A/B change | Change pricing's multiplier; affected scenarios are A/B, original explanations and binding evidence remain intact |
| Unrelated source | Add unrelated Python function; other bindings remain unchanged despite global digest change |
| Granularity/positions | Insert blank lines and auxiliary function, then change only auxiliary; pricing still needs conservative whole-file review |
| Move/rename | Move pricing file and rename total; inspect candidates and explicitly rebind the original binding ID, retaining history |
| Missing | Delete both replacement pricing files; store missing with original path/version and read scenario B in a new process |
| Ambiguity | Copy pricing to two replacements; assert ambiguous and explicitly choose rates3, retaining other candidates |
| Continuous refresh | S1's pending issue survives unrelated S2 and S3; rebinding itself leaves pending review |
| Review outcome | Revise policy once, confirm other target-specific interpretations, read reasons/versions from new processes |
| Rebuild | Completely export again with no cache; facts ID matches, existing logical IDs/explanations remain |
| Failure/scope | Syntax failure publishes nothing; excluding previously included delivery directory produces indeterminate preview with unchanged model bytes |
| Conflict | Preview, commit another refresh, reject the stale preview with REVISION_CONFLICT and byte equality |

`results.json` stores previews, commits and errors. The final model retains
unresolved later source changes intentionally: the example demonstrates their
survival, not automatic clearance. All source changes stay in the output tree.
The repository's source templates and P0 history are preserved.

For an external business Agent, the normal loop is:

1. Read the same model and its scoped `maintenance` query; inspect prior reasons.
2. Run `facts export` with explicit tools into a new output path.
3. Run `maintenance-preview`; inspect basis, target, file-granularity reasons,
   static calls, impacted scenarios and every plausible candidate.
4. Submit `maintenance-refresh` with its token and expected revision.
5. If relocating evidence, use `maintenance-rebind` with the chosen candidate.
6. Inspect source and submit `maintenance-resolve` for each intended target version,
   using confirmed or a revised explanation patch and a concrete reason.
7. Read again in another process. Older unresolved versions remain visible.

Review coverage also follows model edits. Shared new scenarios and changed related
definitions create a new context without extending any old confirmation. Query
`current_pending_ids` for current definitions and `pending_ids` for all unresolved
history. A revised review can create new contexts for other source targets; the
replay re-queries pending work after each explicit outcome and processes these
separately. With the P2 coverage rule its final revision is **24** (the earlier
revision-21 record remains historical). Pre-fix M2 confirmations retain their IDs,
authors, reasons and declared object sets, with unknown content coverage until a
new context is explicitly reviewed.

The [protocol](../../docs/architecture-model.md#m2-source-maintenance) documents
commands, strict review JSON, M1 compatibility and failure semantics. Extend the
M1 test command above to include all M2 regressions in the same directory.

Real worker API checks run in a child process and assert that the pytest parent's
configuration, environment and native module state are unchanged. `.coveragerc`
enables subprocess measurement so those checks remain part of coverage. Additional
explicit-tool tests simulate another installation under a temporary home, check
the actual Node/argv markers, and reject failed Tokei/Pyright executables without
publishing facts or changing the model.

## M3: offline interactive explorer

Open `examples/architecture_model/interactive/index.html` locally for the reviewed
model, or `interactive/pending.html` for the source-change stage. Both are fully
offline. The persisted `interactive/model.json` retains A, B and shared IDs, so
an external Agent can continue updating it with the ordinary CLI.

Replay from real fixture sources and native facts into a **new** directory:

```powershell
uv run python -m examples.architecture_model.viewer_demo `
  --output temp/m3-demo-new `
  --node (Get-Command node).Source `
  --pyright temp/p0-tools/node_modules/pyright/langserver.index.js `
  --tokei temp/p0-tools/tokei.exe
```

Every fact/model operation launches a separate CLI process. The same helpers,
fixture, real StaticAnalyzer/Pyright/Tokei export and M2 maintenance protocol are
reused. Outputs are `01-purchase.html`, `02-shared-businesses.html`,
`03-source-pending.html`, `04-reviewed.html`, the one persisted model plus frozen
stage models and `results.json`. A starts at its explicit entry despite its
deliberately different display order. B is added later and reuses the exact same
four components. Changing `total` from multiplier 10 to 12 makes both businesses
pending. Explicit rebinding and confirmation preserve binding history and exact
review scope. A clarified shared-boundary explanation creates a new review
context: only that context is confirmed, leaving the earlier explanation's pending
review visible as history. A final unrelated S2 export keeps the S1 confirmation
explicitly labeled as an older target. Session feedback is an ordinary opinion; planned/executed checks
are separate from business assertions.

The quantity validation branch is based on `delivery.orders.buy`. The modeled
caller retry loop and abandon/return path are **intent hypotheses**: this fixture
has no retry/cancel caller implementation. Conditions are never evaluated by the
page. `save` only formats an ID, and the executed static export is not a business
execution verification.

Generate any one-model document separately:

```powershell
uv run codeboarding-model model --file temp/m3-demo-new/architecture-model.json `
  export-html --output temp/m3-demo-new/another-view.html `
  --source-root temp/m3-demo-new/source
```

Automate real offline browser acceptance with a locally installed Playwright
package and Google Chrome (no installation/download occurs in this script):

```powershell
# Optional: absolute module directory if Playwright is outside Node's module path.
$env:PLAYWRIGHT_MODULE = 'C:/path/to/node_modules/playwright'
node examples/architecture_model/check_viewer.cjs temp/m3-demo-new
node --test tests/architecture_model/viewer_engine.test.cjs
```

The browser script checks SVG rendering, ancestors/current step, focus, A/B shared
IDs, explicit branch selection, back, loops/return, source evidence, pending/reviewed
state, metadata, mobile width, page errors, requests and model byte identity.
`browser/results.json` and PNG screenshots are written below the chosen output.
It also checks hostile text when `untrusted.html` is present. Python security
regressions run with the architecture_model pytest suite. The runtime ships in
the HTML; Node/Playwright are verification tools only. See
[reader/Agent instructions](../../docs/architecture-model-viewer.md) and
[M3 design](../../docs/design/architecture-model-m3.md).

### M3 review regressions

The example now includes a binding-only opinion, a planned pricing check, the
real executed export targeting `application` and `bind-total`, a component opinion
as control and an opinion targeting several bindings/components. In **Code
evidence → Binding opinions & verification**, open the original records. Shared
records appear once with cross-reference buttons. The metadata panel's binding
index opens the same direct inspector. Executed static export never means that a
component or business was verified; original source versions remain visible after
rebinding to S1.

Repeat the local projection measurement (requires the reviewed baseline Git object):

```powershell
node examples/architecture_model/benchmark_projection.cjs temp/projection-performance.json
```

This compares the baseline's isolated visible-node/hidden-count loop with the new
shared projection for 100/200/400/800 fully expanded components on the same Node
process and input. It asserts equivalent node counts and edge references, and
records machine metadata. Milliseconds are observations, never a test threshold
or full browser performance claim. Node unit tests also check collapsed forests,
out-of-order parents and a deep chain without changing domain IDs.

The native Unicode regression exports actual LF/CRLF/CR files containing U+2028
and U+2029 inside a string, binds the returned function/file locations and checks
exact numbered contents. With the M1 tool variables set as above:

```powershell
uv run pytest tests/architecture_model/test_viewer.py -k native_unicode `
  --basetemp temp/m3-native-new -q
```

The fresh basetemp contains `test_native_unicode_facts_bind0/unicode.html`, its
real `facts.json`, `model.json` and source. Copy that HTML into a replay directory
as `unicode.html` before running check_viewer to check actual source visibility
and inert script-closing text. The browser script also checks `untrusted.html`
when supplied, as documented in the acceptance report. Preserve fresh output paths.
