# M6-A: file inventory and independent source coverage

Base: fork `main` at `8d9060d79dfc019f6374fda06ccef8e3c1c95b3c`, fetched before development.
Branch: `m6/source-coverage-reconciliation`. M1–M5 and Q1 remain the baseline.

## Plan and scope

Reuse Facts v2, SourceVersion's SHA-256 manifest, string-valued tools metadata,
immutable snapshots and root-isolated maintenance. Add provider-free inventory,
read-only physical overlap reporting, descriptor diagnostics, synthetic acceptance,
private isolated acceptance, focused Skill guidance and regression evidence.
No automatic merging, root deduplication, cross-root rebind or new agent logic.

The available private acceptance record confirms a formal revision 9 and an
isolated revision 38 with 20 historical pending observations. It identifies missing
file-only scope and extractor fingerprint changes. Private sources, models and
filename lists stay outside this repository; only aggregate results belong here.

## Protocol decisions

`file-inventory-v1` extends the accepted maintenance descriptor protocol names;
its shape reuses `ExtractionScope`. Descriptor equality is required within a root
before maintenance can infer absence. Rules and implementation hash participate in
the immutable facts ID. No old facts or schema defaults are rewritten.

Physical range is the root-relative manifest plus an explicit local mapping.
Machine paths are observation inputs, not stable root identity or snapshot content.
The exporter intentionally ignores no implicit gitignore files: default directory
exclusions and caller patterns are explicit in the descriptor. Patterns use
case-sensitive fnmatch over POSIX paths (star includes slash); excludes also prune
directories. Ignored subtrees are outside scope. Non-ignored links, junctions,
special files, access failures, limits and source changes fail without publication.
Two streaming hash inventories compare bytes and file metadata. Limits are 100000
selected files, 500000 directory entries and 256 MiB per file. Publish outside the
source root to keep generated snapshots out of their own inventory.

Inventory proves raw file hashes, not functions, calls or runtime behavior. Its
language is `unclassified`; absence of symbols never means absence of code.
Selection completeness never implies semantic analysis completeness.

`source-coverage-v1` is a derived read-only JSON report, not a new model schema.
It selects one snapshot per root: explicit selection/target first, recorded root
maintenance target next, otherwise the sole snapshot. Multiple unselected snapshots
remain unknown. The catalog has no implicit chronological ordering.
Mappings must be existing absolute local directories. Manifest paths are portable
POSIX paths; links and junctions are rejected. Physical overlap uses local device /
inode identity (resolved canonical path when inode is unavailable), never file
names or equal content. Different saved hashes on one physical file remain separate
versions. Live hashes can identify roots needing re-export; matching saved files
does not check additions or declare the full scope fresh.

File content agreement, evidence scope synchronization and architecture review
are distinct report fields. Scope synchronization is not established by overlap.
Review is not established by a coverage report even when pending is empty. Saved
root maintenance targets and historical pending IDs are reported independently.
Unknown or invalid descriptors stay unknown/unsupported in coverage reports.

## Extractor changes and explicit baseline recovery

Maintenance still reports `indeterminate` when recognized extraction descriptors
differ or are absent. Malformed/incomplete or unknown-protocol descriptors retain
the existing `COMPARISON_INVALID` failure; coverage labels them unsupported rather
than claiming a comparable scope. Diagnostics name implementation, tools, rules/protocol and individual
configuration differences. An extractor change alone does not invalidate the
explanation and never implies source deletion. Export a new immutable snapshot
under the intended tools/rules; preview and refresh **that root**; inspect source
and candidate evidence, explicitly rebind selected bindings, then resolve each
interpretation with its exact target version. Preserve old snapshots, history,
reviews and pending records. Subsequent exports under the same descriptor can be
compared to this explicit baseline.

## Validation and delivery

Implemented: `facts export --file-inventory`, repeatable include/exclude rules,
two-pass streaming export, `model coverage-report`, optional proposed target facts,
explicit snapshot/root filters, per-root target/descriptor/pending observations,
physical overlap groups, live/saved version comparisons, affected evidence and
interpretation IDs, bounded Skill report queries and explicit baseline guidance.
The model envelope, Facts schemas, root target resolution and transactional
maintenance operations retain their existing serialization and meanings.

Reproduce real TypeScript acceptance using
`examples/architecture_model/source_coverage/acceptance.py --tools LOCAL_TOOLS --output NEW_DIRECTORY`
under `uv run python`. The public sample has four files, actual native analysis
finds three symbols and two static calls, and three physical overlaps are confirmed.
After changing only the rule, native-only refresh produces one divergent saved
file. Explicit inventory refresh restores content agreement; pending interpretation
reviews remain. A real inventory rule change with identical selected file hashes
is indeterminate; explicit baseline rebind/review succeeds and keeps prior pending.
See `acceptance-summary.json` next to the script; large raw artifacts stay in temp.

