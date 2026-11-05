# M4: external Agent modeling workflow

Current follow-up: [M4 P2 results](architecture-model-m4-p2-results.md) cover bounded
complete-read context and separated target/engine execution on the same PR #5.

Start: 2026-11-05, clean `34b4e48f2388049eeaf180efcbf285029d7b384b`.
Remote PR #4 remains open at that head. Branch `codex/m4-external-agent-skill`
therefore stacks on `codex/m3-interactive-browser`; do not merge or modify #4.

The implementation plan announced before changes was:

1. Package a repository-owned modeling Skill, CLI reference and schema-compatible
   templates; explicit loading must work without global configuration.
2. Use real native facts from a declared Python subsystem to build one model,
   add HTML-export business, let a fresh-context Agent add patch-submission
   business, apply rehearsal feedback and maintain a controlled source change.
3. Check identity/history preservation and interactive delivery, run engineering
   gates, document actual limits, commit/push and open a new stacked Draft PR.

## Story mapping

| Story | Concrete delivery and check |
|---|---|
| H10 | `examples/architecture_model/codeboarding/index.html`: hierarchy, two businesses, explicit paths, evidence and rationale; local Chrome check |
| H11 | Revision 4 rehearsal opinion and in-place store/viewer explanation edits; existing scenarios and component IDs preserved |
| A7 | Explicit Skill/model locator, complete read, boundary/manifests/revision inventory; fresh Agent establishes context from those inputs |
| A8 | New scenario uses existing cli/store/validation, bindings and relations; no copied architecture |
| A9 | `fork_turns:none` Agent commits revision 3; exact task, discovery, commands and preservation assertions retained |
| A10 | Real second export, preview/refresh, three explicit rebinds and independent reviews; later explanation edit reopens content coverage while retaining old confirmations |

The Skill is instructions for an external Agent, not a new internal agent or MCP
service. Templates contain no usable placeholder evidence or fixed object IDs.
Replay mechanics consume authored JSON patches and explicit maintenance decisions;
they contain no business generator or LLM call. Production schema and CLI semantics
remain unchanged. See [actual acceptance](architecture-model-m4-results.md).
