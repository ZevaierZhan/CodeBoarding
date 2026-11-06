# CLI and templates

Use Python 3.12+ and `uv sync --dev` in the CodeBoarding checkout. These commands
do not read `.env` or invoke an LLM. Below, replace uppercase arguments with actual
absolute paths/values. `CODEBOARDING_HOME` selects the prepared **engine checkout**
and execution directory. `TARGET_REPO` is analyzed source, `MODEL` is the persistent
artifact, and `--source-root` is the target source version cited by that model.
None is inferred from the Agent's current directory. Models may be outside the
target. Do not install dependencies or copy engine code into the target.
Use [context.md](context.md) to capture complete reads and large diffs directly to
temporary files; the raw commands below describe protocol, not conversation output.
Inspect `uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model --help` and the relevant subcommand's
help if working against another CodeBoarding version.

## Read and patch

```sh
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model schema
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL validate --patch PATCH
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL diff --patch PATCH
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL apply --patch PATCH --expected-revision REVISION
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL export-html --output NEW.html --source-root TARGET_REPO
```

Responses are JSON `{ok:true,result:...}`; check exit status and `ok`. Full read's
model is at `result.model`. Failures are `{ok:false,error:{code,location,message}}`.
`REVISION_CONFLICT` requires rereading and reconciliation; do not just increment
the expected number. Export refuses an existing output, including a model path.
Successful writes increment revision, including no-ops. Complete model replacement
is not a supported write protocol. Use `create`, `update` and `delete` operations.

For a genuinely new boundary, write a project JSON with `id`, `name`, `boundary`,
then `model --file NEW_MODEL init --project PROJECT.json --author AUTHOR`.
Initialization creates the model ID and revision 0, refusing existing paths.

Schema source: `architecture_model/schema.py`; invariants:
`architecture_model/validation.py`; semantics and error list:
`docs/architecture-model.md`. Consult these in the CodeBoarding checkout when
building less common objects. The portable skill does not bundle a stale schema.

For the optional schema 1 `analysis_kind` / `facet_order` / `facet_checks`
capability, follow [analysis-topics.md](analysis-topics.md) before authoring or
updating a topic. Unknown fields and unsupported versions fail without migration.

### Template expansion

`assets/*.json.template` are text templates, **not executable patches**. Each
`$slot` is a complete JSON value: substitute it with `json.dumps(actual_value)`
using Python `string.Template.substitute`, then parse JSON. Allocate new opaque
IDs (for example `str(uuid.uuid4())`) once and save them; supply existing IDs when
reusing objects. Resolve real binding IDs from the complete model first. These
templates deliberately carry no default IDs, fake locations or fabricated hashes.

- `component.json.template`: one component with an inference claim. Supply
  `component_id`, `name`, `responsibility`, `rationale`, `parent_id`, `binding_ids`,
  `explanation`, `assumptions`, `issues`. Assumptions or issues must be nonempty.
- `scenario.json.template`: scenario object. Supply `scenario_id`, `name`,
  `entry_step_id`, `steps`, `order`, `transitions`, `explanation`, `binding_ids`,
  `assumptions`, `issues`. Each step has `id`, `component_ids`, `binding_ids`,
  `claim`; each transition has `source_id`, `target_id`, `kind`, `condition`.
- `patch.json.template`: supply `author`, `summary`, `operations`. A create uses
  `{action:"create",collection:"components",id:ID,value:COMPONENT}` (as JSON with
  quoted keys). An update uses the existing ID and only changed fields in `value`.
  Fields replace in full; include unchanged steps when replacing `steps`.

New evidence: copy the entire real facts snapshot using a `create` operation on
`facts`, ID equal to its exported `id`. Create a binding with `id`, `snapshot_id`,
`source_version` (snapshot's `source.digest`), `location` copied exactly from
`symbols` or `file_locations`, and `status:"current"`. Facts are append-only.

## Source maintenance

Preinstall Node, Pyright language-server JS and Tokei; supply executable paths
explicitly. The CLI does not install them or silently choose replacements.

```sh
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model facts export --repo TARGET_REPO --project-id PROJECT_ID --node NODE --pyright PYRIGHT_JS --tokei TOKEI --output NEW_FACTS.json
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance-preview --facts NEW_FACTS.json
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance-refresh --facts NEW_FACTS.json --token PREVIEW_TOKEN --author AUTHOR --expected-revision REVISION
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance --binding BINDING_ID
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance-rebind --item ITEM_ID --candidate EXACT_CANDIDATE_KEY --author AUTHOR --reason REASON --expected-revision REVISION
uv run --directory CODEBOARDING_HOME --no-sync python -m architecture_model model --file MODEL maintenance-resolve --item ITEM_ID --review REVIEW.json --expected-revision REVISION
```

Preview is read-only. Refresh saves comparison history and the new immutable
catalog, leaving bindings and explanations alone. After each write reread revision
and current coverage; explanation edits can derive a new review context.
Choose candidates explicitly; ambiguity is not resolved by first-match selection.
The entire containing file is the hash granularity. Scope/config/tool differences
can make comparisons indeterminate; they are not evidence of deletion.

Review JSON: `author`, `reason`, `outcome` (`confirmed` or `revised`),
`source_version` equal to the observation's target digest, optional `operations`.
A `revised` review must change an affected component/relation/scenario. Binding
changes use rebind, not review operations. Old pending contexts remain historical
until explicitly reviewed against their own evidence. Review confirmation is a
version-specific interpretation judgment, not runtime test success.
