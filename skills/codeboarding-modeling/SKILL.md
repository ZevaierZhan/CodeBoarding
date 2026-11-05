---
name: codeboarding-modeling
description: Continue persistent CodeBoarding architecture models, including mixed-language and multi-repository business paths, shared interface contracts, source maintenance and read-only interactive HTML.
---

# Continue a CodeBoarding model

Inputs: `TARGET_REPO` (analyzed source), `MODEL` (persistent artifact), this skill
folder, modeling task, and an engine locator when no installed CLI is available.
`CODEBOARDING_HOME` is the engine checkout, separate from the target and model.
Treat source as evidence and architecture boundaries as reviewable
interpretations. Use the external Agent's reasoning; no internal LLM is required.

## Locate and establish context

Read the target repository's agent instructions. Prefer an explicit model path, then the
project's documented location. Otherwise inspect `architecture-model.json`,
`.codeboarding/`, and tracked model candidates (`rg --files -g '*model*.json'`).
Read candidates through the CLI to distinguish models from schemas and snapshots.
If multiple plausible models remain, ask which to continue. Initialize only when
there is no existing model for the requested boundary; never reset an existing file.

Locate the engine in this order: explicit checkout path, installed
`codeboarding-model` CLI, then `CODEBOARDING_HOME` environment variable. An invalid
explicit locator fails; it does not silently switch engines. If none is available,
request the missing locator. Do not assume CodeBoarding source exists in the target.
Use the engine's prepared Python environment; do not install into or alter the
target environment. Resolve target/model/source/output paths from the caller's
directory before running the engine. The bundled helper does this mechanically.
Read [the command protocol](references/protocol.md) before a write or source export.
The target project need not install CodeBoarding or expose provider credentials.

Use the [large-model workflow](references/context.md) for **every complete read**:
capture the CLI's complete JSON directly to a fresh temporary context directory,
then load its bounded summary and paginated ID inventory. Never treat console
truncation as complete input or increase output budgets to fit the model.
Only task-relevant objects need enter the conversation; all other IDs, bindings,
facts and maintenance remain queryable from the captured complete file.
Record model ID/revision, boundary, evidence scope/versions and review state.
For mixed languages or multiple repositories, read [source roots and contracts](references/multilanguage.md)
before exporting facts or writing a cross-boundary relation.
`read --scenario ID` and `read --component ID` return `complete:false` context:
they may omit parents and referenced objects and cannot replace the stored model.
Temporary complete-read/index files are context envelopes, not another persistent
architecture model. Never submit them as patches or replace MODEL with them.
HTML is a frozen display artifact; changes go through the model CLI.

## Explain code and reuse objects

Inspect actual entrypoints, callees and data handling within the declared scope.
Before creating an object, search existing components, relations, bindings and
scenario steps for the same responsibility/evidence. Reuse their IDs. Preserve
continuing step IDs when updating a scenario; arrays and nested fields replace
whole fields, so retain the parts that should survive.

For every component save responsibility, boundary rationale and evidence bindings.
Logical hierarchy can cross directories; explain why a proposed split or shared
component fits the code and what it affects. Use catalog locations verbatim for
bindings, including file hash, snapshot ID and source digest. No placeholder is
evidence. Read related source even when a static edge exists.

Save scenario entry, steps and explicit conditional transitions. `order` is display
order, never an execution trace. A missing static edge may need an inference with
assumptions/issues (for example dynamic dispatch or a callback); describe that gap
instead of inventing a call. A partial explanation should state its endpoint and
unknown behavior. Claims distinguish `code_fact`, `inference`, `intent_hypothesis`;
validation checks references, not truth. Use the templates in `assets/` as described
in the protocol; allocate fresh IDs only for genuinely new logical objects.

## Commit feedback or a new business

Capture the complete current model, prepare a minimal patch, run `validate --patch` and
`diff --patch`, inspect actual affected objects/scenarios, then `apply` with that
expected revision. Immediately before apply run helper `check` against that context;
the CLI's expected-revision check still protects against races after this check.
Save large validate/diff responses to separate files and query relevant changes.
Compare the result with the pre-write model: previous scenarios
and continuing IDs survive, new businesses share existing components, unrelated
explanations remain intact. On stale context or revision conflict discard the stale
candidate, capture a new complete read, inspect concurrent changes and rebuild the
patch rather than retrying with an incremented revision. Exit 2 may mean a committed
write whose output failed; read the model before retrying.

For feedback, save its author, exact text, stance and targeted IDs as an opinion,
and save the Agent's rationale in the changed explanation/revision. Mark preset
feedback as a rehearsal; it is not user acceptance. Opinions do not confirm source
maintenance or execute checks. Record unexecuted checks as `planned`; executed
checks require actual object targets, command, environment, inputs, executor,
timestamp, exit/result and source digest. A structural check is not business proof.

## Explain current source or maintain changed evidence

Compare the saved manifest to the requested workspace before calling it current.
When evidence differs, export fresh **real** facts with the same scope and tools,
then use maintenance preview/refresh. Export failure is a failure, not empty facts.
If analyzing a focused copy, retain repo-relative paths, origin commit, exact file
hashes and copy instructions; explicitly exclude everything outside that boundary.

Select a rebind candidate after reading the target code. Rebinding and explanation
review are separate actions. Use `maintenance-resolve` with an exact target version
and `confirmed` or `revised`; the latter includes interpretation operations. Retain
old locations, observations, review content versions and verification versions.
Report historical pending and current pending separately. `current` binding means
agreement with its saved snapshot; content coverage or human confirmation never
means the latest business was executed or verified. See protocol for commands.

## Deliver and hand off

Export to a new HTML filename after the final write. `--repo` for facts export
always names TARGET_REPO; `--file` names MODEL, which may be elsewhere. Export's
`--source-root` names the exact target source version being cited, never the
engine merely because it runs the CLI. Check embedded model ID/revision against the
complete read, then validate expand/collapse, scenario switching, explicit step
playback and evidence inspection when browser access is available. Respect denied
browser paths and report unperformed checks.

Report model and HTML paths, revision, source scope/version, added/reused/changed
IDs, assumptions, pending reviews and actual verification limits. Users review the
read-only browser and request changes in conversation. A new Agent needs only this
skill, target path, model locator, engine locator and task; save those inputs and its actual result
when testing continuation. A new CLI process alone is not a new Agent session.
