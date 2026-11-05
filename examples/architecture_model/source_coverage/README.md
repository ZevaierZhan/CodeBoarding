# Reproduce source coverage acceptance

From the repository root, use existing local native tools (TypeScript LSP and
Tokei). The script never installs target dependencies or calls a provider:

```powershell
uv run python examples/architecture_model/source_coverage/acceptance.py --tools LOCAL_TOOLS_JSON --output temp/m6-acceptance-new
uv run pytest tests/architecture_model/test_source_coverage.py -q -rs
```

Use a new output directory on each run. The committed four-file sample contains
no private project source. Native facts in the acceptance script come from actual
TypeScript analysis; synthetic native catalogs in the unit suite are explicitly
marked as fixtures. No unit fixture is presented as native execution evidence.

The script records three confirmed physical overlaps, changes only rules.ts,
refreshes only the native root and observes one saved-version disagreement. It
then explicitly re-exports/refreshes inventory and observes matching content while
reviews remain pending. Changing inventory selection rules without changing its
selected files produces `indeterminate`; explicit refresh/rebind/review establishes
a new baseline without erasing earlier observations. Full models, snapshots, CLI
reports and the source copy remain in the chosen output directory. Only the small
sanitized summary is committed here.

Coverage CLI:

```text
codeboarding-model model --file MODEL coverage-report --source-map MAPPING_JSON --output NEW_REPORT
codeboarding-model model --file MODEL coverage-report --source-map MAPPING_JSON --facts TARGET_FACTS --root ROOT_ID --output NEW_REPORT
python skills/codeboarding-modeling/scripts/model_context.py coverage --report NEW_REPORT --collection overlaps --search rules.ts --limit 5
```

Mappings are JSON objects of stable root IDs to absolute directories. Missing
mappings stay unknown. Explicit target facts never import or refresh a root.
The report file contains full detail; stdout remains a bounded aggregate summary.
See the [M6-A protocol and results](../../../docs/design/architecture-model-m6-a.md).
