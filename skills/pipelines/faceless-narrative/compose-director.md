# Faceless Narrative Compose Director

First read `skills/core/consumer-preproduction.md`. All outputs declared by the
stage manifest are required, including the shared consumer and proof contracts.

Read `edit_decisions.render_runtime` and route composition accordingly. Never
silently change `render_runtime`. If Remotion or HyperFrames becomes unavailable,
surface the blocker and append an approved `render_runtime_selection` revision
before using another runtime.

HyperFrames is preferred for bespoke product-like kinetic design; Remotion is
preferred for structured reusable motion and responsive variants. FFmpeg alone is
acceptable only for footage-led edits whose approved promise does not require
designed motion.

Render the hero profile, then run ffprobe and full decode checks. Review factual
alignment, visual relevance, pacing, caption safety, narration intelligibility,
music ducking, aspect ratio, and final CTA. Write `render_report` and
`final_review`; a playable file is necessary but not sufficient.
