# M5 implementation plan and protocol

Baseline: fork main `4f73e07c46b21a1fc96426b4be9bf9ff96e8a7dd`.

1. Exercise native project discovery and LSP extraction for Rust, TypeScript,
   mixed roots, Java and Vue. Record actual graphs and tool failures.
2. Add a provider-free multi-adapter worker, preserving the legacy Python path.
   Normalize native graph endpoints by file before merging projects; reject
   ambiguous native identities, missing tools/files and unhealthy extraction.
3. Extend Facts with a strict v2 root identity and per-file language/project
   membership. Preserve v1 serialization, IDs and historical references exactly.
   Keep the model envelope v1 with optional additive fields; unknown fields fail.
4. Extend Relation with a typed interface contract and Scenario with relation
   references. Reuse existing claims, impact calculation and review histories.
5. Scope comparisons by snapshot root; track latest targets independently. Add
   explicit root mappings to the existing hash-checked read-only source viewer.
6. Author one continuous Tauri-style model from real exported facts, demonstrate
   independent CLI/Agent continuation and one-sided maintenance. Exercise Java/Vue
   without claiming unavailable SFC symbols or inferred runtime execution.
7. Run regression, real exports, Node playback, format/type and browser checks;
   document actual limits, then commit/push and open a fork-main Draft PR.

## Compatibility

No in-place migration rewrites old catalogs. Facts v1 serialization excludes all
new source-identity fields, even when nested in a newer model. Empty new optional
model/relation/scenario fields also remain omitted, preserving existing content
fingerprints and embedded historical examples. Schema validation still rejects
unknown versions/fields. All writes use the existing locked candidate validation
and atomic replacement. Schema/read/export have no write migration side effects.

Legacy root `""` and explicit root IDs are separate identities. Adoption of explicit
roots is an Agent-authored rebind with append-only history; maintenance never infers
that a legacy root is a new named root merely from equal paths or bytes.

## Facts v2

`project_id` identifies the system boundary; `source_root_id` identifies the source
repository/root. Each immutable snapshot records an independent manifest/digest,
Git context, `file_languages`, `file_projects` (root-relative native workspace),
source locations, exact file-keyed call endpoints and extraction limitations.
Snapshot IDs include root identity. Symbols retain `path|native_name` catalog keys;
their full identity is snapshot/root + language/project + catalog key. A per-project
native run precedes normalization so native name-only merging cannot join separate
Java projects. Native duplicate qualified names inside a project fail explicitly
under the worker's strict identity mode rather than guessing a target.

The supported-file inventory is strict and independently checked against extracted
project membership. Vue is admitted as explicit FILE evidence only. Unknown suffixes
are outside scope. Empty non-Python graphs fail; Python keeps its AST callable
census and valid constants-only behavior. LSP error responses and native ERRORs
fail publication. Native discovery exclusions currently fail if they omit supported
files in this root: choose a narrower root or align ignore rules, never infer deletion.
Native parse/LSP semantic completeness beyond Python remains bounded and recorded.

## Contracts and maintenance

Relation ID is the durable contract ID; no second contract object graph exists.
Typed metadata retains both component-owned evidence sides, matching evidence,
mechanism/operation, rationale, status and uncertainty. `evidenced` means an
explicit authored static match, never that a runtime request executed. Candidate,
missing and ambiguous states require uncertainty. Claim validation is structural;
the Agent still owns semantic judgement. Scenario relation IDs enable impact even
when a step does not repeat every registration binding.

Refresh compares bindings only within the target root. Independent target IDs live
in `maintenance_targets`; the older scalar remains for legacy consumers. Existing
file-granular comparisons, review coverage fingerprints, rebind history, revision
conflicts and atomic writes remain shared. Contract review status is derived from
pending maintenance, independent of the saved authored static status.

One HTML includes all roots and facts. Source maps are execution inputs only;
lookup uses the evidence snapshot's root, path confinement and whole-file hash.
Current files never impersonate unavailable historical bodies. Missing maps do not
fall back to another named root. Existing transition/playback semantics are reused.

Actual probe counts, commands and gate outcomes are in [the results](architecture-model-m5-results.md).
