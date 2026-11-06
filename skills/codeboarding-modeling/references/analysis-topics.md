# Analysis topics (optional schema 1 capability)

Inspect the selected engine's `model schema`: Scenario must advertise
`analysis_kind` and `facet_order`, and Step must advertise `facet_checks`.
Presence of these fields declares use of this additive capability; there is no
separate extension envelope or migration. An older engine rejects them. Preserve
the existing model and request a compatible engine rather than dropping fields,
projecting a reduced model, or initializing a replacement.

- `analysis_kind`: `operation` (default when absent) or `comparison`. Operations
  have concrete triggers and explicitly justified transitions. Comparisons contain
  independent explanations and must have empty transitions; playback is disabled.
- `facet_order`: unique nonempty question labels in authored reading order.
  These labels are local keys, not component IDs or execution stages.
- `Step.facet_checks`: a string-to-string mapping from a declared label to an
  authored mechanism explanation. Each key must occur in its scenario's facet
  order. Missing entries mean unknown/unexamined, not passed or inapplicable.

Check explanations use the step's claim, assumptions/issues and evidence bindings.
They have no executed status. Save actual executed checks separately as Verification
with the existing command, result, evidence scope and provenance requirements.
An operation can answer several questions at one step; the same component may serve
many questions. Component parents do not imply check coverage.

Capture the complete model through the bounded-context workflow. Page existing
scenario IDs, then query relevant scenario/step objects and search the captured
`facet_order` and `facet_checks`; reuse their labels, steps, components and bindings.
`order` organizes reading. A comparison's required `entry_step_id` only selects
the initially inspected item, and creates no execution edge.

Updates merge object-level fields, but arrays/maps replace whole fields. When
updating `steps`, retain every continuing step and its IDs, evidence and facet maps.
When updating `facet_checks`, retain other entries. Rename a question label and all
referring keys together in one patch. Retain transitions unless intentionally
changing the modeled path. Absent fields stay absent on serialization; explicitly
saved empty fields remain explicit.

Use validate / diff / freshness check / apply with expected revision. A facet edit
changes interpretation fingerprints and can append a new maintenance review context.
Historical observations, review resolutions and Verification remain version-scoped.
Export a fresh HTML and inspect topic switching, question explanations, claim kinds,
source evidence and separate Verification records. Reading order and playback
are not observations of runtime behavior.
