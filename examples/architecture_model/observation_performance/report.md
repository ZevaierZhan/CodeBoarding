# M6-C implementation and acceptance report

Baseline: fork main `9c2fd80def6d538534594847d5fe3293e6350fe3` (M6-B PR #10).
Measured on Windows with CPython 3.12.13, repository venv, warm filesystem cache.
Timed benchmark groups were serial and the full test suite was kept separate.
A one-second safety-regression probe overlapped the initial baseline group;
independent repeats and a later unchanged-reference control are retained.
Other host workloads were not controlled; ranges and separate profiles are retained.

## Baseline before production changes

The public fixture contains 16,000 physical files, 32,100 independent root-file
records, 16,000 overlaps, three roots and 30 items. It intentionally has more
overlapping manifest records than the private fixture. First preparation used real
file-inventory exports and ModelStore commits before modifying production code.

| Baseline operation | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: |
| Fresh-process generation, CLI dispatch | 38.61 s | 39.24 s | 39.38 s |
| Fresh-process unchanged check, CLI dispatch | 38.38 s | 38.63 s | 41.31 s |
| Repeated checks inside one new process | 37.09 s | 39.73 s | 49.05 s |

Instrumented baseline check: 62.93 s, separate from the wall-time comparison.
It made 353,973 Python stat calls, 128,520 lstat calls, 64,420 safe_file calls,
16,085 file_digest calls and read 1,345,275 binary bytes. The counts include
engine and external input hashing; selected source was physically hashed once.

| Baseline profile region | Calls | Inclusive time |
| --- | ---: | ---: |
| Two complete workspace observations | 2 | 31.02 s |
| Coverage | 1 | 27.04 s |
| safe_file, across workspace and coverage | 64,420 | 33.21 s |
| Raw file_digest, across all callers | 16,085 | 10.87 s |
| Engine fingerprint | 1 | 0.071 s |
| ModelStore.read, including validation | 1 | 1.50 s |
| M2 query / impact | 1 each | < 0.001 s each on the synthetic fixture |

Inclusive times overlap. These measurements confirm that existing same-directory
scan sharing and physical-file hash sharing already work. They do not justify a
persistent engine cache or cross-command metadata trust. Revalidating all ancestors
for each file in both complete scans and coverage is the measured repeated work.

## Safety regression isolated from the optimization

Before production changes, the new test
`test_change_after_coverage_with_restored_metadata_never_publishes` failed:
M6-B published a plan after a file was rewritten between coverage and the closing
scan, with the same length and restored mtime. The final metadata manifest matched.
This is a correctness repair, not a speed claim: closing observation now reads the
selected bytes again. A second regression exercises another ModelStore writer
during CLI generation/check; the CLI rejects the result before publishing success.
Stable-input state semantics and the Plan protocol are unchanged.

The initial scan-only pilot (one completed pair, before parent-path reuse) took
35.10 s generation / 36.58 s check. That pilot was stopped because restoring exact
closing hashes consumed most of the scan savings. It is not the final performance
result and is not counted as an independent repeat of the final implementation.

See [README.md](README.md) for the six distinct trust boundaries, lifecycle,
protocol, concurrency constraints and reproducible commands. Machine-readable
aggregate evidence accompanies the completed acceptance results below.

## Final performance results

The Windows host reports 12 logical CPUs. Measurements use the same venv and
fixed inputs, with OS caches left warm. Fresh-process wall time below includes
interpreter/import startup, CLI work and the harness's outer integrity checks.
The isolated model has one pair only; it is an acceptance sample, not a repeated
performance claim. All ordinary samples, inclusive profiles and ranges are in
[performance-summary.json](evidence/performance-summary.json) and its companion
sample files. No fastest-run selection or same-process cache substitution is used.

| Fresh-process workload | Baseline median | Final median | Reduction | Repeats/version |
| --- | ---: | ---: | ---: | ---: |
| Synthetic generation | 40.62 s | 14.71 s | 63.8% | 3 |
| Synthetic unchanged check | 40.01 s | 27.85 s | 30.4% | 3 |
| Private formal generation | 49.53 s | 23.74 s | 52.1% | 3 |
| Private formal unchanged check | 48.13 s | 26.68 s | 44.6% | 3 |
| Private isolated generation | 43.81 s | 23.79 s | 45.7% | 1 |
| Private isolated unchanged check | 44.91 s | 24.23 s | 46.0% | 1 |

Synthetic check process wall times vary substantially: baseline 39.61–42.83 s,
final 15.68–50.58 s, while measured CLI dispatch is 38.38–41.31 s versus
11.17–12.66 s. The discrepancy is outside the measured CLI region; its exact
host/startup cause was not established, so the faster CLI number is not presented
as the process-level improvement. Private formal check ranges do not overlap:
45.42–51.37 s versus 23.36–27.46 s. Formal generation ranges are 48.57–56.99 s
versus 23.32–24.16 s. These repeated real-input results support the 30% target
more strongly than the noisy synthetic process samples.

Within the CLI dispatch region, synthetic generation is 39.24 → 12.00 s and check
38.63 → 11.86 s. Repeated checks in a single new process are 39.73 → 11.14 s
(three each). Every repeat still observes source and engine content again; this
does not depend on retaining an observation cache between calls. Formal dispatch
medians are generation 48.26 → 22.52 s and check 46.85 → 25.49 s.

The isolated real model's separate instrumented check identifies the actual costs:

| Inclusive region / counter | Baseline | Final |
| --- | ---: | ---: |
| Workspace observations, including closing verification | 42.30 s | 20.06 s |
| Coverage | 29.24 s | 10.05 s |
| Raw hashing across callers | 14.19 s | 10.08 s |
| Engine fingerprint | 0.078 s | 0.031 s |
| M2 query | 0.874 s | 0.728 s |
| Impact explanation | 1.157 s | 1.113 s |
| Python stat / lstat calls | 470,589 / 280,231 | 225,760 / 52,660 |
| Content-hash calls | 16,294 | 32,506 |
| Path.open calls | 16,297 | 32,509 |
| Actual binary stream bytes | 1,072,393,960 | 2,174,472,857 |
| Peak process working set | 202,862,592 B | 208,687,104 B |

The combined stat/lstat count falls 62.9%. Content opens and bytes increase because
the closing source hash and two on-disk model checks are additional safety gates.
This is not represented as a content-cache hit or I/O reduction. Content reads are
shared per physical identity separately in each boundary. Source byte verification,
model bytes, engine sources and external inputs still require complete hashing.
Peak memory increases about 5.55 MiB (2.9%) in this real profile; memory reduction
has not been established. Python-level counters do not include native resolver
handles, import-time opens or all text JSON I/O, and do not measure physical disk
traffic under a warm page cache.

An alternating 2,000-file probe changed only the read request size. The final
8-KiB-to-1-MiB policy gave 0.220 s median versus 1.284 s, with identical returned
hashes, line counts and physical fingerprints. The final implementation preserves
EOF reads, size limits, descriptor/path fingerprint checks and raw line endings.
Pure-model M2/impact work and the engine digest are much smaller than source
observation in the real profile, so no model-result or engine cache was introduced.

Initial synthetic Windows peak-memory readings were zero because of a harness
handle-marshalling error. They are marked unavailable in published baseline data.
The corrected unchanged-reference control reports 324,153,344 B; the optimized
synthetic profile reports 325,210,112 B. The control's 54.47 s is profiled time,
not an extra ordinary timing sample.

## Private preservation and protocol

The actual current formal model is revision 10: three roots, 16,169 physical source
files (1,071,041,302 bytes), seven Comparison topics and nine Operations. The saved
isolated model is now revision 39: three roots, 16,209 physical source files
(1,071,501,239 bytes), six Comparison topics, nine Operations and 14 binding history
locations. Neither historical revision numbers nor old source counts were assumed.
Each selected plan has 16,215 records and 30 items. Confirmed physical overlap
counts remain 46 formal / 6 isolated; independent roots and versions are retained.

All complete fixed-input plans pass `compare_plans.py`: their own SHA-256 identities
are checked first, then every field except engine_digest and the derived plan_id
is equal. This includes root/item states, hard dependencies, affected IDs, preview
diagnostics, contract sides, verifications and current/historical pending. Both
real plans remain blocked with one blocked root, exactly as the reference does.
The isolated model retains zero current pending and 20 historical pending. Ready
inspection counts remain ten formal / eleven isolated, without authorizing writes.

Independent before/after full source byte digests, raw model SHA-256 and protected
facts/scenarios/facets/bindings/history/verification digests match. A separate
disposable source copy detects a same-size rewrite with restored mtime as stale.
It modifies neither original source tree nor original model. Only aggregate
preservation results are published; private paths, manifests, model hashes, full
models and plans remain outside GitHub.

Plan protocol remains cross-root-maintenance-plan-v2. Old v2 artifacts are safely
stale when the engine fingerprint differs; v1 still requires regeneration. Model
and Facts schemas and ModelStore atomic writes/expected revisions are unchanged.
No persistent cache, automatic maintenance execution, watcher, service or M6-D
work was introduced.

Plan sizes remain 17,944,907 B formal and 18,476,979 B isolated; the highly
overlapping synthetic plan is 52,856,809 B. V2 duplicates in files/overlaps/validity
are retained to avoid an unrelated protocol migration. Serializing and checking
the full artifact remain linear in its size. The synthetic atomic JSON write is
7.62 s inclusive under profiling. CLI stdout remains below 1 KiB; the context
helper retains its 4096-character bound and parses the full JSON locally.

All 14 disposable change scenarios have identical status, replan decision and
reason codes in reference and optimized versions: unchanged, modified,
same-size/restored-mtime, restored original bytes, addition, deletion, rename,
identical physical copy, mapping-byte change, facts change, extraction upgrade,
model revision, same-revision model content and engine mismatch. Raw-model hashes
are protected. Actual engine-source modification in another checkout, concurrent
readers/writers, link/junction boundaries and cache/path regressions are covered
by the test gates reported below. No persistent-cache corruption/version test is
needed because no persistent cache exists; existing Q1 cache tests remain enabled.

Final-code confirmations regenerate and check all three complete fixtures again,
then pass the same complete-plan comparison. These single pairs are supplementary,
not replacements for the primary repeated measurements. Their samples are in
[final-code-confirmations.json](evidence/final-code-confirmations.json).
The final portable-name guard was also exercised on WSL against the actual
standard-library observation source: seven checks cover normal Unicode paths,
colon/backslash files and directories, symlinks and restored-mtime content drift.
WSL uses Python 3.13.5 without importing project dependencies; this is not a full
Linux/ModelStore run and does not override the project's interpreter constraints.

Actual bounded-query measurements on the final plans:

| Fixture | Two ready-item index rows | Pending detail | Process time range |
| --- | ---: | ---: | ---: |
| Synthetic | 380 characters | 70 characters | 0.74–0.87 s |
| Formal | 398 characters | 70 characters | 0.55–0.57 s |
| Isolated | 398 characters | 1650 characters | 0.59–0.66 s |

These query outputs stay well below the unchanged 4096-character limit. The full
JSON is still read locally. Query response contents and private IDs are not
published, only lengths and durations.

## Quality gates and unresolved limitations

| Gate | Result |
| --- | --- |
| First complete native-enabled run | 3061 passed, 8 failed, 55 skipped; 41.29% coverage |
| Complete native-enabled repeat | 3066 passed, 5 failed, 55 skipped; 41.32% coverage |
| Architecture-model tests in repeat | 367 passed, 1 existing host skip |
| Q1 path protocol / cache identity / cache invalidation | 16 passed / 27 passed + 4 existing skips / 6 passed |
| Final plan/coverage/observation subset | 122 passed, 1 existing host skip |
| Final new-test module, including final harness guards | 34 passed |
| Node Viewer | 8 passed |
| Black / mypy / pre-commit / Skill validator | Passed; mypy checks 400 source files |
| Required full coverage | **Failed: 41.32% < unchanged 80%** |

The five final failures reproduce on the unmodified reference checkout:

- `tests/infra/test_tool_registry.py::TestToolRegistry::test_install_node_tools_prefers_embedded_npm`
- `tests/infra/test_tool_registry.py::TestInstallEmbeddedNode::test_rejects_non_executable_node_binary`
- `tests/infra/test_tool_registry.py::TestInstallEmbeddedNodeEndToEnd::test_full_install_flow_with_mocked_download`
- `tests/infra/test_tool_registry.py::TestInstallNativeToolsCompressed::test_gz_asset_is_decompressed_and_chmod_set`
- `tests/test_devcontainer.py::TestDevcontainer::test_post_create_script_bash_syntax`

The first broad run additionally exceeded the original 60-second subprocess guard
in three existing capture tests. No helper/store implementation or timeout was
changed. Current isolated context tests pass 10/10, reference context tests pass
10/10, the current covered context module passes 10/10, and the complete repeat
passes all three. Their exact first-run cause was not established and is not
assigned to host load or classified as a baseline failure. Both complete results
are retained. Two Git HEAD/dirty/untracked cases were added between full collections;
the final focused run additionally covers later portable-name and harness guards.

One additional final-confirmation worker exited 1 before creating a plan. The
initial harness did not surface its captured stderr, so that attempt's exact cause
is unavailable. A direct rerun succeeds (11.96 s), and the complete final-code
confirmation later succeeds for all fixtures. The harness now preserves full
worker stdout/stderr and chains the original exception; an actual failed-child
regression tests that behavior. The failed attempt is not a successful timing
sample and is not used to replace any primary measurement.

The full gate remains failed; no assertion, timeout, skip policy, optional Kotlin
behavior or coverage threshold was weakened. No Kotlin installation was performed.
Selected-source hashing and full v2 JSON parsing/identity checks remain linear;
there is no metadata-only proof of unchanged content or cross-file filesystem
transaction. JSON size and peak memory were not reduced. Process-startup variance
and the non-reproduced first-run failures remain measurement/diagnostic limitations.
Machine-readable results are in [validation-summary.json](evidence/validation-summary.json).
