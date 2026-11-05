# M5 P2: verification scope and independent maintenance targets

Review point: `1f165caa0fccbaaf700c9af96159367c21bf06bd`. Base main:
`4f73e07c46b21a1fc96426b4be9bf9ff96e8a7dd`. This follows up in fork Draft PR #6;
it preserves the M5 model and does not start another milestone.

## Reproduction and fixes

The first three regression tests ran before production edits: **3 failed**. The
old validator accepted a frontend binding verification anchored to the backend
digest, accepted an unscoped two-root relation check, and v2 refresh replaced a
valid legacy maintenance target with a named-root target. The saved red output
is supplemented by independent CLI runs against the exact review source archive.
Both malformed verification patches committed on that old code. Fixed CLI rejects
both with `VERIFICATION_SCOPE`, retaining identical file SHA-256 and revision.

A second live fixture uses three **real Pyright v1 exports**, plus real native
TypeScript and Rust exports. It keeps an older confirmed Python observation and
a newer pending one. The old CLI changes scalar target L to frontend target R and
renders L as older. Fixed frontend then backend refreshes keep L and its pending /
confirmed observations unchanged, and retain both named-root targets. The before /
after query reports and three HTML documents agree on latest/older labels.

## Verification protocol

The model envelope remains v1. Verification adds optional `binding_snapshots`:

```json
{
  "id": "ipc-check",
  "status": "planned",
  "object_ids": ["read-file-ipc"],
  "command": "exercise the desktop host against the declared sources",
  "environment": "host required; not executed",
  "inputs": "frontend, Rust command and registration",
  "source_version": "FRONTEND_DIGEST",
  "binding_snapshots": {
    "invoke": "FRONTEND_SNAPSHOT_ID",
    "command": "BACKEND_SNAPSHOT_ID",
    "registration": "BACKEND_SNAPSHOT_ID"
  }
}
```

The placeholder digest above must be a real 64-hex content version in actual input.
The map gives each actually checked binding an immutable snapshot. Roots and
content versions come from those catalogs, so independent repositories need no
common commit. Each pair must match the binding's current evidence or retained
history; history can keep an earlier executed check valid after rebinding. Unknown
bindings, unrelated target evidence, unavailable snapshots and mismatches fail.
Every directly targeted binding must be included in an explicit map.
Later component membership edits do not rewrite a historical check or force it to
cover the new boundary. Its saved source pairs stay valid; HTML labels evidence
outside today's reference closure `declared_historical`, lists those bindings and
the uncovered current bindings. New/edited checks must still belong to their current
targets. Referenced evidence bindings themselves cannot be silently deleted.

The required old `source_version` remains a compatibility anchor: for declared
scope it must equal at least one mapped snapshot's digest. It does not summarize
all roots. A direct binding's implicit version must belong to that binding's root,
including retained historical roots. New checks cannot guess an unavailable root.

New/edited compound checks whose referenced evidence includes v2 bindings must
declare scope. Reference traversal covers component descendants, relation endpoints,
scenario steps/relations and step components. A source-only check may cover a
subset. A whole root map is not inferred merely because a check targets a contract.
Ordinary read still accepts old unscoped compound records and preserves all their
actual inputs, results and versions; their evidence coverage is **unknown**. Empty
new fields are omitted on serialization, preserving old Verification shapes.
Single-root v1 reads/writes retain compatibility. Unknown fields stay forbidden.

HTML displays the record's targets, declared evidence, root/version tuples and
uncovered binding IDs. `declared_referenced_evidence` means all currently referenced
source evidence was named, not that business behavior ran. A frontend-only check
is `declared_partial`; an unscoped historical compound check is `legacy_unscoped`.
Neither source coverage nor result status promotes a claim or contract. Planned
checks still forbid execution fields; only actual executions get executed records.

The canonical example is revision **11**. Its two additions are an **actually
executed frontend file-hash/IPC-literal check**, explicitly partial for the IPC
relation, and a **planned** bilateral host check. All revision-10 catalogs,
bindings, interpretations, scenarios and maintenance records compare exactly
equal. The IPC remains candidate. See the example's `p2/verification.patch.json`,
execution output, CLI responses and preservation check.

## Maintenance target compatibility

`maintenance_target_snapshot_id` now means the latest **legacy root** target.
`maintenance_targets[root_id]` means the latest target for that named root.
There is no whole-system latest source target. Refresh changes only its root and
still uses preview tokens, expected revision, lock, candidate validation and atomic
replacement. Preview remains read-only. Facts and historical reviews are untouched.

`root_targets()` supplies effective targets for query. Mixed-root query includes
`latest_observation_ids`; HTML uses that result rather than reinterpreting a
global scalar. Pure-v1 report shape remains compatible. The inspector separately
labels legacy and explicit targets.

