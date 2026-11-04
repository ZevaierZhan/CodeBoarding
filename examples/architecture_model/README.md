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
