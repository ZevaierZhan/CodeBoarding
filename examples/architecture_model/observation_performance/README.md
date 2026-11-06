# M6-C exact observation performance

Run from the repository root with Python 3.12 and the repository environment:

```text
uv run python examples/architecture_model/observation_performance/benchmark.py --directory <NEW_DISPOSABLE_DIRECTORY> --prepare 16000 --runs 3
uv run python examples/architecture_model/observation_performance/scenarios.py --directory <ANOTHER_NEW_DIRECTORY> --files 100
```

For an existing model, omit `--prepare` and supply `--model` and `--mapping`.
The output directory must be outside mapped sources. Existing model, facts and
source files are read only. The harness writes its own `plan.json` and measurements
inside the disposable output directory; use a new directory for each experiment.
The scenario harness creates and changes only its own synthetic files.

The fixture has 16,000 physical files and three independent snapshots: two full
roots and a 100-file subset. This deliberately stresses overlap (32,100 records),
rather than claiming to reproduce an enterprise model's architecture. Preparation
uses actual file-inventory exports and ModelStore commits. Preparation is excluded
from timings. An external model retains all actual interpretation and maintenance
records. No LLM provider, credentials, network analysis or Kotlin installation is
needed.

`measurements.json` records three fresh-process generation/check pairs, separate
instrumented generation/check samples, and three checks in one new process.
`process_seconds` includes interpreter/import startup; `seconds` measures CLI
dispatch including ModelStore loading/validation and output serialization/fsync.
The first check is separately available as sample zero. These are warm filesystem,
fresh-interpreter measurements; the harness does not flush the OS page cache.
Profiled samples must not be mixed with ordinary wall times. Inclusive profile
times overlap and must not be added. Metadata counts are Python stat/lstat calls,
not kernel system-call tracing. `path_opens` counts Path.open calls, including
JSON inputs; `binary_opens`/`binary_bytes_read` measure actual raw hashing reads.
Temporary output creation is additionally performed by atomic_write. Peak RSS is
the process lifetime high-water mark (Windows working set / POSIX ru_maxrss).
Full private artifacts and file names stay outside Git; publish aggregates only.

## Observation design

The harness rejects outputs inside mapped source directories and output names
that alias its model/mapping inputs before creating artifacts. Failed child
processes preserve complete stdout/stderr in `worker-failure.json` and chain the
original subprocess exception. This diagnostic is not an observation cache.

| Evidence | Scope and role |
| --- | --- |
| Filesystem identity | Canonical roots, real device/inode, link rejection; establishes physical attribution |
| Metadata | Full directory envelopes and before/after read fingerprints; detects obvious changes, never proves bytes |
| Raw SHA-256 | file_digest reads selected bytes, validates descriptor/path identity and repeats at closing observation |
| Facts provenance | Existing immutable snapshot IDs, source manifest digests, root-specific extraction scopes and versions |
| Engine/configuration | Fresh engine-source digest plus existing extraction/preview input checks; no retained engine cache |
| Interpretation/history | Existing M2 query, comparison, impact, root action gates and current/historical pending calculations |

An ObservationContext belongs to exactly one directory-scan boundary. It shares
directory results for canonical physical mappings and closing content reads for
physical file identities within that boundary. Opening and closing scans always
receive different contexts. Coverage's existing physical-identity hash deduplication
is retained: roots keep independent saved hashes, snapshots and descriptors.

The scanner validates each directory's ancestor chain on entry and exit, then
checks each child with non-following metadata once. It rejects symlinks and Windows
junctions before descending. It retains real device/inode values on Windows;
DirEntry.stat is unsuitable because it can return zero identities there. Directory
identity and mutation checks bracket iteration. The unchanged workspace envelope
still includes each relative path, device, inode, size and nanosecond mtime and
compares complete opening/closing manifests, including new/untracked files.

Coverage additionally shares validated parent paths in PathObservation. Portable
manifest syntax and each file's non-following link check remain mandatory. Every
cached parent is independently resolved and checked for the original device/inode
before returning coverage. A missing parent still yields unavailable manifest
records; it does not erase the selected facts or turn missing content into a match.

Coverage continues exact raw SHA-256 validation through safe_file/file_digest.
file_digest requests between 8 KiB and 1 MiB based on the initial file size,
avoiding a 1 MiB allocation/read request for every tiny file. It still reads to
EOF, checks the maximum byte limit, counts raw line endings, and verifies both the
open descriptor and path fingerprints before and after reading.
At the closing boundary, the scanner hashes the observed manifest files again and
compares the actual bytes to coverage, with physical-identity sharing only inside
that boundary. Files outside the directory observation's default exclusions are
still verified when present in the selected facts. Missing/replaced/changing files
fail conservatively. Metadata does not validate content. The closing hash is an
explicit safety repair: M6-B could miss a same-size rewrite after coverage if its
mtime was restored. The red regression is recorded in the implementation report.

External map/facts/preview input hashes are still checked at both boundaries.
ModelStore validation, actual model-content digest (beyond revision), extraction
scope checks, preview matching, engine-source hashes, root action gates, current
and historical review evidence, and write revision/token semantics remain intact.
CLI generation/check also hashes the on-disk model before loading and after
observation, rejecting a concurrent model rewrite before reporting success.
These model reads retain ModelStore's size policy; the 256 MiB source-file bound
continues to apply to source evidence and is not imposed on model documents.
No persisted model/facts schema or Plan v2 layout changes. Engine changes make
older plans stale as before. V1 remains audit-only and requires regeneration.

There is no persistent cache, Git/mtime shortcut, advisory Ready state, watcher,
background service or new agent. Cache corruption, versioning and concurrent cache
writes consequently introduce no new trust boundary. Scan dictionaries are local
to a command and are discarded on failure. Independent readers share no mutable
observation state. They can observe source changes and must retry on uncertainty.
There is no cross-file filesystem transaction: a successful check describes its
observation boundary and does not promise that files cannot change afterwards.

## Plan and Agent cost

V2 repeats file records in `files`, `validity.file_observations`, and overlap groups.
This change preserves the protocol instead of introducing references requiring
version negotiation and migrations. JSON identity checking and serialization
therefore remain proportional to full artifact size. Full plans stay on disk;
the existing context helper keeps every response within 4096 characters and supports
ID, root/status searches and JSON pointers. It still parses the full JSON locally;
bounded Agent context is not a promise of bounded local memory or partial I/O.

For fixed-input differential acceptance, run the harness against an unchanged
M6-B checkout using an explicit PYTHONPATH, then against this checkout with the
same model/mapping. Compare the saved plans:

```text
uv run python examples/architecture_model/observation_performance/compare_plans.py --before <BASELINE_PLAN> --after <FINAL_PLAN>
```

Both complete plan identities are verified before comparing every generated field
except the intentionally different engine fingerprint and derived plan ID. This
explicit acceptance command requires both artifacts; it introduces no test skip.
See [report.md](report.md) for measurements, private acceptance aggregates and gates.

The supplemental `posix_probe.py` accepts `--reference`, `--candidate` and `--output`.
Run it on a POSIX filesystem through `uv run --offline --no-project` with an
available interpreter. It compiles the actual standard-library observation
functions/classes from both checkouts, avoiding project dependency imports. It
checks real colon/backslash file and directory names, Unicode, symlinks and the
restored-mtime closing hash. The recorded WSL Python 3.13.5 result is seven checks;
it is not a full-project Linux/ModelStore run and does not override project pins.
