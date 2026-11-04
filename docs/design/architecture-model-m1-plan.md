# M1 implementation plan

Baseline: `origin/main` at `d02b718e`, containing reviewed P0
`cb23ff82a2c49d24ff90342068e1f1dedd9bcd94`. The GitHub PR query returned
OPEN despite the main merge commit; Git ancestry establishes that P0 is included.
Workspace was clean; branch `m1/architecture-model-cli`, PR base fork `main`.
No `.codegraph` index or `.env` exists. This entry intentionally requires no provider.

1. Add a strict Pydantic v1 domain schema, separate from native clustering.
   Preserve opaque IDs, evidence kinds, explicit scenario order/transitions,
   historical bindings, opinions, planned/executed verification and revision metadata.
2. Publish immutable Python facts snapshots using a dedicated subprocess worker.
   Configure telemetry before native imports, explicit Node/Pyright/Tokei paths,
   real StaticAnalyzer context, source manifests and fail-closed completeness checks.
   Copy the validated fact catalog into the explanation file for offline historical reads.
3. Share candidate construction and validation across read/validate/diff/apply.
   Explicit create/update/delete operations; arrays replace whole; immutable identities.
   Stable FileLock covers read/revision check/candidate/validation/os.replace.
4. Expose `codeboarding-model` and `python -m architecture_model`, JSON stdout,
   structured errors and separate diagnostic stderr. Scoped reads are marked partial.
5. Reproduce startup and two real business paths with a dedicated small fixture,
   preserving the P0 fixture. Demonstrate structural edits, stale evidence, process
   races and disk failure invariants with tests and independent CLI processes.
6. Run focused coverage, repository Black/mypy/full coverage (bounded where stalled),
   record actual outcomes without claiming the existing Windows gates pass;
   review, commit with hooks, push and open a new fork Draft PR.

M2 automatic refresh/rebinding and M3 graphical views remain outside this delivery.
