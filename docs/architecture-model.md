# Architecture model CLI (M1 + M2)

An external Agent reads source, writes its interpretation, and revises the same
logical objects over successive sessions. CodeBoarding validates declared structure,
references, versions and writes. It does not prove an explanation correct.

Install the repository with `uv sync --dev`. Use `uv run codeboarding-model` or
`uv run python -m architecture_model`. Neither entry goes through the existing
analysis bootstrap. Python 3.12 is required by this repository.

## Start a model and continue it in another session

Write `project.json`:

```json
{"id":"orders-project","name":"Orders","boundary":"Local order handling; external payment is outside this model."}
```

```sh
uv run codeboarding-model model --file architecture-model.json init --project project.json --author analysis-agent
uv run codeboarding-model model --file architecture-model.json read
uv run codeboarding-model model --file architecture-model.json read --scenario purchase
uv run codeboarding-model model --file architecture-model.json read --component pricing
```

Initialization creates a model UUID and revision **0**, with a project boundary and
an initial revision record. The caller supplies an enduring project ID. Initialization
refuses any existing file, including a corrupt one. It never resets a model.

Every success is `{"ok":true,"result":...}` on stdout. Errors are
`{"ok":false,"error":{"code":...,"location":...,"message":...}}`, exit 1.
Logs go to stderr. Output delivery failure exits 2 and means the command's result
could not be delivered; a write may already have committed. Read the revision.
`--help` is ordinary argparse help, exit 0.

Reads include model identity, revision, scope and `complete`. Scoped reads retain
all fact/binding evidence and review records, but filter components, scenarios and
related relations. They can omit a component's parent or other referenced objects;
they are context views, **not standalone valid models**. Full and partial read
envelopes cannot be submitted as patches. This API has no whole-file replacement
command. Re-read the complete current model when resolving a conflict.

## Export real facts without a provider

```sh
uv run codeboarding-model facts export --repo /path/to/python-project --project-id orders-project \
  --node /absolute/path/to/node --pyright /absolute/path/to/pyright/langserver.index.js \
  --tokei /absolute/path/to/tokei --output facts-001.json
```

All three tools must already exist. Paths are resolved before launching a separate
worker; no automatic tool installation or provider setup is enabled. The worker
sets `CODEBOARDING_TELEMETRY=false` and `DO_NOT_TRACK=1` **before native imports**.
The normal model commands do not import StaticAnalyzer or telemetry, open an LSP,
or read `.env`. No API key is needed.

Explicit absolute commands take precedence over both installed tools and PATH
discovery in the native resolvers. Their complete argument lists are preserved;
default unresolved commands continue to use the existing discovery order. A failed
explicit tool is an export failure, not a request to try another installed tool.
Snapshot `tools.node`, `tools.pyright_js` and `tools.tokei` come from the resolved
commands. `tools.python_command` and `tools.tokei_command` store their full argv
arrays as JSON-encoded strings for auditing.

The worker uses PythonAdapter discovery, AST syntax preflight and the real
StaticAnalyzer/LSP pipeline with `skip_cache=True`. It closes clients in an exit
stack even on extraction failure. It rejects mixed-language analysis roots, missing
files in the result, missing declared Python callables, native ERROR logs, invalid
syntax and source changes observed across extraction. It never substitutes an
empty successful graph or enters LLM analysis. A Python root without any source
files is rejected; a valid file containing only constants may have no callables.
The parent bounds analysis to 180 seconds and terminates its worker process group
(Windows process tree) on timeout. A facts failure never writes an explanation.

Facts publication refuses existing output paths. Each snapshot contains a project
ID, content-derived snapshot ID, scoped source manifest and digest, Git commit
context if available, symbols, file locations, call records/sites, explicit tool
paths, and limitations. Source hashes cover exact file bytes, including dirty and
untracked Python files admitted by discovery/ignore rules. Symbol `content_hash`
is the **containing file's SHA-256**, not a function-body hash. Lines are one-based;
call-site columns preserve the native engine's indexing.

