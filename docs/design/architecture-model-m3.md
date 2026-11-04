# M3: persistent architecture explorer

PR #3 was merged at d4ace08b, including reviewed 713cca1f. M3 branches from that
main on `codex/m3-interactive-browser` and targets `main`; no stacked dependency
remains. P3 is a separate first commit. Existing M1/M2 contracts remain in force.

## Stories and implementation

| Story | Entry and result |
|---|---|
| H5 | Project boundary, expandable parent_id tree, shared SVG graph, component/relation inspector, binding locations |
| H6 | Select scenario, explicit-transition player, current step projects into collapsed ancestors; expand restores the original step/component |
| H7 | A/B share component IDs; focus dims unrelated objects; uncheck restores context; each business retains its browsing position |
| H8 | Inspector separates claim.kind, explanation, assumptions, issues, opinions and planned/executed verifications; expandable versioned code evidence |
| H9 | Separate current coverage, current pending and all pending history; each observation names its target and actual confirmation coverage |
| A5 | Existing CLI updates the original model; export-html freezes and exports its next revision |
| A6 | External Agent records session feedback as ordinary opinions/patches and exports again; browser remains read only |

## Direction contract

THESIS: A source-backed reading workbench centered on stable shared objects.
OWN-WORLD: Daytime desktop reading; pale blue work surface, white inspection
panels, deep blue text, restrained teal for selected business state. System UI
type serves dense operations; monospace is reserved for code and metadata.
STORY: Choose a business, follow explicit transitions, inspect its component and
source evidence, understand exactly what still needs review.
FIRST VIEWPORT: Project/revision at top, playback toolbar below, narrow hierarchy
at left, spatially stable graph at center and evidence inspector at right.
FORM: Code-led Operate/Read workbench, seed: none (unavailable); routine design
choices delegated by the user. Mobile stacks the same functional regions.
FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Frozen projection and read-only boundary

`projection(Model)` deep-validates the complete model and calls maintenance.query
on that same frozen instance. Export never combines reads from different store
revisions. Scoped read envelopes (`complete:false`) are not a supported input.
The CLI reads once via ModelStore.read. Model ID, revision, export UTC time,
source snapshots/versions, latest target and selected business/step are available
through the page and metadata inspector. Derived maintenance contexts appear in
the projection without saving them to disk.

Python exports one HTML with local embedded CSS, JS, JSON and optional snippets.
No LLM/provider, telemetry, source analysis or network request runs at export or
view time. The output must be a new file. A flushed temporary file is published
with a non-overwriting hard link; unsupported filesystems fail explicitly. A
failure cannot replace the model, an earlier export or a concurrent writer's
artifact. Browser state stays in memory; reloading resets it. There is no model
write route, browser fetch or condition evaluation.

## Hierarchy and aggregation

Stable preorder layout uses model component order and parent depth; playing,
focusing or collapsing never randomizes positions. Descendants hidden by a
collapsed parent project to the outermost visible ancestor. Active nodes say
that the original current step occurs inside them. Steps and components retain
original IDs. Projected edges retain relation IDs, original component endpoints,
step IDs and transition indices. Rendering groups coincident visible endpoints,
lists underlying references in SVG titles and preserves individual relationships
and choices below the graph. These groups never become domain facts.

Focus dims objects outside the selected business without removing context.
Expanded IDs and each scenario's player position survive switching and focusing.
The browser does not assume logical components match filesystem directories;
evidence explicitly names repository paths and symbols.

## Playback semantics

Start at entry_step_id. `order` controls only the list. Forward choices come only
from transitions whose source is the actual current step. Several outgoing
transitions require user selection; labels show kind, target and condition.
Automatic playback follows a sole non-loop edge, stopping at branches, declared
loops, repeated nodes (including cycles mislabeled next), or absent edges.
Single forward is an explicit user action and may enter a loop. Back pops the
actual browsing history including its incoming transition. Reset returns to entry.
Clicking a listed step explicitly starts a new browsing path and clears back
history, with a message. Clicking components/relations only changes inspection.

Return is an ordinary explicitly modeled edge, not an inferred stack pop. Loop
edges require a choice on every visit; pause stays usable, and available exit
edges are shown beside loop choices. No terminal schema exists: missing edges
are labeled as modeled endpoints or unexplained gaps, never silently filled.
Animations highlight business paths and never claim runtime execution. Actual
verification scope stays in separate planned/executed records.

## Evidence, review scope and security

Component, relation, business and step inspection exposes definitions, claim kind,
assumptions, issues, bindings, opinions and exact verification records. Source
root is optional and explicit. Resolved paths must stay within it; traversal and
escaping symlinks are refused before opening. Only exact whole-file SHA-256 matches
can supply an embedded UTF-8 line range. Missing files, hash mismatch, unsupported
encoding, invalid line range and files above 2 MB withhold bodies while preserving
location/version. Current workspace contents never stand in for old evidence.
Binding history metadata remains visible. Revisions and object fingerprints are
not old explanation bodies; no historical text is reconstructed.

current_coverage_ids means current explanation definitions for each known source
comparison, even when its target is old. current_pending_ids is the unresolved
current subset; pending_ids also retains unresolved historical definitions/targets.
Each observation independently labels current/history, pending/reviewed and
latest/older source target. Resolution author, reason, timestamp, source version,
object_ids and object_versions remain visible. Neither an opinion, an Agent
confirmation nor an executed check changes claim.kind or proves other conclusions.

All untrusted model/code data enters DOM via textContent. JSON escapes `<` before
embedding, blocking script closure. No model-provided URL becomes a live link,
HTML fragment or code. CSP disallows external scripts, connections, base URLs
and form submission. Inline scripts/styles are the trusted shipped runtime.

## P3 compatibility repair

Ordinary patched_model derives current-revision observations before applying and
validating operations, mirroring the read view. Their IDs also join the reserved
ID set. revision_candidate still derives post-edit coverage and validates the
entire result; locks, expected_revision and atomic model replacement stay intact.
Explicit resolve keeps its supplied maintained observations. Old observations,
resolutions and immutable facts are untouched. Regression uses independent read /
maintenance, ordinary apply and read processes, stale-revision and invalid-reference
failures with byte checks.

## Limits

Large graphs/history are unbenchmarked. Layout intentionally keeps empty space
where collapsed descendants were, preserving spatial positions. Labels/conditions
and details carry exact transitions; a coincident edge alone is not a trace.
Only UTF-8 snippets up to 2 MB per file are embedded. Export publication requires
hard-link support. It does not reconstruct unavailable historical bodies. There
is no full event replay, model editor, background scan or multilingual engine change.
