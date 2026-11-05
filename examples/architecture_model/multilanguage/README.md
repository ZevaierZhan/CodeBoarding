# M5: one continuing architecture across TypeScript and Rust

Open [the interactive document](model/index.html). Its canonical persistent artifact
is [model/model.json](model/model.json), model `c3094cd2-b73e-4b0c-a3bb-6b9beb395a58`,
revision **10**. Both `open-document` and `preview-document` reuse the same
`read-file-ipc`, `ipc-client`, `rust-command` and `document-service` identities.
This is an authored static business explanation, not an executed desktop trace.

The fixture contains real TypeScript `invoke("read_file", {path})`, a Rust
`cfg_attr(feature="desktop", tauri::command)` declaration, a feature-gated
`generate_handler![read_file]` registration and a real filesystem service call.
The optional Tauri dependency is pinned. Default-feature `cargo test` compiles
the Rust fixture (zero unit/doc tests); a desktop host and feature build were not
run. Consequently the saved contract remains **candidate/inference**: both source
sides and registration are present, but host activation and runtime dispatch are
unverified. Names alone never promoted it to an evidenced contract.

## Real extraction and continuation

Native StaticAnalyzer runs produced:

| Input | Files | Symbols | Static calls | Scope |
|---|---:|---:|---:|---|
| TypeScript frontend | 1 | 3 | 2 | Native TS SDK/LSP |
| Rust backend | 2 | 3 | 1 | Native rust-analyzer/Cargo |
| Mixed Rust + TypeScript root | 3 | 6 | 3 | Both adapters, one facts snapshot |
| Java backend | 2 | 4 | 3 | Actual JDTLS class/method locations |
| Vue + TypeScript frontend | 2 | 1 | 0 | API method; Vue FILE evidence only |
| Java + Vue + TypeScript root | 4 | 5 | 3 | Native Java/TS plus explicit Vue file scope |

Java's three native call records include class/constructor targets in addition
to the Controller → Service method edge; these are retained native resolution
records, not three runtime invocations. Imports, external libraries, registration
macros, HTTP and IPC are not automatically turned into cross-language call edges.

[Probe commands/results](evidence/results.json), [final mixed facts](evidence/mixed-final.facts.json),
[Java/Vue audited facts](evidence/java-vue-audited.facts.json) and stderr logs are retained.
Initial missing-tool/initialization/strict-package-collision failures also remain
visible. Later successful exports do not replace failed runs in the evidence.
The final mixed snapshot records `frontend`/`backend` project membership separately.

[The independent Agent report](independent-agent.md) records a fresh context,
bounded complete-read queries, source inspection, revision check, validate/diff
and independent CLI apply. It added only the second scenario at revision 2;
the first scenario and all shared definitions were exactly preserved.

## Independent source versions and maintenance

The primary trial copied the source fixture into two independent Git repositories:

- `frontend`: `afb2aa70c0462fb4b96f741e2822cc6703013b80`.
- `backend`: `fa9567b46d60be8d94ed30f35dc6a3c4836d0c1e`.

The canonical model contains five immutable snapshots: original two exports,
explicit adoption of final exporter descriptors for unchanged sources, and one
changed frontend export. Descriptor adoption itself retains binding history; it
does not rewrite original facts or pretend there was a source edit.

Only `frontend/src/utils.ts` then changed: `"notes.txt"` became
`"notes.txt".trim()`. Preview/refresh conservatively marked all three bindings in
that file changed, including the unchanged preview/helper functions. Both scenes
and the shared contract were in review scope. No backend binding was compared,
rebound or reviewed during that source change. Three explicit rebinds and three
version-specific confirmations followed; all original catalogs and interpretation
definitions remain identical. Revision 10 has **three resolved observations and
zero pending reviews**; authored IPC status is still candidate.

