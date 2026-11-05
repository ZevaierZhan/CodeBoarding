# M5 acceptance — 2026-11-05 (Asia/Shanghai)

Started from clean fork main `4f73e07c46b21a1fc96426b4be9bf9ff96e8a7dd` and fetched
origin/main. Work is on `m5/multi-language-architecture`; no upstream PR or merge
is authorized. The [implementation protocol](architecture-model-m5.md),
[replay instructions](../../examples/architecture_model/multilanguage/README.md)
and committed actual evidence accompany this report.

## Real native behavior

| Case | Actual result | Remaining bounds |
|---|---|---|
| Python | Existing real export/failure/audit probes pass through Pyright, including constants, syntax failure and no provider/telemetry | Legacy v1 shape/IDs retained; Python AST callable census remains |
| Rust | 2 files, 3 symbols, 1 method call | Cargo/rust-src required; desktop feature/macro registration not dynamically traced |
| TypeScript | 1 file, 3 functions, 2 calls/sites | External invoke is not an internal static edge; explicit compatible SDK used |
| Rust + TS root | 3 files, 6 symbols, 3 calls | One facts export across both adapters; project map names backend/frontend |
| Java | 2 files, 4 class/method symbols, 3 native calls/sites | Native class/constructor targets coexist with the service method target; not three executions |
| Vue + TS | API method located; .vue present as FILE | No native SFC function discovery/call resolution |
| Java + Vue + TS | 4 files, 5 symbols, 3 native Java calls | Vue is explicitly file-only; HTTP deployment/host absent |

Actual tools: Python 3.12.13; Tokei 14.0.0; Pyright from prepared M1 tools;
TypeScript language server 6.0.3 and SDK 5.9.3; rust-analyzer/Cargo toolchain
1.99.1; Oracle JDK 21.0.8; JDTLS core 1.59.0.202605111959. The repository `.env`
was absent. This provider-free path requires no provider configuration and does
not install into the target environment.

Native TS project membership uses its existing tsconfig scanner; native Java
uses Maven project discovery; Rust is rooted at the native workspace and records
nearest Cargo manifest membership. Export runs native projects separately before
name-only native graph merging, and rejects overlapping file membership and real
entity qualified-name collisions. Repeated package declarations are legitimate
scopes, not graph entities, and are excluded from collision rejection. A dedicated
regression protects that distinction. Large workspaces, overloads and arbitrary
external project references are not claimed verified by these small fixtures.

Initial TS initialization failed without a usable external SDK and native code
returned an empty graph. The new entrance now rejects empty non-Python graphs
and logged LSP error responses. Initial Java exports failed without JDTLS; after
the actual 51,543,088-byte upstream installation, one startup/JDK-discovery attempt
failed and a real repeated-package collision exposed the strict-identity bug.
After the scope/entity distinction was corrected, native Java and mixed exports
succeeded. Error traces and successful follow-ups are both retained; failed runs
did not publish facts. A later audited export records the actual JDTLS core JAR
and hashes the resolved plugin distribution in its extraction descriptor.

Raw probe commands, stdout, stderr, snapshot catalogs and final tool versions
are under [example evidence](../../examples/architecture_model/multilanguage/evidence/).
No production input was manufactured from expected facts JSON. All calls and
symbol locations in the delivered models originate from real native extraction.

## One model, independent versions and a continuing Agent

Canonical [model](../../examples/architecture_model/multilanguage/model/model.json)
ID `c3094cd2-b73e-4b0c-a3bb-6b9beb395a58`, revision **10**; [one HTML](../../examples/architecture_model/multilanguage/model/index.html).
Two independent repositories have stable IDs frontend/backend and distinct commits
`afb2aa70c0462fb4b96f741e2822cc6703013b80` /
`fa9567b46d60be8d94ed30f35dc6a3c4836d0c1e`. Five snapshots remain immutable.

The external author saved open-document at revision 1. A fresh Agent context read
the updated Skill, used complete-read capture/bounded queries, inspected both
roots and added preview-document with independent CLI processes and expected
revision 1. It reused all shared architecture/evidence identities. Saved equality
checks confirm the first business, facts, bindings, components and relations were
unchanged. See [its independent report](../../examples/architecture_model/multilanguage/independent-agent.md).

