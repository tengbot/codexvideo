# Compose Director

Read `edit_decisions.render_runtime` and verify that it matches the approved value
in `proposal_packet`. Route `remotion` to the Remotion composition path and
`hyperframes` to the HyperFrames path. FFmpeg is allowed only when it was explicitly
approved for a footage-led treatment. Never silently change `render_runtime`; if a
runtime is unavailable, surface the blocker and append an approved
`render_runtime_selection` revision before composing with another runtime.

Render the native target aspect ratio and verify H.264/AAC/yuv420p with faststart.
Inspect the first frame, 3-second frame, product proof, CTA, and an even timeline sample.

When `shot_language_plan` exists, implement each selected recipe from its recorded
demo source and preserve its tuned timing constraints. Check the adapted render
against the recipe's reference preview at the declared acceptance frames. Reject a
center-cropped landscape composition when the plan requires native portrait framing.

Fail the render when text overlaps platform UI, a product capture is unreadable, the
voice and visual proof drift, frames are blank or frozen, or the CTA is missing. The
final review must report content, visual, caption, audio, and technical QA separately.
