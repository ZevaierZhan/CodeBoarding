# Architecture model explorer

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Readers explore one accumulating architecture model. External business analysis
Agents inspect source and maintain explanations using the existing JSON CLI.

## Product Purpose

Understand shared components, explicit business flows, source evidence and the
scope of maintenance reviews without editing the model in the browser.

## Stack

Delegated by the M3 brief: Python export with native HTML, CSS, SVG and JavaScript.
The generated document works offline without a server or additional libraries.

## Capabilities and Constraints

Stable domain IDs; hierarchical components; explicit transitions; current and
historical source targets; hash-verified optional source snippets. Conditions are
descriptions. Playback is a modeled path, never a runtime trace. No internal chat
Agent, background scanner, provider initialization or browser model editing.

## Evidence on Hand

M1/M2 schemas, store and maintenance engine; real Python fixture and native
StaticAnalyzer exports under examples/architecture_model. Retry/cancel actions
in the M3 demo are labeled hypotheses because the fixture has no such caller.
