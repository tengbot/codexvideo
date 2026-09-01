# Content Format Contract

This contract turns a researched topic into a repeatable editorial format. The
format is not the topic and it is not a one-off visual treatment.

## Shared upstream contract

Every run must preserve this order:

`consumer need -> evidence -> hook candidates -> approved argument -> format script -> timed scene plan -> assets -> edit -> compose`

- Research the human need before writing hooks.
- Keep claims traceable to `research_brief.sources` or visible first-party evidence.
- Produce at least three hooks and score truth, retention, and relevance.
- Do not select footage by mood alone. Every chosen asset must answer a written
  `visual_intent` and beat reference in `visual_match`.
- Keep provider, creator, source URL, license, and local path in the asset record.
- Generated audio timing is subtitle truth. Recorded speech uses aligned
  transcription.

## Faceless narrative contract

- A narrator carries the story; no presenter is required.
- Use a hook, conflict, development, reveal, and landing.
- Change visual information every 1.5-4 seconds unless a deliberate hold is
  recorded.
- Mix source evidence, relevant B-roll, generated shots, and motion graphics.
- A screenshot is evidence, not a complete visual strategy.

## AI dialogue podcast contract

- Two hosts have durable, different roles in `cast_bible`.
- Host A normally represents the viewer: curious, skeptical, concise.
- Host B normally explains, demonstrates, or reframes without sounding like an
  advertisement.
- `dialogue_script` is written as turns with intent, emotion, timing, and shot.
- Build audio first, then generate avatar shots to the measured turn durations.
- Use separate speaker close-ups for precise dialogue control. Reserve expensive
  two-person generations for opening, reaction, transition, and landing shots.
- Keep the studio, wardrobe, eyeline, lens, lighting, and voice rules stable
  across all generated shots.

## Quality gates

Reject or revise when any of these are true:

- The hook promises more than the evidence supports.
- A line exists only to advertise the source product.
- Three consecutive scenes repeat the same composition.
- A stock clip is only atmospheric and does not express the spoken beat.
- A dialogue turn sounds like a paragraph read aloud rather than conversation.
- Lip sync, speaker identity, eyeline, or studio continuity visibly changes.
- Captions cover a face or important evidence.