Final exporter-descriptor adoption was explicit at revision 3, with unchanged
source bytes and appended binding history. The controlled source edit normalized
only the frontend notes.txt literal with `.trim()`. Native re-export and M2
preview/refresh marked exactly open/preview/invoke as changed at containing-file
granularity; no backend binding was compared. The shared read-file-ipc relation
and both scenarios were included in review scope. Three explicit rebinds and
three exact-version confirmations produced revision 10, with all historical
catalogs/locations retained, no changed interpretation definitions, three resolved
observations and no pending reviews. Rust bindings are byte-for-byte equal to
the adopted baseline throughout the source-change phase.

An additional real frontend export with identical manifest, paths and native
symbol keys but a different root ID validates alongside the existing snapshots
in one model candidate. Its IDs differ and the canonical model bytes/revision
remain unchanged. Tests also cover colliding files/names, legacy catalogs,
root-limited candidates, strict fields, failed writes, contract evidence and maps.

## Contracts and Java/Vue compatibility

read-file-ipc reuses Relation ID as durable contract identity. TypeScript
src/utils.ts:3-5, Rust src/lib.rs:3-6 and src/lib.rs:8-11 provide caller, receiver,
feature condition and registration evidence; src/utils.rs:1-3 provides actual
service code. Native TS/Rust internal call sites are retained. The process hop
remains **candidate/inference**: desktop host activation, feature build and runtime
IPC have not been executed. No same-name heuristic auto-confirms it.

The [Java/Vue capability HTML](../../examples/architecture_model/multilanguage/evidence/java-vue.html)
and authored patch validate one Vue → TS client → Controller → Service scenario
against real mixed facts. Vue is a FILE binding only. TS fetch POST /api/orders,
Java @RequestMapping /api and @PostMapping /orders supply double-sided route
evidence; native call sites supply Controller → Service. The HTTP contract is
candidate because frontend proxy/base URL, Spring application boot/scanning and
deployment were not included or run. SFC method precision remains follow-up work.

## Quality gates

The actual command outputs are committed as evidence. Thresholds/assertions were
not lowered. Private CodeBoarding-tests integration is unavailable in this checkout.

- An earlier complete model suite: **188 passed**, including real Python and
  Rust/TS/mixed export subprocesses. Its raw coverage report widened to imported
  native packages in subprocesses; a separate explicit architecture_model report
  passed the same 80% threshold at **95.29% (1314/1379 statements)**. The raw report
  failure is retained. A final run uses the same source scope explicitly in the
  subprocess coverage configuration; its final result is recorded below.
- Final M5 real-worker/artifact tests: **13 passed**. Native adapter/scanner and
  strict-identity regression selection: **72 passed**.
- Node player: **7 passed**, retaining all original branch/loop/return/history
  assertions and adding real two-root business playback.
- Whole-repository Black completed. Whole-repository mypy completed with no
  issues; a one-line Windows SIGKILL attribute portability fix was required in
  native dependency-process cleanup.
- Headless local Chrome/Playwright checked cross-language steps, collapse/expand,
  Back, per-scenario position, both roots/languages, candidate contract and withheld
  historical bytes. No JavaScript errors; model SHA-256 before/after both
  `a31ae5db4d8b83cb8befb3159911f1568d4b035303667c892cce1095bd56f28b`.
  Screenshot inspected. Built-in browser control was unavailable in this session.
- Default-feature Rust fixture compiled via cargo test, with **0 tests**; this is
  compilation evidence only, not desktop/IPC execution.
- Full repository command `uv run pytest --cov=. --cov-report=term --cov-fail-under=80`
  completed in 1443.77s: **2730 passed / 122 failed / 35 skipped**, raw coverage
  **38.57%**, below 80%. Failures span renderer, diagram and native suites. A clean origin/main source archive in the
  same environment reproduces the first renderer path failure (1 failed / 8 passed
  with maxfail=1); no claim is made that every full-suite failure has been classified.
  Two package-layout assertions scan ambient ignored `temp/` checkout archives;
  the encoding assertion also scans old ignored `temp/` Python scripts. One new
  arrow string in the Java/Vue transcript was fixed; its rerun reports no M5
  source violation, but still fails on those ambient scripts. The original tests
  and thresholds remain untouched; the complete repository gate is **not passed**.

Raw command logs are preserved losslessly as `evidence/*.log.gz` to keep large
tracebacks out of the source diff. The final model source-scope coverage config
adds only `source = architecture_model` to the existing subprocess/omit rules;
all assertions and the 80% threshold remain. Use its absolute path when invoking
from tests that launch CLI helpers in other directories. A relative-path trial
had two 60-second context-helper timeouts; all ten context tests pass with the
absolute config, and that incomplete trial's 94.99% coverage is retained as
diagnostic evidence, not a successful full-suite result.
