# Independent Agent continuation trial

On 2026-11-05, a separately spawned modeling Agent (`/root/independent_model_continuation`) authored and applied the preview business. This was an independent Agent context using the inherited model, with separate CLI subprocesses; it was not merely the parent Agent launching another CLI. No internal modeling LLM or provider credentials were used.

## Inputs and evidence read

- ENGINE: `F:/CodeBoarding`; Python `3.12.13`, invoked with `uv run --project F:/CodeBoarding --no-sync`.
- MODEL: `F:/CodeBoarding/examples/architecture_model/multilanguage/model/model.json`.
- TARGET roots: `F:/CodeBoarding/temp/m5/native-trial/target/frontend` and `F:/CodeBoarding/temp/m5/native-trial/target/backend`.
- Read `skills/codeboarding-modeling/SKILL.md`, `references/protocol.md`, `references/context.md`, `references/multilanguage.md`, and scenario/patch templates. The supplied repository AGENTS instructions were followed; `.codegraph/` is absent and no target AGENTS files were found.
- Read actual frontend `src/utils.ts:3` (`readDocument`), `:7` (`openDocument`), and `:11` (`previewDocument`). The new entry calls the existing helper with `preview.txt`.
- Read actual backend `src/lib.rs:3` command feature attribute, `:4` command delegation, `:8` feature-gated registration, `:10` handler macro; `src/utils.rs:1` filesystem service; and `Cargo.toml` optional Tauri dependency and desktop feature.
- Captured the complete model to a fresh temporary envelope before authoring; queried complete component/relation/binding/scenario ID inventories (all fit one bounded page), exact components, bindings, `open-document`, `read-file-ipc`, and facts source metadata. The complete model was never used as a replacement patch.
- Checked SHA-256 of each of the six bound source locations against actual target files. All match. Initial checker incorrectly looked for root identity under `source`, failed with `KeyError`, and was corrected to the snapshot-level `source_root_id`; the failed attempt did not write a model.

Model identity is `c3094cd2-b73e-4b0c-a3bb-6b9beb395a58`; revision changed **1 → 2**. Boundary remains TypeScript actions, candidate Tauri IPC and Rust filesystem service, excluding desktop host activation/runtime. Source snapshots remain frontend `777d089327dbd628da5a96dc9cf2383353cd4943be67f8bcfe420e153c8bf837` (digest `68e41c24084c9c32720bfa36dcd6dd569d0cd8dc23872d3746ac82879165c9bf`, commit `afb2aa70c0462fb4b96f741e2822cc6703013b80`) and backend `4910f61974e5b420b12ed9593b0d056849b2c8dd5ae9dc0a5e790955695fca60` (digest `5c0c4ee7f45d71895357626bc9f626271e057119ac8d41480db644083ee6c042`, commit `fa9567b46d60be8d94ed30f35dc6a3c4836d0c1e`). No maintenance observations are pending.

## Commands and saved artifacts

All helper invocations use this prefix from the engine root:

```powershell
uv run --project F:/CodeBoarding --no-sync python skills/codeboarding-modeling/scripts/model_context.py
```

Commands, in execution order (MODEL is the absolute input above; CACHE is `F:/CodeBoarding/temp/m5/independent-agent/read-before`; OUT is `F:/CodeBoarding/examples/architecture_model/multilanguage/model`):

```text
--engine F:/CodeBoarding capture --model MODEL --cache CACHE
list --cache CACHE --collection components --limit 10
list --cache CACHE --collection relations --limit 10
list --cache CACHE --collection bindings --limit 10
list --cache CACHE --collection scenarios --limit 10
get --cache CACHE --id open-document
get --cache CACHE --id read-file-ipc
get --cache CACHE --pointer /components
get --cache CACHE --pointer /bindings
get --cache CACHE --pointer /facts/0/source
--engine F:/CodeBoarding cli --response OUT/preview-validate.response.json -- model --file MODEL validate --patch OUT/preview-document.patch.json
--engine F:/CodeBoarding cli --response OUT/preview-diff.response.json -- model --file MODEL diff --patch OUT/preview-document.patch.json
--engine F:/CodeBoarding check --cache CACHE
--engine F:/CodeBoarding cli --response OUT/preview-apply.response.json -- model --file MODEL apply --patch OUT/preview-document.patch.json --expected-revision 1
--engine F:/CodeBoarding capture --model MODEL --cache F:/CodeBoarding/temp/m5/independent-agent/read-after
--engine F:/CodeBoarding cli --response OUT/preview-export.response.json -- model --file MODEL export-html --output OUT/preview-revision-2.html --source-map OUT/preview-source-map.json
```

The authored patch and full validate/diff/apply/export responses are saved under `model/` with those filenames. Validate and diff both returned `ok:true`, `valid:true`, candidate revision 2, and only `scenarios.preview-document` as changed. The Agent inspected both saved responses before apply. Freshness check returned revision 1 immediately before apply; apply used `--expected-revision 1` and committed revision 2. Fresh complete captures/indexes are temporary context under `temp/m5/independent-agent/`, not additional persistent models.

## Reuse and preservation

Only scenario `preview-document` was created. New stable step IDs are `preview-action`, `preview-ipc`, `preview-command`, `preview-service`, with explicit transitions and an explicit feature/host condition on the IPC hop.

Reused component IDs: `frontend-ui`, `ipc-client`, `rust-command`, `document-service`; their existing parent `backend` is retained. Reused relation IDs: `ui-client`, **`read-file-ipc`**, `command-service`. Reused bindings: `preview`, `invoke`, `command`, `registration`, `service`; existing `open` remains intact. Both immutable facts snapshots, all six bindings, all five components, all three relations, opinions, verifications and maintenance are unchanged. Existing `open-document` including its step IDs, claims, transitions and relation IDs compares deeply equal to its pre-write value.

`model/preview-preservation-check.json` records these equality checks, unique step IDs and unchanged IPC status. `model/preview-source-check.json` records all six successful hash checks. Counts changed from 2 facts / 6 bindings / 5 components / 3 relations / 1 scenario to the same counts with 2 scenarios.

## Actual checks and limits

The candidate IPC contract remains `candidate`; the new overall scenario remains an `inference`. Code establishes local calls and feature-gated registration, while desktop activation, installed handler, IPC delivery, file availability and rendering are unverified. No Rust/TypeScript runtime or desktop feature execution was claimed or performed. No facts export, binding refresh, test execution or repository source changes were needed for this scenario-only write.

HTML export succeeded using both explicit source roots. A bounded JSON parser checked embedded model identity/revision, both scenario IDs, and six snippet binding IDs. One initial `rg` HTML search accidentally produced a truncated console line; that output was not treated as complete context, and the subsequent parser checked only selected fields. Browser interaction checks were not performed by this Agent; switching scenarios, expansion, playback and evidence UI remain for the parent Agent's browser QA. Structural CLI validation and source hash agreement do not prove business execution.

Changes are confined to `model/` plus this explicitly requested report and temporary context envelopes. No git commit or push was performed.
