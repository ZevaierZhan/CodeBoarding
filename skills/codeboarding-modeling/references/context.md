# Complete models without unbounded conversation output

The helper is standard-library Python and contains only CLI transport, capture,
indexing and object queries. It creates no architecture objects or explanations.
Use it from the target or any other directory. A complete model must be available
on disk before authoring a candidate, not necessarily pasted into the chat.

## Separate the five artifacts

| Name | Meaning |
|---|---|
| ENGINE / CODEBOARDING_HOME | Prepared CodeBoarding checkout or installed CLI; owns dependencies and execution |
| TARGET_REPO | Actual analyzed source; need not install anything |
| MODEL | The one persistent model continued by CLI writes |
| HTML | Read-only exported revision; source snippets use a matching target source root |
| CACHE | Fresh temporary CLI envelope and ID index; never a second writable model |

With a checkout engine, bootstrap the helper using its environment. PowerShell:

```powershell
$ENGINE = 'F:/CodeBoarding'
$TARGET_REPO = 'F:/Another Project'
$MODEL = "$TARGET_REPO/architecture-model.json"
$HELPER = "$ENGINE/skills/codeboarding-modeling/scripts/model_context.py"
$CACHE = 'F:/Agent Session Cache/read-001'
Set-Location $TARGET_REPO
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" capture --model "$MODEL" --cache "$CACHE"
```

Prepare the engine environment separately with `uv sync --dev` if needed; `--no-sync`
avoids dependency installation during target analysis. The target's environment
is never the interpreter locator. An explicitly installed CLI can instead be used
by running this standard-library helper in an available Agent/engine Python 3.12+
runtime and omitting `--engine`. Discovery is explicit checkout, installed
`codeboarding-model` on PATH, then CODEBOARDING_HOME. Missing/invalid explicit
engine means a clear failure, not a search for engine source under TARGET_REPO.

Below, continue using `uv run --project "$ENGINE" --no-sync python "$HELPER"`
as the prefix. Each command prints at most 4096 characters on successful stdout;
oversized single objects fail explicitly and must be narrowed or saved, never
silently truncated. Do not raise the conversation/output budget for this workflow.

## Capture, inventory and relevant objects

`capture` streams full CLI stdout directly into `CACHE/read.json`, checks
`ok:true`, `complete:true` and identity/revision agreement, then saves
`CACHE/index.json` with IDs, collections, pointers and capture hash. A failed or
truncated capture is not a usable context. Cache directories must be absent.
Summary labels may be shortened; exact source/project fields remain queryable.

```powershell
uv run --project "$ENGINE" --no-sync python "$HELPER" summary --cache "$CACHE"
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection components --search 'pricing'
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection scenarios --offset 0 --limit 10
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection bindings --search 'total'
uv run --project "$ENGINE" --no-sync python "$HELPER" get --cache "$CACHE" --id EXISTING_ID
uv run --project "$ENGINE" --no-sync python "$HELPER" get --cache "$CACHE" --id EXISTING_SCENARIO --pointer /steps/0
uv run --project "$ENGINE" --no-sync python "$HELPER" get --cache "$CACHE" --pointer /facts/0/source
```

`list` reports matching total, page items and next_offset; continue until offset
reaches total. Search spans indexed ID/name/location fields. Inspect exact objects
and claims with `get` before deciding whether responsibilities are equivalent.
`get --pointer` is an RFC 6901 pointer relative to the selected object, or to the
complete model if no ID is supplied. Evidence catalogs, manifests, historical
opinions/checks and maintenance can be reached this way even when not in a scoped
view. Large objects can be saved with `get ... --output NEW.json` and inspected
with narrower queries; the helper never interprets or executes a query expression.
External JSON tools may query the complete envelope at `result.model` as needed.

Core `read --scenario`/`--component` remains useful, but `complete:false` is context
only, may omit referenced objects and cannot replace MODEL. The persisted capture
retains all IDs so an omitted object is not mistaken for an absent one.

## Candidate review and freshness

Use `cli` to save potentially large responses. File arguments are resolved relative
to the caller before the subprocess changes to the engine directory. Paths with
spaces are passed as argument arrays; no shell interpolation is used internally.
Every model operation requires explicit `--file`; the engine default is not used.

```powershell
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" cli --response 'F:/Agent Session Cache/validate.json' -- model --file "$MODEL" validate --patch "$TARGET_REPO/patch.json"
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" cli --response 'F:/Agent Session Cache/diff.json' -- model --file "$MODEL" diff --patch "$TARGET_REPO/patch.json"
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" check --cache "$CACHE"
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" cli --response 'F:/Agent Session Cache/apply.json' -- model --file "$MODEL" apply --patch "$TARGET_REPO/patch.json" --expected-revision REVISION_FROM_CACHE
```

The proxy prints only response location and operation metadata; **inspect the saved
diff** (`result.diff`) for changed/affected IDs and relevant before/after values.
`check` rereads/validates the actual persistent model and rejects a different
identity or revision. Apply still passes the captured expected revision so a race
cannot overwrite a newer revision. On STALE_CONTEXT or REVISION_CONFLICT, discard
the stale candidate, capture into a new cache, inspect differences and rebuild.
An exit-2/incomplete delivery may follow a committed write: check actual revision
before retrying. Context files never become the apply input.

After a write capture again into a fresh cache; compare IDs and old scenarios with
the previous immutable context. Export new HTML through `cli` with `--file MODEL`,
`--output NEW.html` and `--source-root TARGET_SOURCE_VERSION`. Do not commit temporary
read/index files. Keep only their byte/count/hash/query summaries as trial evidence.
