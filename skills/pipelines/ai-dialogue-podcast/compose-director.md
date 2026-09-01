# AI Dialogue Podcast Compose Director

Route using `edit_decisions.render_runtime`; never silently replace the approved
`render_runtime`. If Remotion or HyperFrames is unavailable, surface a blocker and
append an approved `render_runtime_selection` revision before changing runtime.

Remotion is usually strongest for repeatable speaker layouts, responsive captions,
and multi-profile timelines. HyperFrames is useful when the studio package and
evidence graphics require bespoke HTML/GSAP motion. The runtime composes the
conversation; it does not repair failed avatar identity or lip sync.

Render, then run ffprobe and full decode checks. Review each turn for lip timing,
speaker identity, voice identity, eyeline, studio/wardrobe continuity, reaction
truth, caption placement, evidence accuracy, audio balance, and conversational
pacing. Write `render_report` and `final_review`; reject a technically playable
video when the people look or sound inconsistent.