See [maintenance checks](model/maintenance-check.json), the saved preview/pending/final
reports and every CLI response. [Identity validation](evidence/identity-check.json)
also places an actual independently exported root with identical `src/utils.ts`,
symbol keys and manifest bytes into the same model candidate: distinct root and
snapshot IDs coexist without rewriting the canonical model.

Current primary evidence is reproducible with the committed
`source-current/frontend` (the edited file) and `source/backend`. Historical
frontend bodies are withheld against current edited bytes. To inspect old bodies,
map frontend to `source/frontend` instead. Matching is per file, so neither map
pretends to be an archive of every historical version.

```json
{"frontend":"/absolute/example/source-current/frontend","backend":"/absolute/example/source/backend"}
```

```sh
uv run python -m architecture_model model --file model/model.json export-html \
  --source-map roots.json --output a-new-view.html
```

Paths in saved source maps and command logs describe the acceptance machine;
substitute local paths when replaying. Model identities do not contain those paths.

## Reproduce

Run from the engine root using its environment, Python 3.12+, prepared native tools
and no provider credentials. The target never installs CodeBoarding. Prepare
`tools.json` with absolute executable argv arrays:

```json
{
  "tokei":["/tools/tokei","-o","json"],
  "typescript_sdk":"/tools/node_modules/typescript/lib/tsserver.js",
  "lsp_servers":{
    "typescript":["/tools/node","/tools/node_modules/typescript-language-server/lib/cli.mjs","--stdio"],
    "rust":["/tools/rust-analyzer"],
    "java":["/jdk/bin/java"]
  },
  "jdtls_root":"/tools/jdtls"
}
```

Acceptance used TS language server **6.0.3**, TypeScript **5.9.3**, rust-analyzer
**1.99.1**, Tokei **14.0.0**, Java **21.0.8** and JDTLS **1.59.0.202605111959**.
Initial TypeScript tool discovery did not supply a usable tsserver; the final
probe explicitly selected the recorded SDK. Java needs a JDTLS distribution and usable JDK 21+;
Cargo/rust-src must be usable for Rust. Tools are not auto-installed by export.

```sh
uv run python examples/architecture_model/multilanguage/probe.py --tools tools.json --output NEW_TRIAL
uv run python examples/architecture_model/multilanguage/author_initial.py --facts NEW_TRIAL --output NEW_MODEL_DIR
```

Give a fresh external Agent the Skill, two `NEW_TRIAL/target` roots and the model
locator to add preview using existing IDs. The saved preview patch also permits a
deterministic independent-CLI replay; replay alone is not a new Agent session.
Then run:

```sh
uv run python examples/architecture_model/multilanguage/maintain_trial.py --model-dir NEW_MODEL_DIR --target NEW_TRIAL/target --tools tools.json
```

The scripts are external Agent authoring/acceptance transcripts, not product
business-generation logic. Each output directory/publication must be fresh.
Baseline adoption may be a no-op when replaying with the final engine, so replay
revision numbers may differ while stable logical IDs and maintenance semantics hold.

## Java/Vue check and limits

[The separate capability HTML](evidence/java-vue.html) freezes a temporary validated
check model with Vue → API Client → Controller → Service in one scene.
[Its authored patch](evidence/java-vue.patch.json) and [check result](evidence/java-vue-check.json)
come from actual mixed facts. Vue is bound to its FILE; no SFC function symbol or
Vue → API native call was invented. API `POST /api/orders`, Java class prefix
`/api`, method suffix `/orders`, and native service method calls provide evidence.
The reusable HTTP relation stays **candidate** because frontend base URL/proxy,
Spring host startup/scanning and deployment are not present or executed.

Follow-up work: native Vue SFC symbol/call support; adapter-specific completeness
checks beyond Python; broader workspace/overload cases; desktop feature/host and
HTTP deployment execution. Static contracts never establish runtime correctness.

Actual quality gates and limitations are in [the M5 results](../../../docs/design/architecture-model-m5-results.md).
