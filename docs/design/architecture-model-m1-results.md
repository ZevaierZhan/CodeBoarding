# M1 validation — 2026-11-04 (Asia/Shanghai)

M1 is implemented on `m1/architecture-model-cli` from fork `origin/main`
`d02b718e`, which includes reviewed P0 `cb23ff82`. No existing native analyzer,
clustering, semantic pipeline, P0 fixture or P0 branch was changed. The initial
workspace was clean. The new PR targets fork `main`; P0 is already included by
Git ancestry even though the PR query returned an inconsistent OPEN state.

The [implementation plan](architecture-model-m1-plan.md) was recorded before
implementation. The [protocol guide](../architecture-model.md) describes the
schema, commands, error codes, identity/evidence semantics and commit boundary.
Machine-readable outcomes, exact source hashes and fact locations are in
[architecture-model-m1-validation.json](architecture-model-m1-validation.json).
Temporary full logs and replay output remain ignored under `temp/`.

## Completed behavior

| User story / acceptance | Observed result |
|---|---|
| H1/A1: persist startup and read in another session | One initialized model; independent CLI processes add startup, business A and business B. Final revision 10. All three scenarios survive. |
| A3: share and revise a public component | A/B share component `policy`. Reading only A and updating that component changes its description; diff reports both scenarios, and B's own steps/explanations remain byte-equivalent as JSON values. |
| A2/H4: real structure changes | Cross-directory policy/persistence membership, rename without ID replacement, reparent, split and merge with explicit reference repair succeed. Merge retains the business steps. |
| Structural failures and cycles | Delete omitting a scene reference and component parent cycle fail without changing model bytes. An explicitly hypothetical business repeat transition saves, with the lack of a caller loop recorded as uncertainty. |
| A5/H3: rationale and uncertainty | Independent rationale and typed claims persist. Inference needs evidence and assumptions/issues. Opinion acceptance does not promote inference. Planned checks cannot contain executed results. |
| Historical evidence | The replay deletes temporary pricing source, marks the binding missing with a reason, and reads its original location/hash/version plus the unchanged scenario in a new process. Absent internal binding IDs still fail. |
| Real facts, no provider | Original P0: 8 callable nodes, exactly 3 expected call edges, real locations. After changing `place_order`'s target to `format_receipt` in a temporary copy, the exact call edge and source version change. Explanation bytes remain unchanged. |
| Native isolation probe | No API-key requirement; telemetry disabled before native imports; no forbidden provider/profile or Python socket events; no unfinished Python threads. Guard report: 8 symbols/3 calls. A swallowed network-attempt negative still exits 1 at finalization. This is not an OS network sandbox for Node/LSP subprocesses. |
| Independent competing writers | Ready/go barrier launches two different patches at one expected revision. Exactly one commits, one gets `REVISION_CONFLICT`, final revision advances once and contains only the winner's complete update. |
| Save failure invariants | Injected temporary creation/serialization/fsync/replace failures keep original bytes and revision. Failed init leaves no model. Post-commit stdout failure exits 2 and keeps the committed revision; no compensating overwrite occurs. |
| Strict inputs | Duplicate IDs/JSON keys, nested unknown fields, bad schema versions, missing references, contradictory current bindings and discarded historical locations are rejected. Partial read envelopes cannot be used as patches. |

The independent guard originally exposed its own profiler teardown handling of an
empty module name. It was fixed to tolerate teardown and to finalize after native
exit callbacks, accumulate failures and force nonzero exit on report/flush failure.
The final positive and swallowed-attempt negative were rerun. No experimental
guard/audit/atexit code is imported by the production package.

## Engineering checks

| Command / scope | Actual outcome |
|---|---|
| `uv run pytest tests/architecture_model -q --cov=architecture_model --cov-report=term-missing --cov-fail-under=80` with explicit M1 tool environment | **72 passed**, no skips; **96.94%** M1 coverage. Exact duration and statement counts are in the machine record. Includes real native runs and separate-process tests. |
| `uv run black .` | Exit 0, 349 Python files at execution; final hook/check also required before commit. |
| `uv run mypy .` | Exit 1; one error at `static_analyzer/workspace_dependencies.py:78`, Windows `signal.SIGKILL` attr-defined. No M1 type errors. |
| Four P0-focused test files | Exit 1; 63 passed, 2 failed in 5.04s, the two ScopeAssembler Windows relative-path assertions. |
| Fresh `origin/main` archive, activated same Python 3.12 venv, `python -m mypy .` | Exit 1; same SIGKILL error, 333 source files. |
| Same fresh baseline, `python -m pytest tests/diagram_analysis/test_scope_assembly.py -q` | Exit 1; 20 passed, same 2 failed in 6.72s. Both affected production files are unchanged from baseline. |
| `uv run pytest --cov=. --cov-report=term --cov-fail-under=80` | Final attempt collected 2771; observed failures outside M1; reached `test_call_graph_builder.py`, about 60%, then hit the 180s total bound. Owned process tree terminated; test process exit 1, elapsed 180.25s. Earlier attempts reached about 68% before the same bound. No final coverage report; whole-repository 80% **not confirmed**. |
| `uv build --wheel` | Exit 0; inspected wheel contains all 9 architecture modules and the `codeboarding-model` console entry point. Installed CLI validates the replay's final model at revision 10. |
| Raw JSON Schema compared with runtime `Model.model_json_schema()` | Equal. |
| Private `CodeBoarding-tests` integration | Not run; unavailable private repository. |

The final focused run includes guarded-probe finalization negatives and a regression
for validating the completed multi-operation binding candidate. The two Windows path
failures and mypy error are independently baseline-reproduced. Other full-suite failures
are **unattributed**, not asserted to be baseline or environment-only. No threshold
was lowered and no existing failed test was removed or disabled.

After the last bounded full-suite attempt, the worker adopted the repository's
shared stderr logging setup. Focused tests, native probe, complete CLI replay,
Black, mypy and wheel were rerun with that final integration.

## Remaining boundaries

M1 provides maintained interpretation files and structured CLI review. It does not
perform automatic source refresh, rename inference, fuzzy rebinding or explanation
verification (M2); graphical editing, expansion/playback and animation (M3); MCP;
internal business analysis; accounts/approval services; or multi-file transactions.
Python facts are scoped static records with explicit tool paths, not complete
dynamic execution facts or a full dependency/environment fingerprint. The copied
fact catalog favors offline auditability over storage efficiency. Large-project
performance and network-filesystem locking have not been validated.
