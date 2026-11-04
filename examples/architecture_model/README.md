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

The [protocol](../../docs/architecture-model.md#m2-source-maintenance) documents
commands, strict review JSON, M1 compatibility and failure semantics. Extend the
M1 test command above to include all M2 regressions in the same directory.

Real worker API checks run in a child process and assert that the pytest parent's
configuration, environment and native module state are unchanged. `.coveragerc`
enables subprocess measurement so those checks remain part of coverage. Additional
explicit-tool tests simulate another installation under a temporary home, check
the actual Node/argv markers, and reject failed Tokei/Pyright executables without
publishing facts or changing the model.
