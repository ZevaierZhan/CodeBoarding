# Read-only architecture and business flow explorer

Open [the included example](../examples/architecture_model/interactive/index.html)
in a browser, or generate a new offline document from your own complete model:

```powershell
uv run codeboarding-model model --file architecture-model.json export-html `
  --output architecture-view.html --source-root C:/path/to/project
```

`--source-root` is optional. Choose a new output filename on each export; existing
files are never overwritten. No provider, `.env`, server, CDN or implicit analysis
is required. The document contains the complete model and any matching source
snippets: share it only with readers who may see that information. The included
`interactive/model.json` is the persisted model behind the included document.

## Explore and play

1. Read the project boundary and model/revision. Use **Snapshots & model metadata**
   for exact source snapshot/version, latest maintenance target and export time.
2. Expand/collapse the **Project structure** tree or use **Expand all / Collapse
   all**. Select a component for its responsibilities, rationale and code evidence.
   Components are logical boundaries; their bound paths show actual directories.
3. Choose a business. Its entry step is selected independently of display order.
   **Business explanation** inspects the scenario itself. Step buttons inspect a
   step directly and start a fresh browsing path; this clears Back history.
4. **Play** follows explicit saved transitions. **Pause** stops the timer. **Step
   forward** follows a sole saved edge. For a branch, choose its labeled outgoing
   transition. Conditions are explanations and are never evaluated.
5. Loops pause automatic playback. Choose the loop to enter it, or a saved return /
   exit edge when available. **Back** follows the path actually browsed, including
   loops, and **Reset** returns to the entry step. An absent transition is reported
   as an endpoint or unexplained gap; no edge is inferred from list order.
6. **Focus business** dims unrelated architecture. Uncheck it to restore the full
   context. Collapse/focus preserve the current business and step. A collapsed
   ancestor says **Current step inside**; expanding recovers the original node.
   Switching A/B preserves each business's session position and shares component IDs.
7. Select component relationships below the graph for their meaning and claims.
   Teal dashed graph paths show outgoing/current traversed explicit transitions;
   gray paths show architecture relations. Coincident paths are display groups,
   with original references in their SVG titles and original choices still visible.

## Read evidence and review scope

The inspector keeps code_fact, inference and intent_hypothesis separate. Assumptions,
issues and human opinions remain independent. Verification details identify planned
versus executed, command, inputs, environment, version and actual result. An executed
check does not verify a broader business claim automatically.

Open a **Code evidence** disclosure for binding ID, snapshot, version, path, symbol,
line numbers and content hash. Export embeds a snippet only when the referenced
whole-file hash matches. Missing/changed sources or unavailable old bodies show a
reason and retain exact locations. History lists old bindings, not invented old
source or explanation text. No model-supplied link becomes executable HTML.

**Maintenance & review history** labels three independent dimensions:

| Label | Meaning |
|---|---|
| Current / Historical explanation | Whether the observation's content fingerprints match today's model definitions |
| Current pending / Historical pending / Review recorded | Membership in current_pending_ids / pending_ids and explicit resolution |
| Latest / Older target | Whether target_snapshot_id equals latest_target_snapshot_id |

Current coverage may target older source. A historical confirmation never means the
latest code was verified. Expand an observation for exact target version, reasons,
affected objects, author, rationale, timestamp and actual content fingerprints.
Unknown legacy coverage stays unknown. Unresolved older targets are retained.

## External Agent workflow

Read the original model through `model read` or scoped queries. Inspect code and
facts, then use normal expected-revision CLI patches to reuse existing IDs and
record explanations or session feedback as opinions. Apply source maintenance
through the existing preview/refresh/rebind/resolve protocol. Then call export-html
again with a new output path. The browser never writes the model; the generated
document is a revision snapshot, so it will not auto-refresh after external edits.

For the real-source, independent-process replay and browser check commands, see
[the continuous example](../examples/architecture_model/README.md#m3-offline-interactive-explorer).
Design and exact limitations are in [M3 design](design/architecture-model-m3.md).
