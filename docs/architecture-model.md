# Architecture model CLI (M1)

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
Agent maintenance and structured review. Automatic refresh/rename/rebinding (M2),
interactive diagrams and scenario playback (M3), MCP, internal business generation,
accounts and approval workflows are not implemented.