New exporter/coverage tests: **31 passed, 1 skipped**. The skip is unavailable
Windows symlink creation; an actual Windows junction escape test passes. Other
cases cover different physical directories with identical bytes, hardlinks,
missing mappings/files, unsafe Windows/POSIX/UNC paths, bounded queries, unknown
descriptors, rule/tool changes, publication errors/limits, source edit/add/delete
during scanning, CR/LF chunk boundaries, root isolation and byte-for-byte read-only
reporting. No existing test or threshold was relaxed. Native imports/providers
remain unloaded during inventory export.

Initial broad M1–M5/native/Q1 focused run: **420 passed, 5 skipped** in 246 seconds,
with existing native Python, TypeScript and Rust tools enabled. Subsequent
maintenance/Skill regression: **109 passed, 1 skipped** before four additional
newline cases. Node business player: **7 passed**. `uv run black .`, `uv run mypy .`
(386 files) and the Skill validator pass. No `.env` exists; these tests and explicit
local static exports require no provider credentials. No Kotlin installation or
grammar downloads were performed.

First full command `uv run pytest --cov=. --cov-report=term --cov-fail-under=80`:
**2928 passed, 5 failed, 64 skipped; 39.37% coverage**, so the full gate fails.
All five failures independently reproduce against an archive of the exact base
`8d9060d…`: four existing Windows tool-installer assertions and the devcontainer
bash/path assertion. The historical sixth intermittent cleanup failure did not
reproduce. The final full run, with native tool probes enabled and the complete
new test set: **2950 passed, 5 failed, 55 skipped** in 474.21 seconds. No new
failure appeared. Full coverage and module percentages are recorded in the
machine-readable `validation-summary.json` next to the public acceptance script;
the 80% whole-repository requirement remains unmet.

## Private acceptance: measured results and unresolved compatibility

Both private original model files remain byte-for-byte intact: formal revision 9
and isolated revision 38. **Complete original-model acceptance is not complete**:
these files carry scenario/step extensions `analysis_kind`, `facet_order` and
`facet_checks` that this fork's current main schema rejects. Accepting them would
require a separate schema/compatibility decision; silently dropping them in the
product or widening the public model is outside M6-A.

For explicitly limited diagnostics only, private isolated projections omit those
extensions and retain all facts, bindings, maintenance records, reviews and
verification records. Projection reports do not constitute complete-model
validation or current interpretation-review validation. Their saved 20 historical
pending observations remain unchanged. No projected model replaces an original.

Measured facts coverage:

| Projection and mapping | Physical overlaps | Saved versions | Historical pending |
| --- | ---: | --- | ---: |
| Formal revision 9, original roots | 46 | 46 agree | 0 |
| Revision 38, focused-copy mapping | 6 | 6 agree | 20 |
| Revision 38, canonical original physical paths | 46 | 45 agree, 1 differs | 20 |

The focused copy is physically distinct; identical bytes do not make its 40 files
overlap the original full-repository root. The canonical mapping instead compares
the saved catalogs at the original physical paths and reports the saved version
disagreement; it does not claim the modified native snapshot matches live source.
The file-only historical root remains missing maintenance_scope in every case.

A new provider-free inventory of the actual source tree selected **16169 files**,
with explicit default exclusions and no source text in stdout. Initial measurement:
49.02 seconds and 10.7 MB snapshot. Final projection timings/output sizes are in
the sanitized `private-acceptance-summary.json`; all detailed reports, copied
models and enterprise filenames stay in the private acceptance workspace.

## Remaining work and next-stage candidates

- Resolve the private scenario-extension compatibility separately, then rerun the
  complete original-model validation and review semantics. The current projection
  diagnostics are an explicit limitation, not a substitute for that acceptance.
- Existing whole-repository failures and the 80% coverage gap remain open.
- A report observes local filesystem identity at a point in time. Matching saved
  files does not detect additions or certify extraction or runtime completeness.
- Scope synchronization between different extractors is deliberately unproven;
  Agent inspection and root-specific exports/reviews remain explicit decisions.

No M6-B implementation, automatic cross-root reconciliation or merge is included.

## P2 reliability correction (review baseline e93dc733)

The two regression commands exercise real ModelStore transactions and validation:

```powershell
uv run pytest tests/architecture_model/test_source_coverage.py -k "unavailable_historical or separates_latest" -q
uv run pytest tests/architecture_model/test_source_coverage.py -q
```

Before the fix, both valid historical statuses (`missing` and `changed`, with a
reason and an unavailable snapshot) failed at `catalog[binding.snapshot_id]` with
`KeyError: 'unavailable-snapshot'`. The model validated successfully first. A
separate invocation through the real CLI dispatcher with the baseline coverage
function produced the same unhandled exception. The second reproduction recorded
two targets on the same component and explicitly rebound/reviewed the newer one:
the old report retained one undifferentiated pending ID and exposed no current or
historical classification. The initial regression run failed all three cases.
Sanitized evidence is in `examples/architecture_model/source_coverage/p2/`.
The committed `p2/negative-model.json` retains the valid ModelStore negative
fixture. Runtime before/after hashes and the portable LF fixture hash are in
`reproduction-summary.json`. Validate it with
`uv run codeboarding-model model --file examples/architecture_model/source_coverage/p2/negative-model.json validate`.
Run its `coverage-report` with `--source-map` pointing to `p2/empty-mapping.json`
and a new `--output` path. On the review baseline this raises the recorded
KeyError; after the fix it returns the structured report in `negative-report.json`.

