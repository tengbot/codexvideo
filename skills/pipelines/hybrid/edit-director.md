# Edit Director - Hybrid Pipeline

## When To Use

This stage creates the layered edit logic for a source-led video with support elements. The order matters: anchor cut first, support layers second.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Source/support assets and timeline intent |
| Playbook | Active style playbook | Typography and motion consistency |
| Interchange | `editable_timeline` | Portable multi-track handoff and round-trip edits |

## Process

### 1. Lock The Anchor Cut First

The viewer should understand the story before support overlays are added. If the anchor cut is weak, support layers will not save it.

### 2. Add Support In Priority Order

Typical order:

1. subtitles,
2. speaker or context labels,
3. diagrams or stat cards,
4. optional inserts,
5. CTA elements.

### 3. Protect Readability

Never stack too many support layers in one moment. If subtitles, labels, charts, and overlays collide, simplify.

### 4. Use Metadata For Layering Logic

Recommended metadata keys:

- `anchor_cut_notes`
- `layer_order`
- `overlay_windows`
- `variant_edit_rules`

### 5. Quality Gate

- the anchor cut works on its own,
- support layers clarify instead of distract,
- mobile readability survives,
- variants remain consistent.

### 6. Export The Editable Project

After `edit_decisions` validates, call `editable_timeline` with
`operation="export"` and the canonical scene plan, asset manifest, and edit
decisions paths. Store the artifact at `artifacts/editable_timeline.json` and
the portable pack under `editable/`.

If a person or agent changes timing, trims, volume, text, transforms, or
keyframes, apply those changes through the timeline command log and import the
result back into `edit_decisions` before compose. Complex HyperFrames or
Remotion scenes stay source compositions and may be represented by scene proxy
clips in the portable project.

## Common Pitfalls

- Trying to fix a weak cut with extra graphics.
- Letting support layers compete with the source.
- Building each platform variant as a separate editorial philosophy.
- Keeping manual changes outside the editable timeline command history.
