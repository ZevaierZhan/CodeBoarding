# Source roots and interface contracts

Keep MODEL as one system. Assign each repository/source root an enduring caller-chosen
ID, independent of its physical directory, URL, commit and language. Reuse it on
refresh and after moving machines. Different roots may have independent commits.
Legacy v1 snapshots represent the implicit single root `""`; continue them through
the legacy exporter or establish explicit new bindings with history. Never rewrite
old facts to manufacture a root ID or recompute their snapshot IDs.

Export each root using ENGINE's environment:

```sh
uv run --project ENGINE --no-sync python -m architecture_model facts export \
  --repo TARGET_ROOT --project-id SYSTEM_ID --source-root-id ROOT_ID \
  --tools ABSOLUTE_TOOLS_JSON --output NEW_FACTS_JSON
```

The tools JSON declares `tokei` argv and `lsp_servers` mapping language keys to
argv arrays. Executables must be absolute existing files. For TypeScript supply
`typescript_sdk` as the absolute engine-side `typescript/lib/tsserver.js`; use an
SDK supported by the language server. Java additionally accepts `jdtls_root`.
Tools are external prerequisites; the target never installs CodeBoarding. Missing
tools, LSP errors, empty non-Python symbol extraction, overlapping native projects
or omitted supported files fail publication. No dependencies are installed by
the exporter. Vue files are explicitly file evidence, never SFC symbol support.
Other unsupported suffixes are outside the declared scope; inspect limitations.

Before writing, query existing bindings by root ID AND path/symbol, and search
relations by mechanism/operation and both components. v2 call endpoints are exact
`path|native_symbol` catalog keys. Full identity includes source root, file language
and project recorded in that snapshot; a bare native name is never globally unique.
Copy exact locations from catalogs. File bindings may cite actual configuration
or registrations that static calls omit.

Use the existing stable Relation ID as the contract ID. Its optional `contract`
contains `mechanism`, `operation`, caller/receiver binding IDs, matching binding IDs,
`rationale`, `uncertainties` and status (`candidate`, `evidenced`, `ambiguous`, `missing`).
Both sides belong to their endpoint components and all contract bindings appear
in the relation claim. `evidenced` requires a code_fact claim, explicit matching
evidence and no unresolved uncertainties; this is an authored static judgement,
never an automatic promotion or runtime proof. Name/URL equality alone remains
a candidate. Capture registration, route prefixes, feature conditions and payload
assumptions; use inference with uncertainty when these cannot be established.
Scenarios list reused `relation_ids` to preserve contract impact explicitly.

Refresh one root at a time through maintenance-preview/refresh. Only bindings of
that root are compared. Other catalogs remain immutable; `maintenance_targets`
tracks roots independently. Pending relation/scenario observations describe review
status without overwriting authored contract text. Comparison is conservative at
whole-file granularity. Rebind explicitly, then resolve the exact review version;
history and previous confirmations stay saved. A failed or absent root supplies
no deletion evidence.

`maintenance_target_snapshot_id` is the legacy root's target only. Explicit roots
use `maintenance_targets[root_id]`. Query and HTML use these effective targets by
root; there is no global latest source version. Old M5 files may have a v2 scalar
alias: the reader maps it to that named root without writing. An overwritten
legacy target cannot be recovered reliably from snapshot order or review history;
the reader reports it unknown until an explicit legacy preview/refresh establishes
it. A normal successful refresh normalizes the old alias into the root map while
preserving all immutable facts and historical observations.

For a new Verification targeting a v2 component, step, scenario, model or relation,
declare `binding_snapshots`, mapping each actually checked binding ID to its exact
immutable snapshot ID. Those bindings must belong to the targets' referenced
evidence, and each pair must match current evidence or retained binding history.
Directly targeted bindings must be covered. Declare both sides only if both were
actually checked; use separate records for different checks. The required old
`source_version` is an anchor equal to one scoped snapshot's digest, never the
whole-system version. HTML resolves the complete binding/root/version scope.

A frontend-only executed source check may target the IPC relation but covers only
its declared frontend bindings. It remains partial, not bilateral/runtime approval.
Declare an unexecuted bilateral host check as planned. Reading an old unscoped
compound record preserves its actual fields/results and reports unknown scope;
editing that record into a new v2 check requires explicit scope. Legacy single-root
records still read. A direct binding record cannot name another root's version.
Neither source coverage nor a successful static check changes contract/claim kind.
After component boundaries change, retain old check evidence. The viewer marks
evidence outside today's membership historical and shows the new uncovered bindings;
do not rewrite an old execution to make it appear to cover the revised component.

Export ONE HTML with `--source-map MAP_JSON`, a JSON object mapping root IDs to
current physical directories. `--source-root` remains for legacy bindings only.
Mapping is local execution input, never persistent identity. Each historical and
current snippet uses its own snapshot's root and whole-file hash; missing old bytes
remain unavailable. Inspect both languages, shared contracts, switching scenarios,
collapse/expand and review state. Export and browsing are read-only.
