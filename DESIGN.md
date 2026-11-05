---
name: CodeBoarding architecture explorer
description: A source-backed reading workbench for shared architecture and modeled flows.
colors:
  ink: "#213646"
  muted: "#506676"
  paper: "#f3f6f8"
  line: "#cbd6dd"
  accent: "#005e69"
  active: "#d5f0ec"
  warning: "#7f440a"
  white: "#ffffff"
typography:
  headline:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "27px"
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
  subheading:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
  body:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  label:
    fontFamily: "Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
  code:
    fontFamily: "Consolas, monospace"
    fontSize: "12px"
    lineHeight: 1.6
rounded:
  control: "5px"
  diagram: "8px"
  badge: "3px"
spacing:
  tight: "6px"
  control: "8px"
  detail: "12px"
  group: "16px"
  panel: "22px"
components:
  button:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 11px"
  button-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
  claim-badge:
    backgroundColor: "{colors.active}"
    textColor: "{colors.accent}"
    rounded: "{rounded.badge}"
    padding: "3px 6px"
  diagram-node:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.diagram}"
    padding: "12px"
    width: "190px"
---

# Design System: CodeBoarding architecture explorer

## Overview

**Creative North Star: "The Source-backed Workbench"**

This system serves dense reading and inspection. Pale work surfaces separate
architecture from white navigation and evidence panels. Familiar native controls
keep attention on component identity, explicit transitions and source provenance.

**Key Characteristics:**

- Restrained teal marks selection and the current modeled path.
- Tonal surfaces and fine rules define work areas without decorative elevation.
- Stable diagram positions preserve spatial memory through playback and folding.
- Disclosures make detailed evidence available within the same reading workspace.

## Colors

The palette pairs cool, blue-tinted neutrals with one deep teal selection accent.

### Primary

- **Deep Teal** (`accent`): selected controls, current-state outlines and focus.
- **Pale Teal** (`active`): current diagram nodes and claim-kind labels.

### Neutral

- **Blue Ink** (`ink`): primary text and diagram annotation.
- **Slate Text** (`muted`): provenance, supporting labels and qualifications.
- **Cool Paper** (`paper`): the continuous workspace ground.
- **Mist Rule** (`line`): control borders and panel divisions.
- **White Panel** (`white`): navigation, inspection and resting controls.

### Named Rules

**The State Color Rule.** Teal communicates selection or current modeled state;
it is not evidence that a business conclusion has been verified. Warning brown
identifies unavailable or mismatched evidence and review qualifications.

## Typography

Use the system UI stack for operational text and Consolas for source and serialized
metadata. Project headings are compact rather than promotional. The frontmatter
records the implemented headline, section, subheading, body, label and code roles.
SVG edge annotations use the smaller diagram-specific size (11px).

**The Evidence Type Rule.** Monospace identifies code or structured metadata;
responsibilities, explanations and actions stay in the UI face.

## Layout

Desktop uses a narrow hierarchy rail (220px), flexible diagram work area (minimum
400px) and evidence panel (310–380px). Main panels use the panel spacing token;
the outer header and toolbar align on a wider gutter (30px). Actions wrap as a
group rather than overflow.

At the medium breakpoint (1100px), the hierarchy rail narrows (190px) and the
inspector moves below the two work columns. At the mobile breakpoint (600px),
regions stack and gutters narrow (16px). The diagram remains a bounded scrolling
region, with an explicit horizontal-navigation hint and keyboard focus. Diagram
nodes keep their positions when the visible hierarchy or current step changes.

## Elevation & Depth

The system uses no shadows. Pale header/workspace surfaces, white reading panels
and one-pixel rules establish separation. The current node gains a stronger
teal outline (2px); focus uses an external teal ring (3px with 3px offset).

## Shapes

Controls and code blocks have modest control rounding. Diagram nodes and their
canvas use the larger diagram radius; compact badges use the smaller badge radius.
Borders describe actual controls, work regions or disclosures rather than
ornamental containers around every paragraph.

## Components

### Buttons and inputs

Resting buttons and selects use white surfaces, ink text, a fine rule and the
control radius. Hover tints the surface. Active step controls use teal with white
text. Disabled controls reduce opacity (0.5). Buttons, selects, inputs and
disclosure summaries expose a visible keyboard focus ring.

### Hierarchy and step navigation

Hierarchy rows indent by depth and expose native button toggles. Step entries
retain their explicit identity and a supporting explanation. Selection uses the
same active treatment as other controls; the display order is labeled separately.

### Diagram nodes

Nodes show a name, stable ID and current-state annotation. A collapsed ancestor
can identify the original step inside it. Unrelated nodes dim during focus
(opacity 0.35); their identity and surrounding architecture remain recoverable.
Only the node background transitions (180ms ease-out), disabled by reduced motion.

### Evidence disclosures and badges

Native disclosures use semibold summaries, fine bottom dividers and readable
vertical spacing. Code and JSON use a tinted preformatted surface, wrapping long
content and scrolling after their maximum height (380px). Claim badges use pale
teal with deep teal text; their words distinguish the actual claim kinds.

## Do's and Don'ts

### Do:

- **Do** preserve stable diagram positions while changing the visible depth.
- **Do** retain clear keyboard focus and scroll affordances in bounded diagrams.
- **Do** keep claim kinds, review currency and source targets explicitly labeled.
- **Do** use disclosures to reveal exact evidence without leaving the workspace.

### Don't:

- **Don't** use current-step color as a synonym for verified business correctness.
- **Don't** replace source-version qualifications with decorative success markers.
- **Don't** add shadow elevation where tonal regions already express separation.
