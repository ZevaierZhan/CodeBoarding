# M4 P2: large context and separated execution — 2026-11-05

This closes the two P2 items on the same Draft PR #5 and M4 branch. Domain model,
core CLI protocol, maintenance semantics and UI are unchanged. The original
[revision 0–13 acceptance](architecture-model-m4-results.md), its fresh Agent,
feedback and two pending maintenance contexts remain preserved.

## Base and ancestry

Fetched origin before work. PR #4 had merged normally into main at
`0897007f83ad7231f210cb593432ed953fb6a1f1`; reviewed M3 head
`34b4e48f2388049eeaf180efcbf285029d7b384b` is its ancestor. Existing M4 head was
`2e741c37e2afcc747180e151cde4f1f84b187a12`, with a clean local main checkout.
Switched to `codex/m4-external-agent-skill`, merged origin/main at `5ebb9154`, and
retargeted **the existing PR #5 to main**. No rebase or force-push was needed.
Local diff against main and GitHub's PR file list contain M4 only; there are no
architecture_model runtime/M3 asset changes in this follow-up.

## P2-1: full latest state on disk, bounded relevant context

The distributed Skill now routes complete reads through its standard-library
[mechanical helper](../../skills/codeboarding-modeling/scripts/model_context.py)
and [context protocol](../../skills/codeboarding-modeling/references/context.md):

1. Stream full CLI stdout directly into a new temporary `read.json`; require
   success, `complete:true` and matching envelope/model identity/revision.
2. Save a hash-checked ID/collection/pointer inventory and show a bounded summary.
   Model/project IDs, bindings, components, scenarios/steps, facts, maintenance,
   opinions and verifications are all retrievable.
3. Page inventory and load relevant exact objects with JSON pointers. A large
   individual object must be saved or narrowed; successful stdout is capped at
   **4096 characters**, with no output-budget override.
4. Save validate/diff responses separately, inspect changes and recheck the actual
   persistent model's identity/revision immediately before apply. Apply still
   passes the captured expected revision to reject a subsequent race.
5. On stale context/conflict, discard the stale candidate, capture fresh complete
   state and reconcile. Output failure may follow commit, so reread before retry.

Full JSON need not enter conversation. A console fragment never becomes complete
state. Scoped reads remain `complete:false` and cannot replace MODEL. Cache files
are CLI envelopes/indexes, not another writable model; helper writes never replace
MODEL or its context files. Read/index files remain outside the target and Git.
The helper has no business text, model-specific IDs, component/scenario generator
or LLM. Its `cli` command only transports explicitly supplied CLI arguments.

## P2-2: actual independent target and engine

| Role | Actual path |
|---|---|
| Engine | `F:/CodeBoarding` — prepared CodeBoarding checkout and Python environment |
| Target | `F:/CodeBoarding M4 Target` — separate sibling directory, independent order fixture source |
| Persistent model | `F:/CodeBoarding M4 Target/architecture-model.json` |
| Generated HTML | `F:/CodeBoarding M4 Target/quotation-r3.html` |
| Temporary context | `F:/CodeBoarding M4 Session Cache/fresh-agent/read-001` and `read-002` |

Engine resolution is explicit checkout, installed codeboarding-model, then the
CODEBOARDING_HOME environment variable. Invalid explicit or absent engine fails
clearly. File arguments resolve from the caller before the engine subprocess runs
in its own directory. This works with spaces in target/cache/argument paths.
Unit checks also exercise engine paths with spaces and locator priority; a real
installed-CLI test runs outside the checkout. The engine is not inferred from a
target's source or Python environment.

The target materializes only four existing independent fixture Python files;
it is **not CodeBoarding as target**. Real StaticAnalyzer/PythonAdapter/Pyright
export yields 5 symbols, 5 static call records, source digest
`52785ff2dcb7ec175bb1a5d0b952922423413ff4484d526f1558403e9f3554ca`.
Git context is empty. Source/tool descriptors and exact hashes are retained in
[initial/fresh facts](architecture-model-m4-p2-evidence/facts-fresh.json).
Static records from app.start describe registration references; actual code only
returns callable values. The fresh explanation does not invent an executed
registration-to-quotation edge.

