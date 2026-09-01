# AI Dialogue Podcast Asset Director

Produce `asset_manifest`, `visual_match`, and `audio_timeline`.

Generate each host's audio turn first with the locked voice and performance
direction. Concatenate a clean master dialogue track while retaining one file per
turn. Measured audio duration controls avatar shot duration and captions.

Generate active-speaker shots per turn. Reuse approved silent reaction footage
when it preserves identity and continuity. For each avatar shot record provider,
model, avatar ID, voice ID, prompt, source reference, duration, cost, and local
path. Generate two-person shots separately and reject identity drift, bad hands,
wrong eyelines, speaking-listener mouth motion, or visible studio changes.

Score evidence and B-roll candidates in `visual_match`. All paths must resolve on
disk before the asset checkpoint is approved.

