# M5 final follow-up: implicit binding evidence ownership

Review baseline: `f18fed3dff13ce9fe7f00056a965317d7893fbb3` in Draft PR #6.
Only `architecture_model/verification.py` changes production behavior. Existing
facts, maintenance targets, model revision 11, historical records and player assets
are unchanged.

## Red and green evidence

The regression uses real `ModelStore.apply()` with two valid frontend v2 catalogs.
Binding `frontend` (X) belongs to A, has no history, and its exact location/content
fact is absent from B. B has another source digest. Both catalogs coexist in the
same valid model. The unscoped check targets only X but names B's source digest.

Before the fix, apply committed revision 3 -> 4 and projection invented an
`implicit_direct_bindings` association to B. The second regression independently
loads that old record and rejects this invented association. Both tests failed
with pytest exit **1**, before production edits. See
[red.log.gz](../../examples/architecture_model/multilanguage/verification-attribution/red.log.gz)
and [red.exit.txt](../../examples/architecture_model/multilanguage/verification-attribution/red.exit.txt).

After the fix, the same apply returns `VERIFICATION_SCOPE`; original file bytes
and revision remain unchanged. Old records still load and serialize with their
saved fields, but the unknown association projects as `legacy_unscoped`, with no
evidence and X uncovered. The final replay of all P2 cases
passes **29 tests**, exit **0**. See
[green.log](../../examples/architecture_model/multilanguage/verification-attribution/green.log).

Run the regression from the repository root:

```powershell
uv run --no-sync pytest tests/architecture_model/test_m5_p2.py -k unowned -v -s --basetemp=temp/m5-attribution-repro
```

The fixture is deterministic; model IDs and temporary directories vary. Red output
is the actual pre-fix execution, not a reconstructed failure transcript.

## Final protocol

`binding_snapshots` remains optional; no schema or serialized field is added.
For each new/edited direct v2 binding check that omits it, candidate snapshots come
only from that binding's actual current entry and append-only history. Each entry
must match snapshot ID, source digest, complete location and the corresponding
symbol/file catalog fact. Filter those owned snapshots by `source_version` and
require **exactly one distinct snapshot ID**. Otherwise return `VERIFICATION_SCOPE`
and ask for an explicit map; explicit maps must themselves pass ownership checks.

A second unowned catalog with the same digest does not create a candidate. Two
actually owned snapshots sharing a digest are ambiguous: choose one explicitly.
Accurate historical A remains usable after rebinding to B. Corrupt/missing history
facts cannot establish ownership. One shared resolver handles explicit ownership,
implicit submission and HTML projection.

Strict inference applies to new/edited records. Reading old unscoped records and
unrelated edits preserve their saved fields/results. Unproven or ambiguous scope
is unknown, not fabricated precision. Legacy v1 single-root writes retain their
compatibility path; v1 projections also require proof before naming a snapshot.
Explicit bilateral/partial scopes and compound scope requirements remain intact.
Neither source scope nor successful static evidence constitutes runtime/business
proof; planned checks remain planned.

## Validation and limits

Results on Windows / Python 3.12.13 / pytest 8.3.5:

| Check | Actual result |
|---|---|
| M1–M5 architecture-model suite, real tools enabled | 219 passed in 420.84 s |
| Module coverage, unchanged 80% threshold | 95.09% (1433 / 1507 statements) |
| Final P2 selection (overlaps the full suite) | 29 passed in 12.81 s |
| Node player tests | 7 passed |
| Repository Black / mypy | Passed, 377 Python sources |
| Chrome/Playwright ownership and original playback | Passed, no JS errors |
| Fresh Python v1 export | 2 symbols / 1 call |
| Fresh TypeScript / Rust / mixed exports | 3/2, 3/1, 6/3 symbols/calls |

Raw logs and browser receipts are in
[verification-attribution](../../examples/architecture_model/multilanguage/verification-attribution/).
The new ownership cases cover create/edit rollback, current and historical A,
unowned duplicate digests, owned duplicate ambiguity with explicit disambiguation,
invalid history ID/version/location, old serialization and exported HTML. Existing
P2 cases retain explicit frontend/backend and partial checks and legacy targets.

Chrome/Playwright verified visible unknown evidence, uncovered frontend, planned
state and the runtime-proof notice. Existing cross-language playback, shared
contracts, collapse/back/scenario switching and read-only model bytes also pass.
Java/Vue capability was replayed against the committed real native facts: Vue is
file evidence only and HTTP stays candidate. This is not a fresh Java export.

The previous full-suite classification is unchanged: 89 baseline failures, 33
environment/prerequisite cases, zero identified PR regressions, zero unclassified
causes. Of these, 29 Kotlin cases remain blocked before their later assertions.
The original full-repository coverage **38.57%** remains below the unchanged **80%**
gate. The private integration suite was not run. No new full-repository run is
claimed for this narrow correction.