The digest identifies the declared Python extraction scope, not every file in the
repository or installed dependencies. External libraries, environment and analysis
configuration can affect resolution; their complete contents are not fingerprinted.
Git HEAD alone is never presented as the content version. This projection includes
native graph symbols and graph-internal calls; external/unresolved call sites and
non-call reference edges are not exported. Calls are static records,
not executions, and dynamic dispatch/registration can be incomplete. Native group
names, clustering and generated descriptions do not become architecture facts.

## Schema and evidence

The runtime source is `architecture_model/schema.py`. Export the exact JSON Schema:

```sh
uv run codeboarding-model model schema > schema-response.json
```

The JSON Schema is the response's `result` property. The committed raw
[schema reference](architecture-model-v1.schema.json) is generated directly with
`Model.model_json_schema()`. Every domain object forbids unknown fields, including nested locations,
claims, transitions and verification records. Dynamic maps are limited to explicit
ID/path-indexed fact catalogs and tool metadata. Unknown schema versions are
rejected without migration. JSON duplicate keys are also rejected.

| Collection | Main fields and meaning |
|---|---|
| `facts` | Immutable snapshot catalogs, copied from independently published facts files. Snapshot ID hashes canonical content excluding `id`; source digest hashes the file manifest. Copying preserves offline historical reads without a multi-file transaction. |
| `bindings` | Stable `id`, `snapshot_id`, `source_version`, `location`, `status`, review `reason`, append-only `history`. Current means matching that specific snapshot, not matching today's working directory. |
| `components` | Stable `id`, `name`, `responsibility`, `rationale`, `parent_id`, `binding_ids`, `claim`. Empty parent is a root. Membership is independent of native ownership and can overlap. |
| `relations` | Stable `id`, component `source_id`/`target_id`, `meaning`, `claim`. Inference is permitted without a native call edge. |
| `scenarios` | Stable `id`, name, `entry_step_id`, stable-ID `steps`, explicit `order`, explicit `transitions`, claim. Each step has component IDs, bindings and its own claim. |
| `opinions` | Author, exact text, stance and referenced object IDs. Acceptance never changes a claim's kind. |
| `verifications` | Planned/executed, referenced objects, command, environment, inputs and source version. Executed requires executor, timestamp, exit code and result; planned forbids execution results. |
| `revisions` | Contiguous revision history from zero, author, timestamp, supplied summary, computed changed object IDs and affected scenario IDs. Historical IDs can refer to deleted objects. |

IDs are nonempty caller-chosen opaque strings and unique across project, model,
top-level objects and all scenario steps. Names, source paths, parent and list
indices never generate replacement identities. A scenario update can deliberately
replace its steps, but the Agent must preserve the IDs of continuing logical steps.
Two scenarios reference the same component ID to share it; the model does not
guess semantic equivalence between separately created IDs.

A claim contains `kind` (`code_fact`, `inference`, `intent_hypothesis`), explanation,
binding IDs, assumptions and issues. All claims need evidence; inferred claims
also need assumptions or explicit uncertainty. `code_fact` is a declaration by the
author; the validator checks its references, not its truth. There is no implicit
promotion after user approval, matching source, or an executed check.

Current symbol or file bindings must exactly match their catalog's version,
location, kind and content hash. `changed`, `missing`, `ambiguous` bindings require
a reason and may retain an unavailable historical snapshot/location. They do not
trigger filesystem access or automatic rebinding. Changing a binding's location or
version requires appending the previous snapshot/version/location and a reason to
history. Previous history cannot be removed. Merely marking an unchanged location
missing/changed keeps its previous version and location directly in the binding.
An internal reference to an absent binding ID is always rejected.

Component parent links must be acyclic. Scenario `order` lists every step exactly
once; transitions reference steps within that scenario and carry an explicit
condition and kind (`next`, `branch`, `return`, `loop`). Cyclic transitions are
legal. Display order is not a claimed execution trace. Cross-scenario subroutine
references are not part of this version; shared behavior is represented by shared
components and explicit steps.

## Patch protocol and review

Create a component with an explicit `create` operation after first creating its
bindings and fact catalog in the same patch. To copy facts into a patch, put the
entire exported snapshot in the operation's `value`, using its `id` as operation ID.
The complete candidate is validated, so operations can repair references together.
For a later revision:

```json
{
  "author":"analysis-agent",
  "summary":"Clarify the shared pricing responsibility",
  "operations":[
    {"action":"update","collection":"components","id":"pricing",
     "value":{"responsibility":"Calculate the price used by purchase and quotation."}}
  ]
}
```

```sh
uv run codeboarding-model model validate --patch patch.json
uv run codeboarding-model model diff --patch patch.json
uv run codeboarding-model model apply --expected-revision 3 --patch patch.json
```

Use `model --file PATH ...` to select another model. `validate` without a patch
validates the stored complete model. `validate --patch`, `diff` and `apply` call the
same candidate builder and validator. Validate/diff/read never change model bytes
or revision. Diff contains before/after values from actual objects, changed object
IDs, and affected components/relations/scenarios; it does not trust the supplied
summary. Binding changes propagate to referencing components and steps; component
changes affect referencing scenarios. Relation changes also affect their endpoints'
scenarios. No business correctness or automatic source impact inference is claimed.

Creating, updating or deleting an opinion/verification also affects scenarios
explicitly named in its `object_ids`, and scenarios that own referenced steps.
Both previous and new targets are considered. Changing only the text/result still
reports those scenarios. The same computed list is saved in the revision record.

Operations have exactly `action`, `collection`, `id`, `value`:

- `create` requires an absent ID and the object's required schema fields. It cannot overwrite.
- `update` requires an existing ID. Omitted fields remain. Present fields replace
  **the entire field**, including nested objects and arrays. There is no recursive
  merge or array-index editing. Arrays clear with `[]`; a parent clears with `""`;
  required text does not clear with `""` or null. Identity cannot change.
- `delete` requires an existing ID and an empty/omitted value. References must be
  repaired in the same candidate. Facts only permit create.

Split/merge/reparent are compositions of these operations: retain the appropriate
ID, create new identities, change membership/parents and explicitly revise each
scenario/relation/opinion/check reference before deleting an old ID. The library
never redirects to the first split result, or deletes/merges steps automatically.
An effective no-op patch still consumes one revision on successful apply.

After `REVISION_CONFLICT`, read again, inspect current IDs and explanations,
reconstruct the patch and validate/diff it against the latest model. Do not simply
retry with a higher revision while assuming the old context still applies.

## Transaction boundary and errors

A resolved model path uses a sibling `.lock` via FileLock. Within one cross-process
critical section apply reads the newest full file, checks expected revision,
constructs/validates the complete candidate and writes/fsyncs a same-directory
temporary file. **`os.replace` is the commit point**. One success adds one revision.
Readers see a complete snapshot. No rollback-overwrite compensation is used.

Pre-commit validation, temporary creation/write/fsync and replace failures preserve
the previous model's bytes and revision. Initialization failure leaves no valid
model artifact. Output errors after commit do not undo it. Guarantees assume a
local filesystem with normal OS lock/atomic replacement behavior; directory fsync,
power-loss durability, hostile noncooperating writers, network filesystems and
multi-file transactions are outside this contract. Do not remove lock paths while
commands are running.

| Code | Meaning |
|---|---|
| `USAGE_ERROR`, `JSON_INVALID`, `SCHEMA_INVALID`, `UNSUPPORTED_VERSION` | Bad arguments, JSON, domain shape or schema version |
| `DUPLICATE_ID`, `NOT_FOUND`, `ALREADY_EXISTS`, `IMMUTABLE` | Create/update/delete/initialization identity violation |
| `DANGLING_REFERENCE`, `PARENT_CYCLE`, `STEP_ORDER` | Internal reference or structural inconsistency |
| `FACTS_MISMATCH`, `BINDING_MISMATCH`, `HISTORY_REQUIRED` | Catalog/version contradiction or discarded binding history |
| `REVISION_INVALID`, `REVISION_CONFLICT`, `LOCK_TIMEOUT` | Invalid revision history, optimistic conflict, or apply lock wait exceeded |
| `IO_ERROR`, `SAVE_FAILED` | Read/lock/filesystem error, or failure before atomic commit |
| `TOOL_MISSING`, `FACTS_FAILED` | Explicit tools unavailable or native extraction failed |

