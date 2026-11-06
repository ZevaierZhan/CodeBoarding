# M6-C delivery checkpoint

Baseline: `9c2fd80def6d538534594847d5fe3293e6350fe3`, fork main, 2026-11-06.

- Measured the unmodified implementation before production changes with a public
  16,000-file fixture; retained ordinary, profiled and same-process samples.
- Added command-local workspace and ancestor observations with independent
  closing checks. Existing physical hash sharing and root boundaries remain.
- Sized raw reads without changing SHA-256, EOF, line counting or source limits.
- Added closing content and concurrent on-disk model checks. No model/facts schema,
  Plan v2, ModelStore atomic-write or expected-revision change was introduced.
- Preserved portable names, symlink/junction rejection, real Windows identities,
  missing-file records, current/historical pending and preview gates.
- Compared complete synthetic and actual formal/isolated plans against main;
  only engine fingerprint and derived plan identity differ.
- Completed read-only revision 10 / 39 acceptance and a disposable-copy mutation;
  original source/model hashes and interpretation/history match before/after.
- Updated external Agent guidance without changing bounded-output limits or
  adding a persistent cache, watcher, service, approval record or internal agent.
- Published aggregate evidence and reproducible benchmark/scenario/POSIX probes.

Private formal fresh-process medians: generation **49.53 → 23.74 s** (52.1% less),
unchanged check **48.13 → 26.68 s** (44.6% less), three comparable runs per version.
Private inputs contain about 16,000 physical files and 1.07 GB of bytes. Selected
plans retain 16,215 file records, three roots, 30 items and the original states.
The isolated model retains zero current pending and 20 historical pending.

Validation: the complete native-enabled repeat has **3066 passed, 5 failed,
55 skipped**, with **41.32%** coverage against the unchanged **80%** threshold.
The five failures reproduce on unmodified main. The first complete run additionally
timed out in three existing capture tests; isolated/reference/covered checks and
the complete repeat pass them, without changing their 60-second limit. Their exact
first-run cause remains unestablished and both runs are retained.

The final coverage/plan/observation subset has **122 passed, 1 existing host skip**;
the final new-test module has **34 passed**. Node Viewer has **8 passed**. Black,
mypy (400 files), pre-commit and Skill validation pass. A supplemental WSL probe
passes seven actual standard-library observation checks on Python 3.13.5; it is not
a full Linux project run. Benchmark input-preservation and child-trace tests are
included in the final new-test module after the broad-run collection.

The full quality gate remains failed because of baseline Windows failures and
coverage below 80%. JSON size and peak memory were not reduced. Full selected-byte
hashing remains necessary, and the closing safety repair increases content reads.
No M6-D work or merge is performed. Details and limitations are in
[the performance and acceptance report](report.md).
