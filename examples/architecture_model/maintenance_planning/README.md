# Cross-root maintenance acceptance

M6-B adds read-only `maintenance-plan` and `maintenance-plan-check`, using
`cross-root-maintenance-plan-v2`. Valid v1 artifacts are retained for audit and
check as stale; regenerate before choosing actions. See the
[design and protocol](../../../docs/design/architecture-model-m6-b.md) and
[Agent continuation workflow](../../../skills/codeboarding-modeling/references/maintenance-plan.md).

Run the public synthetic project with an existing, explicit Native tool config:

```text
uv run python -m examples.architecture_model.maintenance_planning.demo --output temp/my-maintenance-demo --tools ABSOLUTE_TOOLS_JSON
```

The destination must be new. It creates a tiny TypeScript repository, exports real
file-inventory and Native TypeScript facts, edits one file and explicitly refreshes
only Native through existing preview/token/revision checks. The resulting plan
reports a saved version mismatch and an independently outdated inventory root.
Generation/checking asserts unchanged model bytes and saves a self-contained
handoff for an external Agent. No tools are installed and no provider is invoked.
The helper's `plan` command pages the saved artifact without printing all files.

The automated suite covers scenarios A–F in
`tests/architecture_model/test_maintenance_plan.py`, alongside the existing M1–M6
maintenance, history, contracts, native-export, cache/path and topic regressions.
Fixtures that fabricate static catalogs are explicitly synthetic; the demo and
native-enabled tests perform actual exports. An independent Agent B, given only
the Skill and handoff locators, performs scenario G in a fresh conversation.

`validation-summary.json` and compressed logs record actual gates and known baseline
failures. `agent-continuation.json` contains the sanitized independent-session
result. `real-acceptance-summary.json` contains counts and integrity assertions
from the private original model and revision 38 isolation; private source names,
models, manifests, source digests and detailed hash inventories stay private.

Ready permits the named read-only action with satisfied hard prerequisites. Completed item
counts refer to recorded maintenance actions only. Pending historical reviews,
semantic scope differences and unexecuted runtime checks remain distinct.

The [P2 dependency correction](p2/README.md) records the reviewed-head red output,
the v2 per-item states, dependency invariants, current-preview response input and
new validation. Earlier summaries/logs in this directory describe the original
reviewed head and remain historical evidence.