Old M5 files may contain a v2 scalar alias. Read recognizes its snapshot's root
and uses it only as a fallback for that named root; an existing root-map entry wins.
It never treats that scalar as legacy. If legacy facts also exist, the unavailable
legacy target is explicitly reported unknown. Snapshot insertion order, review
context timestamps and history cannot reliably reconstruct an overwritten target,
so none is guessed. Explicit legacy preview/refresh establishes a new valid target.
Such observations are labeled `target latestness unknown`, not incorrectly called
older. Query supplies `unknown_target_observation_ids` for that distinction.
The next successful refresh normalizes the old named alias into the map and keeps
the scalar legacy-only. Reads do not migrate/write the model.

## Regression attribution and gates

The evidence directory contains all **122 original node IDs and failure types**,
paired clean-source main/review-head results, JUnit XML, raw compressed logs and
diagnostic timeout stacks. Both source archives are generated from exact Git refs;
both use the same engine venv, Python 3.12.13, pytest 8.3.5 and host tools. These are
clean source archives, not Git checkouts with separate `.git` state. No tests or
assertions are changed in either control. File groups have a 150-second diagnostic
budget; blocked groups are retried individually with a 35-second budget and
15-second faulthandler stack dumps. Those budgets produce blocked outcomes, never
passes. Exact selectors are retained, including the two multiline Kotlin parameters.

Completed comparison classification and final checks are recorded in the
accompanying evidence summary. Baseline classification requires the same failure
type **and normalized failure message**, not just two nonzero exits. Normalization
removes randomized fixture IDs, addresses and actual timer samples; it retains the
timing threshold. Kotlin grammar-loader blocks are environment cases, with their
post-setup assertions explicitly unverified. This does not establish that all native
logic would pass after tool restoration.

| Original failure classification | Count | Evidence |
|---|---:|---|
| PR-introduced assertion regression observed | 0 | No clean-main pass / review-head fail pair |
| Baseline-existing | 89 | Same test, failure type and normalized failure message |
| Environment / prerequisites | 33 | 29 Kotlin grammar-loader/download blocks; 1 Windows symlink privilege; 1 unavailable Bash/WSL; 2 pass in both clean archives |
| Unattributed failure cause | 0 | All 122 original names and exception types are accounted for |

The two clean-archive passes are package inventory and Python encoding scans:
the original workspace included ignored `temp/` content. The historical encoding
run also saw a transient transcript arrow that was already fixed before the review
head. Package ghost declarations still reproduce on main; they are not called
environment passes. Many baseline failures are Windows path/URI assumptions,
mocked tool paths or timer behavior. Those unrelated issues are left intact.

Original failure types: 61 AssertionError, 29 ValueError, 29 chained
tree_sitter_language_pack.DownloadError, 2 DotnetSdkError, 1 OSError. Full original
and paired errors are in `p2/evidence/failure-classification.json`; raw logs, XML,
incremental reports and exact timeout commands are in `attribution-details.zip`.
No new native-analyzer assertion regression was observed in the comparable cases.
The 29 parser-blocked tests remain **unverified beyond dependency setup**, even
though their environmental failure cause is identified. The two P2 defects were
missing coverage in the old 122 and now have dedicated regression tests.

Final checks: **209 architecture-model tests passed in 280.44s**, including real tools,
coverage **95.12% (1422/1495 statements)** against the unchanged 80% threshold;
**19 P2 cases passed**; **72 native adapter/scanner/identity tests passed**;
**7 Node player tests passed**; Black and repository-wide mypy passed (377 sources).
Chrome/Playwright passed partial-executed versus planned-bilateral scope inspection,
legacy and both named-root latest/older checks, and the original cross-language
playback/history/source-evidence checks. Model bytes remained unchanged by browsing.

Fresh native exports again produced Python v1, TS 3 symbols/2 calls, Rust 3/1,
mixed Rust+TS 6/3, Java 4/3 and Java+Vue+TS 5/3. Vue remains FILE evidence only.
The Java/Vue scenario check retains an HTTP candidate. A fresh deterministic
continuation replay reused the two original businesses and IPC ID and completed
frontend-only change/rebind/review at revision 9 with zero pending reviews and
unchanged Rust bindings. This is a CLI replay, not another independent Agent session.

The earlier full-run result remains **2730 passed / 122 failed / 35 skipped**,
coverage **38.57%**, below the unchanged 80% gate. This round uses that log and
targeted controls rather than repeating the full 24-minute run. Private integration
and a passing whole-repository 80% gate remain unconfirmed. No unrelated whole-repo
cleanup, automatic merge or upstream PR is performed.
