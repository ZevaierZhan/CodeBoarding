# M6 compatibility: analysis topics and lossless evolution

## Baseline and investigation

PR #8 was merged before development. Base: `deebabf9030eadbf0a4f1e73218a822d268fcbf5`
(fork `origin/main`). This work does not include M6-B orchestration.

Read-only structural inspection of the private revision 9 and revision 38 models
found exactly three unsupported field paths:

| Path | Observed type | Meaning |
| --- | --- | --- |
| `/scenarios/*/analysis_kind` | `operation` or `comparison` | Execution flow versus independent explanatory topic |
| `/scenarios/*/facet_order` | string array, sometimes empty | Authored display order of analysis questions |
| `/scenarios/*/steps/*/facet_checks` | string-to-string mapping, sometimes empty | Question label to authored mechanism explanation |

Both models have 15 scenarios (9 operations, 6 comparisons). Revision 9 contains
79 explicit facet maps with 88 entries; revision 38 contains 76 maps with 75 entries.
All comparisons have no execution transitions. Every nonempty check key is declared
in its scenario's facet order. Labels are local keys, not global object IDs. Values
contain prose, not machine-readable execution status or Verification references.
There are no other Pydantic schema differences. Model identity and schema version
are shared; the complete IDs and private reports remain outside the public repository.
Observed facet-order lengths are 0 or 9. Check-map sizes range from 0–6 in revision 9
and 0–3 in revision 38, with nonempty string answers. Every scenario declares its
kind/order and every step declares its map. The two revisions share the same field
structure; the authored content and step inventory differ.

The protocol originates in local development commit `76fab0fb522c154a9ad2e043a8a1ffb578607d4b`
on `codex/business-permission-matrix`, then documented by `88c184a1` and used by an
external modeling script. It was an implemented branch-local convention, absent
from main, rather than an unknown enterprise data envelope. No private facet names,
policy rules, paths, facts or source digests are included here.

## Decision

| Option | Compatibility and costs |
| --- | --- |
| A: typed optional fields | Direct lossless reads, existing IDs and patch surfaces; small validation/viewer change; domain-neutral question labels |
| B: versioned extension envelope | Useful for independently owned protocols, but existing fields would require migration or duplicate representations; more Agent negotiation |
| C: separate presentation artifact | Appropriate for layout preferences, but loses authored explanations from diff/review fingerprints unless a new lifecycle is built |

Choose A. These fields describe general architecture interpretations already owned
by scenarios and steps. A closed enum, string arrays and `dict[Text, Text]` express
their actual structure without importing enterprise logic or allowing arbitrary JSON.
Keep `extra="forbid"`. Unknown kinds, fields, types and facet references fail explicitly.

## Protocol and versions

This is an additive optional extension of model schema 1, without a migration.
Presence of the typed fields declares use of the capability; `model schema` advertises
support. Older engines reject these fields. New Agents inspect schema before use
and request a compatible engine on failure, preserving the original file.

Absent fields mean `operation`, empty facet order and empty check map. Serialization
omits absent defaults but retains explicitly supplied defaults, including empty maps.
This preserves both old serialization and authored extension presence. No file is
rewritten by validation, read, diff or export.

`order` is the complete step display order, including for comparisons. The required
entry step of a comparison is an initial inspection anchor only. Comparisons reject
execution transitions. `facet_order` contains unique, nonempty question labels;
every check key must reference a declared label in its enclosing scenario. Missing
entries mean unexamined/unknown. Checks use the step claim and evidence bindings;
they are authored explanations, never executed checks. Verification remains a separate
record with its existing scope and provenance requirements.

Patches merge top-level object fields. Supplying `steps`, `facet_order`, `facet_checks`
or other nested fields replaces that entire field. Preserve continuing step IDs,
transitions and unrelated values when replacing arrays. A label rename requires
updating all referring keys in the same validated patch. Labels have no independent
stable IDs; steps and scenarios retain their established IDs.

All meaningful topic content participates in diff and object coverage fingerprints.
Only semantic defaults are normalized for fingerprints, matching the originating
branch's `objects-v1` rules and the pre-extension shape. Stored observations,
resolutions and their fingerprints remain immutable; explanation changes append new
coverage observations through the existing machinery. Unknown data and failed or
conflicting writes leave model bytes unchanged through existing atomic commits.

## Delivery and acceptance

Implementation includes the strict schema, reference/kind invariants, default-preserving
serialization, normalized interpretation fingerprints, the existing M3 viewer and
the portable modeling Skill's schema negotiation and bounded-context workflow.
The complete synthetic fixture and reusable acceptance/browser scripts live in
`examples/architecture_model/schema_compat/`.

### Isolated real-model acceptance

Both original private models were copied, with original SHA-256 values recorded in
private acceptance reports. Standard CLI commands operated on complete copies,
including all extension fields. No projection or migration was used.

| Check | Original revision 9 | Original revision 38 |
| --- | --- | --- |
| Complete validate and round-trip | Pass | Pass |
| Original model ID and every object ID | Preserved | Preserved |
| Read/validate/diff/export leave bytes unchanged | Pass | Pass |
| Coverage report with actual source map | Pass: 3 roots | Pass: 3 roots |
| Existing facet update in copy | Revision 9 → 10 | Revision 38 → 39 |
| Expected revision, diff and affected scenario | Pass | Pass |
| Facts, bindings/history, prior revisions and checks | Preserved | Preserved |
| Historical maintenance records | 0 retained | All 66 retained; 26 new content coverage records appended |
| Pending before edit | 0 | 20 total, 13 current |
| Original file hash after acceptance and browser | Unchanged | Unchanged |
| Current binding bodies match supplied source | 81/81 | 72/72 |
| Historical bodies | None | 2 mismatches correctly withheld |

Coverage results describe physical overlap under the supplied mappings, not automatic
cross-root reconciliation: 46 confirmed same-version overlaps in the first model,
6 in the isolated model. Root targets, resolutions, rebind history and Verification
payloads are unchanged. No runtime behavior was executed or re-verified by this work;
interpretation review remains outstanding where the saved maintenance state says so.

Real file-only evidence includes the terminal empty line of newline-terminated files.
The viewer now accepts that actual line after checking exact bytes; it still withholds
hash mismatches and genuinely out-of-range bodies. No fact range, ID or digest changes.
LF, CRLF and CR tests cover this boundary and reject an extra nonexistent line.

Chrome/Playwright checks cover the exported original and updated copies: topic
playback disabled, independent inspection, operation switching, branches and Back,
ordered facet answers and missing-answer labels, component hierarchy folding,
source disclosures and claim-kind rendering. Node tests retain loop/return/history
coverage. Screenshots and all private data remain outside this repository.

### Validation and remaining limits

Final automated measurements are recorded below when the final run completes.
The initial broad run had the five documented Windows/bashed-path baseline failures,
plus a 60-second bounded-context subprocess timeout under concurrent acceptance load.
All 10 context tests passed on isolated rerun. No timeout, threshold or test was weakened.

The UI mechanical detector ran on the unexpanded HTML template, where embedded CSS
placeholders are unresolved. It reported default black text and flat 16px headings;
the exported, styled HTML was separately inspected in Chrome. The existing design
sidecar is stale; updating that unrelated artifact is outside this compatibility change.

M6-B can consume legal complete models without stripping topic fields. Automatic
root coordination, fact regeneration, a new rendering engine and internal Agents
remain outside this change.
