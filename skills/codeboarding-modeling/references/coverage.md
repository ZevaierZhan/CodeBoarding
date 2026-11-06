# Independent facts roots and physical coverage

Discover roots with a complete model capture and `list --collection facts`.
Do not infer file-only scope from an empty symbols map: inspect each catalog's
`tools.maintenance_scope`, limitations and source manifest. `file-inventory-v1`
proves selected file hashes only; native protocols offer bounded static evidence.
Missing or unsupported descriptors cannot establish comparable maintenance scope.

If strict model loading rejects extensions from another engine version, use the
matching engine or request an explicit schema decision. A diagnostic projection
that omits fields is not complete-model acceptance; preserve the original model.

## Export inventory and inspect overlap

Run against the engine environment with explicit target and output paths:

```text
codeboarding-model facts export --file-inventory --repo TARGET --project-id PROJECT --source-root-id all-files --output NEW_FACTS
codeboarding-model model --file MODEL coverage-report --source-map LOCAL_MAPPING --output NEW_REPORT
```

Inventory runs without LLM, LSP, Kotlin or target dependency installation.
Publish outside TARGET. `--include` and `--exclude` repeat; the default include is
`*`. Patterns are case-sensitive fnmatch over root-relative POSIX paths (star
includes slash); excludes prune matching directories. The descriptor records
default excluded directory names, rules, streaming limits and implementation hash.
Unselected ranges remain outside scope. Export errors never become empty success.

LOCAL_MAPPING is a JSON object of stable root IDs to existing absolute local
directories; use `""` for the legacy v1 root. Partial mappings produce unknown
physical identity. Confirm each mapping's actual provenance with the user/workspace;
equal names or hashes cannot establish that independently copied repositories
share physical files. A focused source copy has its own physical identity.

Coverage chooses one snapshot per root: `--snapshot ID` or `--facts NEW_FACTS`
(repeat for different roots), otherwise its recorded maintenance target, otherwise
its only catalog. Ambiguous roots require explicit selection. `--root ID` bounds
analysis. Proposed facts are inspected without importing or refreshing them.
Stdout contains aggregate counts and the report path, not the manifest.

Query the full report without loading its file list into context:

```text
python model_context.py coverage --report NEW_REPORT --collection roots --limit 1
python model_context.py coverage --report NEW_REPORT --collection overlaps --search rules.ts --limit 5
python model_context.py coverage --report NEW_REPORT --collection files --search ROOT_ID --offset 0 --limit 10
```

The helper enforces its existing output budget. Use `next_offset` until the desired
range is inspected. Full descriptors and pending IDs remain in the saved report;
an oversized single root entry needs a local JSON field query, not a truncated read
represented as complete. Reports are temporary derived evidence, not writable models.

## Decide which root to maintain

`confirmed` physical overlap means the mapped files share local filesystem
identity at observation time. `same_version` means their saved content hashes
agree; `different_versions` means independent catalogs retain different bytes.
The live hash marks roots `needed_workspace_differs`. Matching recorded files
does not check new files or certify the whole extraction as fresh.

Inspect `latest_recorded_maintenance_target`, `extraction`, descriptor differences,
pending IDs and `affected` binding/component/scenario IDs. No report field turns
content agreement into synchronized semantic evidence or reviewed architecture.
Refresh and rebind remain root-isolated. Check each affected interpretation and
its exact target version explicitly; current pending and historical pending are
different. Empty pending does not establish that an interpretation was reviewed.

## Extractor upgrade or missing scope

Keep `indeterminate`; inspect reasons naming implementation/tools/protocol/patterns
or configuration changes. It does not prove deleted code or invalid explanation.
Retain old fingerprints, snapshots and review records exactly.

To establish a comparable baseline: export a new immutable catalog with intended
tools/rules, run maintenance-preview and maintenance-refresh for that root, read
candidate source, explicitly maintenance-rebind selected evidence, then
maintenance-resolve the exact target interpretation with confirmed/revised and
the Agent's rationale. A later export under the same descriptor can compare
against that baseline. Use revision/token checks from the existing protocol.
Re-export other roots only after evaluating their own report evidence; an updated
native root does not refresh an overlapping inventory root. Human/user clarification
is required when mapping provenance or intended extraction boundary is uncertain.
