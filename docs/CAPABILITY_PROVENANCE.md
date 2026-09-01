# Capability Provenance

This ledger separates source present in the repository from capabilities that
are active in a production pipeline. It also prevents research inspiration from
being misrepresented as copied or executed code.

Status checked: 2026-09-01.

| Upstream | License | Integration | Tracked implementation | Active product-promo stage |
| --- | --- | --- | --- | --- |
| [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft) at `00371a361f8242ee5d35db19a7530fb9fbcacc0e` | Apache-2.0 | Complete vendored mirror with 155 recipe cards, 212 styles, and 212 previews; independently wired resolver | `.agents/skills/video-shotcraft/`, `tools/creative/shotcraft_catalog.py`, `schemas/artifacts/shot_language_plan.schema.json` | `shotcraft_plan` |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) at `d7d4a13a26e7c435ea8a234f1a2d996e9a1c3719` | MIT | Independent contract adaptation; no runtime dependency | `schemas/artifacts/production_preset.schema.json`, `skills/pipelines/product-promo-factory/production-contract-director.md` | `production_contract` |
| [OpenStory](https://github.com/openstory-so/openstory) at `02317772b8b06101a5df44ff26ac5609616383ff` | MIT | Independent contract adaptation; no runtime dependency or provider requirement | `schemas/artifacts/visual_continuity_bible.schema.json`, `skills/pipelines/product-promo-factory/continuity-director.md` | `continuity_design` |
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
