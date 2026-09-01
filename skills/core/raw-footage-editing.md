---
name: core/raw-footage-editing
description: Offline transcript-to-EDL rendering and cut-boundary verification for existing footage.
version: "1.0"
---

# Raw Footage Editing

Use this path when a project already has recorded or generated video takes. It
does not generate media and it does not call a hosted transcription service.

## Contracts

1. Import local SRT or local word JSON with `raw_transcript`. Preserve the
   original source file and record whether timing is exact or interpolated.
2. Review `takes_packed.md`, then author `edit_decisions.json`. Every cut needs
   a reason and must remain within the probed source duration.
3. Render with `raw_edit_render`. Restrict `allowed_roots`, use at most two
   threads on a laptop, and keep subtitles enabled only when a matching source
   transcript exists. Use `grade=auto` only after reviewing its signalstats;
   overlays must be mapped through `overlay_paths` and shifted onto the output
   timeline before subtitles.
4. Run `cut_boundary_qa`. A completed render is not accepted until full decode,
   codec compatibility, audio checks, the overview, and every boundary image
   exist in `cut_qa_report.json`.

## Editorial Rules

- Make cuts from human-reviewed source ranges, not from guessed timestamps.
- Keep one timing truth from source transcript through EDL and final subtitles.
- Render cuts independently and apply short audio fades before concatenation.
- Burn subtitles after visual edits, then normalize loudness and add faststart.
- Never modify source recordings in place.
- Treat cue-interpolated SRT timing as approximate; use local forced alignment
  when word-exact karaoke timing or very tight cuts are required.

## Runtime Boundary

This is an OpenMontage-native module with MIT-licensed algorithms adapted from
`browser-use/video-use` commit `92c2b34e`. It uses Python, NumPy, Pillow, FFmpeg, and
FFprobe locally. It does not require `video-use`, ElevenLabs, Scribe, or another
editing API.
