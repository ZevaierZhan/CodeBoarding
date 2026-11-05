# Real CodeBoarding continuous model

For an independent target and large-context continuation, use the
[separated ENGINE/TARGET example](../separated/README.md). Its Skill workflow
captures full reads outside conversation and does not rely on the target being
the CodeBoarding checkout. The original 0–13 trial below remains historical evidence.

Open [index.html](index.html) to inspect revision **13** of model
`ba06c25c-e8de-4781-8a09-e7643b9e4721`. Its source boundary is
`architecture_model/*.py` from CodeBoarding, not all CodeBoarding behavior.
Architecture boundaries are evidence-backed Agent interpretations. The final
document includes a controlled-copy source experiment; it does not claim that
experiment was committed into production code.

Continue [model.json](model.json) for this boundary. Stage `*.model.json.gz` files are
read-only audit snapshots, not alternative models to continue. HTML is read-only;
ask the Agent for changes in conversation. [scope.json](scope.json) records the
origin commit, exact source manifest, copy root, exclusions and Git-context limits.

## Load the Skill without global installation

Give an external Agent this prompt, replacing the checkout path if necessary:

> Read F:/CodeBoarding/skills/codeboarding-modeling/SKILL.md and follow it.
> Repository: F:/CodeBoarding. Continue the model at
> F:/CodeBoarding/examples/architecture_model/codeboarding/model.json. Task: explain or revise
> [the requested business] using real code, reusing the existing objects, and
> export a new HTML document.

For that original self-model, engine and target both happen to be F:/CodeBoarding;
provide the engine locator explicitly when loading the current Skill. For another
project pass its own TARGET_REPO and MODEL separately, as in the example above.

This explicit file-loading method was executed by the separate fresh-context
Agent in [03-agent-session.md](03-agent-session.md). No user-wide configuration
was changed. Distribute the complete `skills/codeboarding-modeling` folder; its
entrypoint links the bundled protocol and three templates. Automatic discovery
in other Agent products and global installation were not tested. CodeBoarding
must be available separately: run `uv sync --dev` in its Python 3.12+ checkout.

Inspect or export from the CodeBoarding root:

```sh
uv run python -m architecture_model model --file examples/architecture_model/codeboarding/model.json read
uv run python -m architecture_model model --file examples/architecture_model/codeboarding/model.json maintenance
uv run python -m architecture_model model --file examples/architecture_model/codeboarding/model.json export-html --output temp/m4-current-workspace.html --source-root .
```

The last command deliberately checks the **current workspace**. Three final viewer
bindings cite the controlled copy, so their bodies will be withheld against the
unmodified workspace. It must not silently substitute current source for those
versions. To reproduce the exact final snippets, use the source copy below.
Choose a new HTML output path on every export; export refuses overwrites.

## Reproduce the recorded sequence

Node, Pyright JS and Tokei must already be installed. Example PowerShell command
using this environment's existing tools, run from the repository root:

```powershell
uv run python examples/architecture_model/codeboarding/replay.py --output temp/m4-new-replay --node (Get-Command node).Source --pyright temp/p0-tools/node_modules/pyright/langserver.index.js --tokei temp/p0-tools/tokei.exe
```

Use an absent output directory. Replay creates a fresh model for an independent
experiment (new model UUID); it never resets or rewrites the delivered model.
It copies the actual 12 subsystem Python files, retaining `architecture_model/`
paths, exports real facts, uses the four recorded A–D patches, performs the exact
controlled change from [replay.json](replay.json), and executes its explicit
maintenance actions. Locations/snapshot digests are rebound to the new real
export; identities and authored explanations remain in the patch data.

The original run and successful replay both used unmodified product Python at
`34b4e48f2388049eeaf180efcbf285029d7b384b`; a later product version may require
reviewing the patches and marker. Replay refuses product bytes that differ from
the declared manifest. It reruns structural verification and records its own
model ID, command, environment, time and result instead of inheriting an executed
claim from the original run. The replay does not launch a new reasoning
Agent. Actual fresh-Agent evidence is stage C, separate from this CLI replay.

The new output contains `model.json`, `index.html`, the source copy, both exported
catalogs, all applied patches, reviews and a command journal. Export again using:

```sh
uv run python -m architecture_model model --file temp/m4-new-replay/model.json export-html --output temp/m4-new-replay/reexport.html --source-root temp/m4-new-replay/source
```

For the delivered model, `temp/m4-source` was the original execution copy; after
replay, `temp/m4-new-replay/source` has the same controlled Python bytes and can
also supply hash-checked snippets for the delivered model. The copy's Git context
can be inherited from its enclosing checkout; exact `source.files` identifies
bytes, including the controlled change, regardless of HEAD.

## Audit artifacts

| Stage | Revision | Saved result |
|---|---:|---|
| Initialize | 0 | project boundary, one persistent model ID |
| A | 1 | 7 logical components, 26 bindings, 5 relations, real facts |
| B | 2 | `read-to-html`, 7 steps, planned human/business check, first HTML |
| C | 3 | independent Agent adds `agent-submits-patch`, 11 steps; reuses cli/store/validation |
| D | 4 | preset feedback opinion, two explanation edits, actual revision-3 structural verification |
| E comparison | 5 | new real catalog, affected explanation observations, pending HTML |
| E rebind/review | 6–11 | 3 explicit candidate choices, 3 confirmations; original evidence retained |
| E explanation update | 12–13 | publication prerequisite clarified, new export explanation confirmed; 2 other content contexts remain pending |

`commands.json` and `03-commands.json` are compact indexes. Their sibling `.json.gz`
files preserve the full original command records losslessly, with raw SHA-256 in
the index. Historical model snapshots and full maintenance reports are also
losslessly compressed; read with Python `gzip.open(path, 'rt', encoding='utf-8')`.
Stage C also retains its actual response files and one-off authoring
transcript as `.py.txt`; that transcript is historical, not an executable Skill
helper. The authored JSON patch is canonical. The controlled modification is
reviewable as [controlled-source.patch](controlled-source.patch); only its isolated
copy changes, and the original source manifest still matches production.

Two pending contexts at revision 13 are intentional: the later viewer explanation
edit changes coverage for `e-projection` and `e-snippet`. Older confirmations remain
visible; they do not automatically cover the revised explanation. The planned
business check remains planned, and the executed check records only revision-3
JSON structural validation against the original source digest. Neither is evidence
that every modeled success/failure path ran.

The controlled source is analyzed and reviewed, not installed as the executing
CLI. The unchanged CodeBoarding exporter generates all documents. No runtime test
of the changed failure message is claimed.

Engineering results and limits: [M4 acceptance](../../../docs/design/architecture-model-m4-results.md).
