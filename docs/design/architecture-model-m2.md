# M2 implementation design

M1 is merged in fork main at d265acc5, including reviewed df5b6920. M2 branches
from that main and targets main. P0 experiments and M1 history remain intact.

## State and comparison

`binding.current` means correspondence to its own immutable saved snapshot.
Refresh does not advance bindings or explanations. Each comparison stores a
binding's original evidence, target snapshot/version, model revision, disposition,
reasons, candidates and affected component/relation/scenario/step identities.
`unchanged` needs no business review; changed/missing/ambiguous/indeterminate stay
pending until an explicit version-specific Agent resolution. Each binding is
compared against its own snapshot, never a global baseline. Earlier pending
comparisons survive subsequent targets, including unrelated changes and reverts.

Comparison is conservative at **file byte hash** granularity. Line positions and
static incident calls are reported separately. Matching names are candidates,
never implicit relocation. Multiple plausible replacements remain ambiguous.
Global source digest differences alone do not imply business changes.

New facts retain the M1 facts schema and carry a canonical extraction descriptor
in tools metadata: discovery implementation hashes, effective ignore patterns,
engine configuration/tool hashes and completeness declaration. The descriptor is
checked before and after extraction. Old snapshots remain content/digest compatible;
absent or different descriptors yield indeterminate, never deleted. Export errors
publish nothing. An independent strict inventory rejects traversal/stat/read errors
and native discovery disagreement. A complete comparable export can establish
missing evidence.

## Operations and compatibility

Add an optional strict `maintenance` collection to the existing v1 model envelope.
Existing M1 files load with an empty collection; the first successful write saves
it. IDs, revision, explanations, histories and immutable facts remain unchanged.
Old M1 binaries reject the new field; use the M2 reader after writing M2 state.
No historical fact snapshots are upgraded or rehashed.

`model maintenance-preview --facts FILE` is read only and returns its model
revision plus a reproducible preview token. `maintenance-refresh` requires that
token and expected revision, recomputes within the existing lock and atomically
imports facts and appends observations. Repeating a target adds no duplicate facts
or observations; a successful no-op consumes one revision, matching M1 apply.

`maintenance-rebind` explicitly selects a stored candidate, appends M1 binding
history and retains the binding ID. It leaves review open. `maintenance-resolve`
records confirmed/revised, author, rationale, exact target version and affected
objects; optional ordinary interpretation operations commit in the same revision.
Revised requires an actual interpretation change. No general patch can edit or
erase maintenance records. Read/query supports binding/component/scenario scope.

## P2: model evolution and review coverage

The source comparison key is independent of review coverage. `objects-v1` adds an
ID-indexed map of SHA-256 hashes of the complete affected component, relation,
scenario and step definitions. Observation identity includes the map. The review
unit is conservatively the whole affected set: new shared B or a changed related
definition creates another context, while unrelated edits and model revision alone
do not. Exact unchanged/reverted contexts reuse their existing state.

All candidate writes derive the current context for every known historical source
comparison, atomically with ordinary explanation edits. Read/preview/query use the
same helper. Historical observations and resolutions retain their original object
sets and content hashes. Current coverage IDs and current pending IDs are exposed
separately from all pending history. Confirming old coverage never closes new
coverage. Resolve patches require current context and record the resulting state
as reviewed in the same transaction; historical confirmations are not overwritten.

Legacy M2 observations lack hashes. Preserve them unchanged as coverage-unknown;
derive a new current context, persisting it on the next successful write. Do not
invent historical content coverage or rewrite any fact catalog. Rebinding uses the
same snapshot/version/location triple as M1 history protection, including recovery
when only a non-current binding's declared source version differs.

All writes use ModelStore candidate validation and its same read/check/build/
validate/replace critical section. Stale previews conflict before any write.
New errors distinguish incomparable evidence, invalid preview, candidate selection
and review protocol errors. Post-commit output failure retains M1 exit 2 semantics.

## Acceptance

Extend the real Python fixture in temporary copies and run each CLI operation in
a separate process: unchanged exports; shared A/B changes; unrelated file changes;
line movement and same-file conservatism; rename/move and ambiguity; deletion;
S0→S1→S2 pending retention; explicit rebind and confirm/revise; fresh export;
failed export/scope uncertainty; stale preview and atomic failures. Preserve the
M1 assertions, provider/native guard and repository coverage threshold. Record
baseline failures, environment limits and unattributed results separately.
