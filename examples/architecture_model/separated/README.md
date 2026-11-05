# Another target, a separate CodeBoarding engine

The engine owns its Python environment and native tools. The target owns analyzed
source; the model is one persistent explanation artifact, and HTML is a generated
read-only artifact. Complete-read envelopes/indexes are temporary Agent context,
not another model. This example tests the same M4 workflow with an independent
source copy and large, explicitly synthetic context drills.

## Use the Skill on an existing target

Run from anywhere, including a target whose path contains spaces. These PowerShell
commands use the prepared engine environment without installing into the target:

```powershell
$ENGINE = 'F:/CodeBoarding'
$TARGET_REPO = 'F:/Another Business Project'
$MODEL = "$TARGET_REPO/architecture-model.json"
$HELPER = "$ENGINE/skills/codeboarding-modeling/scripts/model_context.py"
$CACHE = 'F:/Agent Session Cache/read-001'
Set-Location $TARGET_REPO
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" capture --model "$MODEL" --cache "$CACHE"
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection components --limit 10
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection scenarios --limit 10
uv run --project "$ENGINE" --no-sync python "$HELPER" list --cache "$CACHE" --collection bindings --limit 10
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" check --cache "$CACHE"
uv run --project "$ENGINE" --no-sync python "$HELPER" --engine "$ENGINE" cli --response 'F:/Agent Session Cache/html-response.json' -- model --file "$MODEL" export-html --output "$TARGET_REPO/architecture-export.html" --source-root "$TARGET_REPO"
```

The export example uses current target bytes and a new output filename. If bindings
cite another source version, supply that matching target copy instead; mismatched
bodies are withheld. The model must already exist for capture. For a new target, initialize once with a
declared project boundary using the protocol in the Skill; never reset an existing
model. Supply the external Agent the Skill path, TARGET_REPO, MODEL, engine locator
and task. It can query exact objects by ID/JSON pointer, save a large object to a
temporary file, author a minimal patch, save validate/diff outputs, check freshness
and apply at that revision. It should never paste the entire model into chat.

Engine resolution is explicit checkout, installed `codeboarding-model` on PATH,
then CODEBOARDING_HOME. A bad explicit checkout or missing engine fails clearly.
The helper resolves file options from the caller directory before running in the
engine directory. Facts export's `--repo` is TARGET_REPO; export's `--source-root`
is the cited version of **target source**. MODEL may be elsewhere entirely.
No target provider key, Python environment changes or engine-source copy is needed.

Detailed commands: [Skill context workflow](../../../skills/codeboarding-modeling/references/context.md).

## Reproduce the separated large-target preparation

From any directory, choose absent target and cache directories and existing native
tools. This is the actual preparation command shape used in the trial:

```powershell
$ENGINE = 'F:/CodeBoarding'
uv run --project "$ENGINE" --no-sync python "$ENGINE/examples/architecture_model/separated/prepare_trial.py" --engine "$ENGINE" --target 'F:/New Separated Target' --cache 'F:/New Session Cache/preparation' --node (Get-Command node).Source --pyright "$ENGINE/temp/p0-tools/node_modules/pyright/langserver.index.js" --tokei "$ENGINE/temp/p0-tools/tokei.exe"
```

Paths to Pyright/Tokei are existing tools in this author's engine, not an automatic
installation convention. Substitute your actual installed tool paths. Engine
dependencies must have been prepared separately (`uv sync --dev` in the engine).

Preparation materializes only the four independent order fixture Python files,
exports real facts, applies the authored [fixture specification](fixture.json),
then creates 128 explicitly labeled synthetic repetitions of the purchase path.
These are context-size drills, not 128 separate real businesses or extra facts.
All business explanations/IDs and extension parameters live in the specification;
the preparation script only transports data and expands that declared fixture.
The Skill helper itself contains no business text, model-specific IDs or LLM calls.

The resulting revision-2 model has 4 components, 5 bindings and 129 scenarios,
about 9.65 MB in the actual run. Start a **fresh-context Agent** from the target
with only the five inputs above and ask it to explain quotation using existing
entry/shared-pricing objects. Mechanical preparation or a new CLI process is not
fresh-Agent acceptance; that independent session is recorded separately.

Temporary read/index files remain outside the target and outside Git. Evidence
archives preserve the actual persistent target model before/after and generated
HTML, not copies of temporary contexts. [P2 acceptance](../../../docs/design/architecture-model-m4-p2-results.md)
records actual paths, exact fresh-Agent input, bounded queries, preservation and
remaining gates. The original [M4 revision-13 model](../codeboarding/README.md)
and previous fresh-Agent evidence remain unchanged.