Errors carry an object/JSON-pointer location, or filesystem path where applicable.
The worker logs tracebacks on stderr. Model errors preserve exception chains in the
Python library; CLI messages are compact machine-readable summaries.

## Reproduce the continuous example

See [the example guide](../examples/architecture_model/README.md) and the
[actual validation record](design/architecture-model-m1-results.md). M1 provides
Agent modeling and structured review. M2 source maintenance is described below.
Interactive diagrams and scenario playback (M3), MCP, internal business generation,
accounts and approval workflows are not implemented.

## M2 source maintenance

Run every command through `uv run codeboarding-model`, using `model --file PATH`
to select the same model. Export a fresh **complete** Python snapshot using the
explicit-tool `facts export` command above. Exporting facts never edits a model.

```sh
uv run codeboarding-model model --file model.json maintenance-preview --facts target.json
uv run codeboarding-model model --file model.json maintenance-refresh --facts target.json \
  --expected-revision 3 --token TOKEN_FROM_PREVIEW --author business-agent
uv run codeboarding-model model --file model.json maintenance --scenario business-A
uv run codeboarding-model model --file model.json maintenance --component pricing
uv run codeboarding-model model --file model.json maintenance --binding bind-total
```

Preview validates the target snapshot/project and compares **each binding against
its own saved baseline**. It includes model ID/revision, target snapshot, content
version and Git context, original version/location/hash, new candidates and their
reasons, incident calls before/after, and affected components/relations/scenarios/
steps. `pending_ids` includes earlier unresolved observations and proposed ones.
The token covers the complete preview and revision. Preview leaves bytes intact.
Refresh requires that token and expected revision, then recomputes within the same
ModelStore lock used by apply. It imports the immutable facts once and appends
new observations. It does not edit bindings, business explanations, opinions or
verification records. A stale revision fails before any write; a wrong token
fails with `PREVIEW_CONFLICT`.

There are three independent concepts:

| Field | Meaning |
|---|---|
| `binding.snapshot_id/source_version/location/status` | Evidence currently cited by that binding. `current` still means exact agreement with **that saved snapshot**. |
| `maintenance_target_snapshot_id` | Most recently committed comparison target; it does not advance binding evidence. |
| `maintenance[].disposition/resolution` | Observation against a particular target; unresolved non-unchanged observations need Agent review. |

Full and scoped `model read` retain maintenance history. `model maintenance`
filters observations by binding/component/scenario and lists unresolved IDs.
Maintenance observations retain historical object IDs even after explicit object
deletion; these are audit references, not live membership requirements.

### Judgement and candidates

`unchanged` means the exact same immutable snapshot, or equal containing-file
bytes and equal incident call endpoints under matching extraction descriptors.
Different global source digests alone do not trigger review. Different Git context
alone is mechanical metadata. Positions and call sites are reported; static calls
are not an execution trace.

`changed` means file bytes/call endpoints differ, or one plausible replacement
exists. Every binding to a changed file is conservatively affected, including
insertion of blank lines and changes to **another function in that file**. There
is no function-body precision. `ambiguous` retains multiple plausible candidates;
the engine does not rank and adopt the first. Candidate reasons include matching
file bytes, terminal symbol name/kind, and same-file/kind rename possibilities.
File-byte matches are deliberately weak symbol evidence: multiple functions can
share the same file hash. File moves and renames always require Agent inspection.

`missing` means the original location is absent under comparable complete
extraction rules and no heuristic candidate exists. It is an evidence judgement,
not deletion of the binding or a proof that equivalent business behavior vanished.
`indeterminate` means the old catalog is unavailable/inconsistent or extraction
descriptors are absent/different. Excluded files are never reported deleted on the
strength of an equal project ID or human-readable scope string.

New exports store `tools.maintenance_scope`, a canonical descriptor containing
the Python discovery/static-engine/ignore implementation digest, effective ignore
patterns (including defaults), explicit executable/Pyright entry-file hashes,
root Pyright/pyproject/setup configuration hashes and completion declaration.
The implementation digest includes the exporter. An independent strict inventory
rejects unreadable directories/files, escaping/repeated symlink directories and
differences from native discovery; native silent skips cannot establish deletion.
The worker checks rules and source before/after extraction and rejects errors,
syntax failures and incomplete results. This does not fingerprint all installed
packages, Pyright dependency contents, environment or external libraries. Supplied
snapshots are local trusted artifacts, not cryptographically authenticated exports.

