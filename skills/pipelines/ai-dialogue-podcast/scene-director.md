# AI Dialogue Podcast Scene Director

Convert `dialogue_script` and `cast_bible` into the canonical `scene_plan`.

Map every turn to one of: two-shot, active-speaker close-up, listener reaction,
evidence insert, or B-roll. Prefer active-speaker close-ups for precise lip sync.
Use listener reactions only when the source clip contains no conflicting mouth
movement. Reserve expensive two-person generations for the opening, transitions,
important shared reactions, and landing.

For every scene specify duration, speaker, eyeline, lens/framing, studio state,
wardrobe, lighting, emotion, caption-safe area, and continuity reference. Evidence
inserts must remain on screen long enough to read and may not imply facts the
research does not support.