Coverage now omits unavailable binding snapshots from the root/path index and
descriptor comparisons. Top-level `unattributed_bindings` records contain
`binding_id`, `snapshot_id`, original `status`, `attribution: unknown` and
`reason: snapshot_unavailable`; the summary includes their count. These bindings
are never inferred from paths, names, digests or local mappings, and never enter
file overlap or affected-binding sets. Unattributed entries remain visible even
with a root filter, since the report cannot determine their membership. Valid
roots continue to be analyzed. Current bindings with unavailable snapshots and
non-current bindings without reasons still fail the existing model validator.
There is no schema or historical-data repair.

All review observations and interpretation-version coverage come directly from
M2 `maintenance.query()`, which already uses `maintained_observations()` and
`capture_coverage()`. The report applies only a root/latest-target partition to
that result; it does not implement another object-version or review algorithm.
For each root, let `C` be M2's current interpretation coverage IDs restricted to
the root's latest **recorded maintenance target**, `P` all M2 pending IDs for
that root, and `R` its explicitly resolved observation IDs:

| Root field | Meaning |
| --- | --- |
| `latest_recorded_maintenance_target` | Existing root-target resolution, including supported legacy scalar targets; empty means unknown |
| `current_coverage_ids` | `C`; an old target may still have current object coverage in M2 but belongs to history in this root/latest-target view |
| `current_pending_ids` | `P` intersect `C` |
| `historical_pending_ids` | `P` minus `C`, including earlier source targets and earlier interpretation versions |
| `resolved_ids` | `R`, all explicitly completed reviews |
| `historical_resolved_ids` | `R` minus `C` |
| `pending_ids` | Compatibility aggregate `P`; includes M2-derived observations rather than only persisted records |
| `unassessed_binding_ids` | Attributed root bindings without coverage in `C` |
| `review_coverage_status` | `unknown_target` if no root target is recorded; `unknown_coverage` if current target coverage is absent/incomplete; otherwise `established` |

`established` describes the coverage relation, not successful review: inspect
`current_pending_ids` separately. Empty pending with unknown coverage never
certifies review. An explicitly selected old or proposed snapshot affects file
comparison only, not the recorded maintenance target or this review partition.
`architecture_review` remains `not_established_by_coverage`. Matching target IDs
alone do not prove that current interpretation objects were reviewed.

Compatibility is additive within the derived `source-coverage-v1` report. The
model envelope, Facts, bindings, Verification and Maintenance schemas and M2
query semantics remain unchanged. `pending_ids` remains the all-pending union;
consumers needing current counts must use the new partition and unknown status.
The bounded CLI envelope still returns only summary and output path. The M4
coverage helper additionally pages `unattributed_bindings`; root/file/overlap
pagination is retained with the same size limit.

The extended public acceptance runs actual TypeScript analysis and verifies:
3 overlaps; 1 saved-version difference after native-only refresh; 3 agreeing
overlaps after explicit inventory refresh; retained historical pending after
latest-target rebind/review; zero latest-current pending at that point; new
latest-current pending after an explicit interpretation edit; unchanged old
reviews, facts, bindings and Verification. Each of five coverage phases checks
full model equality, exact bytes, SHA-256 and revision before/after. The public
acceptance summary includes those five paired hashes and revisions.
The additional read-only checks exercise legacy scalar target selection and
virtual interpretation edits without a ModelStore commit: newly derived pending
IDs match M2, while both the input model object and file bytes/revision stay intact.

Private compatibility remains a separate unresolved issue: formal revision 9
and isolated revision 38 carry `analysis_kind`, `facet_order`, `facet_checks`
extensions rejected by the public schema. A separate decision must specify the
supported scenario/step extension schema, versioning/migration policy and
round-trip preservation before complete original-model acceptance can be claimed.
This correction does not open, rewrite or project either private model. Previous
projection diagnostics remain explicitly partial and are not full acceptance.
No Kotlin installation, optional-dependency change, M6-B work or model protocol
expansion is included.

Final P2 validation: **2957 passed, 5 failed, 55 skipped**, with **40.57%** full
coverage against the unchanged **80%** requirement. All five failed test IDs match
the independently recorded baseline (four Windows installer assertions and one
devcontainer bash/path assertion); there are no new failures. The full-run
M1–M5/model and Q1 path/cache subset is **337 passed, 5 skipped**, with its exact
module list in `p2/validation-summary.json`. The dedicated exporter/coverage run
is **38 passed, 1 skipped** (Windows symlink privileges; real junction rejection
passes). Node **7 passed**; Black and mypy **386 files** pass, as do pre-commit
hooks. Coverage module coverage is **93.70%**, inventory **93.33%**. Full logs and
JUnit results are archived under `p2/`; the earlier baseline results remain
separate in the parent `validation-summary.json`. No test skip, threshold or
coverage omit was added to hide the existing full-repository gate failure.