### Explicit rebinding and explanation review

```sh
uv run codeboarding-model model --file model.json maintenance-rebind \
  --item OBSERVATION_ID --candidate 'policies/rates.py|policies.rates.total' \
  --expected-revision 4 --author business-agent --reason 'Inspected moved pricing implementation'
```

This chooses exactly a candidate saved in the observation, imports no new facts,
preserves binding ID and appends its previous location/version/reason to M1 history.
It does **not** close review or rewrite explanations. Selection from an older
observation explicitly selects that historical target; the engine does not replace
it with the latest target. A same-evidence selection is a no-op with one revision.

Write a review JSON file, then submit it:

```json
{
  "author": "business-agent",
  "reason": "Inspected the target pricing change and its A/B consumers; both explanations still hold.",
  "outcome": "confirmed",
  "source_version": "EXACT_64_HEX_TARGET_SOURCE_DIGEST",
  "operations": []
}
```

```sh
uv run codeboarding-model model --file model.json maintenance-resolve \
  --item OBSERVATION_ID --review review.json --expected-revision 5
```

The Agent reviews all affected interpretation IDs listed by the selected
observation. The record saves those IDs, author, timestamp, reason, outcome and
exact target content version. `confirmed` permits keeping original text;
`revised` requires an actual change to an affected component/relation/scenario.
Optional `operations` use ordinary M1 patch semantics and commit together with
the resolution. They may edit components, relations, scenarios, opinions and
verifications; facts and bindings are handled separately. Neither accepting a
candidate nor user acceptance proves business correctness. Previous verification
versions and results remain historical; a new check requires explicit submission.

Only the named observation closes. Other target-version reviews remain pending.
S0→S1→S2 therefore retains unresolved S1 changes even if S2 changes only an
unrelated file or reverts the source. Bindings still citing an older baseline may
have another observation for S2; Agent review is deliberately version-specific.
Repeating an identical binding-basis/target pair reuses the saved observation,
including a completed resolution. It never resets it or duplicates facts. Every
successful refresh, including a no-op, consumes exactly one revision like M1 apply.
General patches cannot edit/delete maintenance observations.

### M1 compatibility and errors

The strict v1 model envelope adds optional `maintenance` (default `[]`) and
`maintenance_target_snapshot_id` (default `""`). M1 files read directly without a
write or revision change. Their first successful M2 write serializes these fields,
preserving existing identities, explanations, revision history and fact catalogs.
Use the M2 reader afterwards: older M1 binaries reject the additional fields.
The raw v1 JSON Schema is regenerated to include these strict optional fields.
There is no broad migration platform or automatic revision reset.

Historical **facts** retain their exact original schema/content/digest. M2 never
adds descriptors to old catalogs or recomputes their IDs. Comparing an old M1
snapshot to a different export produces `indeterminate`; the Agent can inspect
new evidence, explicitly rebind to a candidate and explicitly resolve the review
to establish its M2 baseline. Re-exporting does not silently upgrade the old one.

| Additional error | Meaning |
|---|---|
| `COMPARISON_INVALID` | Malformed extraction descriptor; no successful comparison or write |
| `PREVIEW_CONFLICT` | Token does not describe this revision/model/target |
| `MAINTENANCE_INVALID` | Stored maintenance target/candidate/review contradicts its catalog |
| `CANDIDATE_INVALID` | Explicit selection absent from the stored observation |
| `REVIEW_INVALID` | Wrong review version, already closed/unchanged item, forbidden operations or ineffective revision |

M1 `REVISION_CONFLICT`, schema/reference/history and atomic-save errors still apply.
Uncertainty is a persisted disposition, not a fake successful deletion. Failed
exports publish nothing. All pre-commit failures preserve bytes and revision;
output failures after replacement retain exit 2 and may already have committed.

See the [M2 design](design/architecture-model-m2.md),
[continuous example](../examples/architecture_model/README.md) and
[M2 validation](design/architecture-model-m2-results.md).
