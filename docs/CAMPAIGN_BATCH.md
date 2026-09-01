# Modular Campaign Batch

`campaign_batch` turns approved hook, body, and CTA modules into a resumable
set of platform deliverables. It is deliberately mechanical: the agent still
owns research, scripts, visual direction, experiment design, approvals, and
winner selection.

## Build graph

```text
approved campaign_plan
  -> validate module roles and experiment deltas
  -> materialize explicit or full-factorial variants
  -> create variant x profile jobs
  -> select source or approved profile-specific reflow render
  -> trim and normalize each module
  -> offset and merge module subtitles
  -> concatenate + subtitle + audio + encode in one FFmpeg pass
  -> ffprobe + full decode + faststart + checksum QA
  -> atomic batch_run update
  -> batch-report.json
```

## Campaign plan

The canonical input is `artifacts/campaign_plan.json`. Every module has one
role (`hook`, `body`, or `cta`), a default video source, optional
profile-specific sources, an optional trim window, and optional SRT captions.

Each explicit variant selects exactly one module per role. When
`control_variant_id` and `max_changed_dimensions` are set, planning fails if a
variant changes too many dimensions from the control.

`full_factorial` mode is available for deliberate exhaustive production. Leave
`variants` empty in that mode; planning generates the Cartesian product.

## Aspect profiles

Profiles define resolution, frame rate, codec settings, subtitle style, and a
fit strategy:

- `reflow`: requires a profile-specific source for every selected module. Use
  for motion graphics, product UI, and typography-led work.
- `contain`: preserves the whole frame and pads the remainder. Use for approved
  delivery fallbacks and source footage that must not be cropped.
- `cover`: fills the frame and center-crops overflow. Use only when the safe
  crop is known.

The batch executor does not pretend that an FFmpeg crop is responsive design.
HyperFrames or Remotion must produce the ratio-specific module before planning
a `reflow` profile.

## Subtitle truth

Module captions are relative to the module by default. Set
`captions_timebase="source"` when the module trims a longer source and the SRT
uses source time. Planning keeps captions attached to the module; assembly
trims and offsets cues into the final variant timeline.

For generated narration, prefer known TTS/script timings. Use Whisper for
recorded speech and final audio comparison.

## Operations

```python
from tools.editing.campaign_batch import CampaignBatch

tool = CampaignBatch()
planned = tool.execute({
    "operation": "plan",
    "campaign_path": "projects/demo/campaign.json",
})
rendered = tool.execute({
    "operation": "run",
    "run_path": planned.data["run_path"],
})
resumed = tool.execute({
    "operation": "resume",
    "run_path": planned.data["run_path"],
})
```

`resume` verifies the stored output checksum before treating a QA-passed job as
cached. Changed campaign inputs require a new `plan` operation. Atomic JSON
writes keep the last valid job state available after interruption.

## Completion contract

A campaign is complete only when:

1. Every requested variant/profile job is `qa_passed`.
2. Resolution, H.264 video, AAC audio, yuv420p, duration, full decode, and MP4
   faststart checks pass.
3. A second unchanged `resume` renders zero jobs.
4. Ratio-specific visual review confirms no text, product UI, subtitle, or CTA
   clipping.
5. `reports/batch-report.json` names every output and any explicit failure.
