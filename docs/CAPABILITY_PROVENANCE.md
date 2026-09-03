# Capability Provenance

This ledger separates source present in the repository from capabilities that
are active in a production pipeline. It also prevents research inspiration from
being misrepresented as copied or executed code.

Status checked: 2026-09-02.

| Upstream | License | Integration | Tracked implementation | Active product-promo stage |
| --- | --- | --- | --- | --- |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) at `00371a361f8242ee5d35db19a7530fb9fbcacc0e` | Apache-2.0 | Complete vendored mirror with 155 recipe cards, 212 styles, and 212 previews; independently wired resolver | `.agents/skills/video-shotcraft/`, `tools/creative/shotcraft_catalog.py`, `schemas/artifacts/shot_language_plan.schema.json` | `shotcraft_plan` |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) at `d7d4a13a26e7c435ea8a234f1a2d996e9a1c3719` | MIT | Independent contract adaptation; no runtime dependency | `schemas/artifacts/production_preset.schema.json`, `skills/pipelines/product-promo-factory/production-contract-director.md` | `production_contract` |
| [OpenStory](https://github.com/openstory-so/openstory) at `02317772b8b06101a5df44ff26ac5609616383ff` | MIT | Independent contract adaptation; no runtime dependency or provider requirement | `schemas/artifacts/visual_continuity_bible.schema.json`, `skills/pipelines/product-promo-factory/continuity-director.md` | `continuity_design` |
| [video-use](https://github.com/browser-use/video-use) at `9575612f066aa517354790a645fd90f9f95a743b` | MIT | Native raw-footage adaptation; no package, hosted runtime, or transcription-provider dependency | `tools/editing/raw_footage/`, `tools/audio/audio_mixer.py`, `schemas/artifacts/source_ingest_manifest.schema.json`, `schemas/artifacts/source_transcript.schema.json`, `schemas/artifacts/editable_timeline.schema.json`, `schemas/artifacts/cut_qa_report.schema.json` | Supplied-media branches across clip, talking-head, podcast, screen-demo, faceless, dialogue, and avatar pipelines |
| [DBSkill](https://github.com/dontbesilent2025/dbskill) at `0876f0432eed4435d34e3ab5a796f5d57ced1cdd` | CC BY-NC 4.0 | Research only. No DBSkill source or skill content is copied into CodexVideo. | Original CodexVideo contracts: `audience_job`, `hook_candidates`, and `script_qa_report` | `audience_job`, `hook_lab`, `script_quality` |

## What Each Integration Contributes

### video-shotcraft

- Resolves scene intent to an existing recipe, exact style, demo source, and preview.
- Forces portrait-native camera planning, explicit SFX cues, and acceptance frames.
- Does not write claims, perform consumer research, or replace first-party proof.

### MoneyPrinterTurbo

- Materializes approved choices into a reusable production preset.
- Sets controlled variant axes, content-addressed caching, retry ceilings, and
  failed-or-stale-only resume behavior.
- Reuses CodexVideo's existing `campaign_plan`, `batch_run`, clip cache, FFmpeg,
  captions, and export tools instead of importing another application shell.

### OpenStory

- Locks product identity, palette, typography, lighting, camera, and motion across scenes.
- Carries an explicit visual state from each scene to the next.
- Hashes upstream artifacts and declares downstream invalidation so changed
  evidence cannot leave stale scenes or renders marked current.

### video-use

- Packs word-timed takes into a compact editorial view and keeps one timing
  truth through EDL, subtitles, and final output.
- Renders each cut independently with short audio fades, overlay PTS alignment,
  subtitles last, bounded grading, HDR-to-SDR conversion, and two-pass loudness.
- Produces filmstrip, waveform, transcript, silence, and every-boundary QA views.
- Preserves source frame rate by default, honors display rotation, and rejects a
  selected silent audio track before transcription work begins.
- Adds one-command source ingest with strong fingerprints, multi-track
  inventory, selected-audio caching, local transcript import, and resumable
  manifests. Subtitle support is preflighted before rendering, and strict QA
  retains up to three attempt reports instead of overwriting evidence.
- Uses OpenMontage checkpoints, schemas, provider selection, and laptop-safe
  thread limits instead of importing video-use's application shell or Scribe
  dependency.

### DBSkill Boundary

DBSkill is not installed globally and is not a CodexVideo dependency. Its
non-commercial license is incompatible with copying the package into a planned
commercial SaaS product. CodexVideo therefore keeps only independently authored,
general-purpose consumer-job, hook, and script-quality contracts.

## Proof In A Local Run

Project workspaces are intentionally ignored by Git. A current VibeAha planning
run writes the following local artifacts under
`projects/vibeaha-pain-first-promo/artifacts/`:

- `production_preset.json`: batch, cache, retry, output, and approval contract.
- `visual_continuity_bible.json`: cross-scene identity and dependency locks.
- `shot_language_plan.json`: six traceable Shotcraft recipes for the 18-second cut.

These artifacts can be present and still be marked `planned_not_rendered` or
`pending`. That is deliberate: a file proves planning, while a decoded render and
QA report prove execution.
