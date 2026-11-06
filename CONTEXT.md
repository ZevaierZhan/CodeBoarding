# CodeBoarding architecture interpretations

This vocabulary distinguishes authored architecture explanations from their source
evidence and from observations of executed behavior.

## Language

**Operation**: A modeled business flow with a concrete trigger, outcome and explicitly
justified execution transitions. _Avoid_: runtime trace.

**Comparison topic**: A collection of independent mechanism explanations whose
reading order asserts no execution sequence. _Avoid_: sequential workflow.

**Analysis facet**: An authored question examined across one or more explanation
items, supported by their claims and evidence. _Avoid_: mandatory execution stage.

**Facet check**: An authored answer explaining a mechanism for an analysis facet.
An absent answer is unknown. _Avoid_: executed test, passed verification.

**Verification**: A separately scoped planned check or recorded execution with
its actual inputs, source version and result. _Avoid_: interpretation approval.
