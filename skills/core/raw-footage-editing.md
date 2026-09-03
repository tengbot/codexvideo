---
name: core/raw-footage-editing
description: Offline transcript-to-EDL rendering and cut-boundary verification for existing footage.
version: "1.1"
---

# Raw Footage Editing

Use this path when a project already has recorded or generated video takes. It
does not generate media and it does not call a hosted transcription service.

## Contracts

1. Start with `raw_footage_ingest`. It writes a strong source fingerprint,
   inventories every audio stream, selects or confirms a non-silent track, and
   caches the extracted PCM audio. When several tracks contain sound, inspect
   the selected track before ASR; loudest does not prove that it contains the
   intended speaker.
2. Use the provider chosen at preflight to transcribe the cached audio. Local
   ASR is allowed but never mandatory. Do not silently switch to a hosted ASR
   provider, and do not run a local model merely because it is installed.
3. Re-run `raw_footage_ingest` with the approved local SRT or word JSON, or use
   `raw_transcript` directly. Preserve the
   original source file and record whether timing is exact or interpolated.
4. Review `takes_packed.md`, then author `edit_decisions.json`. Every cut needs
   a reason and must remain within the probed source duration.
5. Export the decisions with `editable_timeline` before composition when a
   person may adjust trims, captions, transforms, or audio. The timeline is a
   supplementary round-trip artifact; `edit_decisions.json` remains the render
   contract.
6. Render with `raw_edit_render`. Restrict `allowed_roots`, use at most two
   threads on a laptop, and keep subtitles enabled only when a matching source
   transcript exists. Use `grade=auto` only after reviewing its signalstats;
   overlays must be mapped through `overlay_paths` and shifted onto the output
   timeline before subtitles. Leave `fps` unset to preserve the first source's
   exact average frame rate; set it only when the delivery contract requires a
   different rate.
7. Run `cut_boundary_qa` with `strict=true` and `attempt=1`. A completed render
   is not accepted until full decode,
   codec compatibility, audio checks, the overview, and every boundary image
   exist in `cut_qa_report.json`.
8. When QA returns `revise`, change the EDL or render settings before trying
   again, increment `attempt`, and preserve the prior report. Stop after three
   attempts and surface the remaining issue instead of looping unchanged work.

## Editorial Rules

- Make cuts from human-reviewed source ranges, not from guessed timestamps.
- Keep one timing truth from source transcript through EDL and final subtitles.
- Render cuts independently and apply short audio fades before concatenation.
- Burn subtitles after visual edits, then normalize loudness and add faststart.
- Never modify source recordings in place.
- Reuse a cached ingest only when the source fingerprint, track policy,
  transcript fingerprint, language, and silence threshold still match.
- Do not force raw-footage rendering onto fully generated scenes. This branch
  applies only to supplied, captured, downloaded, or already generated takes.
- Treat cue-interpolated SRT timing as approximate; use local forced alignment
  when word-exact karaoke timing or very tight cuts are required.

## Runtime Boundary

This is an OpenMontage-native module with MIT-licensed algorithms adapted from
`browser-use/video-use` commit `9575612f`. It uses Python, NumPy, Pillow,
FFmpeg, and FFprobe locally. It does not require `video-use`, ElevenLabs,
Scribe, or another editing API.