[Preparation](../../examples/architecture_model/separated/prepare_trial.py) reads
the authored fixture JSON, exports real facts and applies explicit seed/extension
patches through the CLI. The 128 additional scenarios are **labeled synthetic
context drills repeating purchase**, not independent real business discoveries.
The resulting revision-2 persistent model is **9,650,537 bytes**, over 17 times the
original checked-in M4 model (554,108 bytes). Its complete CLI read is **9,508,194
bytes**, obviously beyond ordinary conversation output. Size was measured from the
captured file, never by emitting that JSON or increasing a tool output budget.

Reproduction and a copyable other-target invocation are in the
[separated example guide](../../examples/architecture_model/separated/README.md).
The target did not install CodeBoarding/dependencies, acquire provider keys, change
its Python environment or receive engine source. File inventories and source hashes
before/after show no `.venv`, `.env`, pyproject, environment lockfile or requirements addition.

## Independent fresh-context acceptance

Spawned one independent Agent with **fork_turns:none**, no later steering and no
parent history. Its five input categories were Skill path, TARGET_REPO, MODEL,
engine locator and quotation modeling task (plus execution/output constraints).
The exact input, actual target cwd, queries and outcomes are in the
[fresh-Agent report](architecture-model-m4-p2-evidence/fresh-agent-report.md).

The Agent captured complete revision 2 outside TARGET, queried existing purchase,
entry, pricing, bindings, relations and fact descriptors, then paged scenario IDs.
It actually hit the cap when fetching `/facts/0/tools`; the helper refused oversized
stdout. The Agent used `get --output` and local JSON inspection, without changing
the cap. Native progress logs were truncated in console, but real exported facts
were already complete on disk and parsed there; no facts were recovered from logs.

It exported fresh TARGET facts through ENGINE using existing tool paths discovered
from saved model evidence. The new catalog exactly equals the existing one, so no
duplicate fact object was created. After validate/diff and freshness check, apply
at expected revision 2 committed revision **3**. The sole new object is quotation
scenario `8e49f803-0756-4d12-bc0d-da18008a0218`, with three new step IDs.
It reuses `order-entry`, `shared-pricing`, `bind-quote`, `bind-total` and existing
`entry-pricing`. All **129 prior scenarios**, four components, five bindings,
two relations, facts and previous revision records remain exactly unchanged.

The Agent correctly describes quotation's numeric return and lack of buy's
positivity guard; no receipt/database step is invented. Three explicit steps and
two transitions summarize nested execution with assumptions and an unknown caller.
No opinion, acceptance or business-executed verification was fabricated. Exact
before/after preservation and target source equality are machine-checked.

HTML embeds the complete revision-3 model exactly and all saved source snippets
match target bytes. New browser interactions and runtime business execution were
not performed; existing M3/M4 browser evidence remains historical. The exported
HTML is actually present at TARGET; the repository retains its compressed archive.

## Regression and remaining gates

| Check | Actual outcome |
|---|---|
| Existing M1–M4 plus new helper suite | **173 passed**, 300.88s; architecture_model + helper combined coverage **96.53%** (1253/1298); unchanged 80% threshold |
| New helper cases within that suite | **10 passed**: capture/query/pagination, non-model cache, truncated/scoped rejection, stale context/conflicting apply, protected outputs, engine priority/space paths, installed CLI from non-engine cwd, malformed/failed result rejection |
| Final focused replay of helper + original M4 + separated artifact checks | **17 passed**, 61.57s; final helper coverage **92.27%**; includes **3 new** separated artifact regressions added after the 173-test collection |
| Node engine tests | **6 passed** |
| Relevant mypy | PASS for helper, preparation and both new test modules |
| Windows whole-repo mypy | Existing SIGKILL attr-defined error only; no new P2 errors |
| Black / Skill validator | PASS; enabled Black commit hook required before push |
| Whole repository requested coverage command | **2872 collected**, failures observed; bounded at 300s, process tree terminated, exit 1. No final coverage report; repository-wide 80% and full-suite success remain unconfirmed. New artifact tests were added after this collection. |
| Private integration | Not run; private CodeBoarding-tests unavailable |

Coverage files were separate for the suite and bounded full run; no old shared-data
contamination or threshold change. Full-suite failures were not all attributed and
are not called baseline-only. No fresh Linux pass or browser certification is claimed.

[Evidence directory](architecture-model-m4-p2-evidence/) includes exact fresh input,
40 bounded inventory commands, patch, fact catalogs, real model/HTML archives,
source/environment metadata and check logs. The `.archive.json.gz` files archive
the actual persistent TARGET model before/after; they are not context envelopes.
Only size/hash metadata for temporary read/index files is committed, never their
contents. This concludes M4 P2, not a new product stage.
