# Consumer Workflow

CodexVideo has two layers with a deliberately narrow boundary:

1. The consumer front door performs deterministic setup: capability discovery,
   format routing, style compatibility, project scaffolding, budget policy,
   preview policy, and resume state.
2. Codex performs the creative work by following the selected pipeline and its
   director skills. Python does not invent claims, pains, scripts, or shots.

## One Command

```bash
codexvideo create "Make an English consumer-first launch video" \
  --url https://example.com \
  --type product-promo \
  --style cinematic-saas \
  --destination tiktok
```

This creates:

```text
projects/<id>/
|-- CODEX_TASK.md
|-- project.json
|-- artifacts/
|   |-- consumer_request.json
|   |-- capability_manifest.json
|   |-- run_plan.json
|   `-- creative_qa_report.json
|-- assets/
`-- renders/
```

Open that project in Codex or tell Codex to execute `CODEX_TASK.md`. On an
interrupted run, use:

```bash
codexvideo resume projects/<id>
```

## Formats

| Consumer choice | Pipeline | Default style |
| --- | --- | --- |
| Product promotion | `product-promo-factory` | Cinematic SaaS |
| Faceless narrative | `faceless-narrative` | Faceless Documentary |
| Two-host AI podcast | `ai-dialogue-podcast` | AI Podcast Studio |
| Avatar spokesperson | `avatar-spokesperson` | UGC Direct Response |
| Product walkthrough | `screen-demo` | Clean Explainer |
| Footage repurposing | `clip-factory` | Social Editorial |

The plain-language style is a production contract. It selects an existing
playbook, preferred renderer, relevant Shotcraft categories, and rejection
rules such as `no-slideshow` or `stable-cast`. It does not silently lock the
final provider or runtime.

## Keys

Run `codexvideo doctor` before production. The local floor covers planning,
supplied-media editing, composition, captions, and QA. Generation remains
optional and provider-neutral. A provider pack describes what one account may
unlock, but the exact provider, model, voice, estimated cost, and fallback must
still be approved in the production proposal.

Secrets stay in the ignored `.env`. Capability manifests contain environment
variable names and availability only, never secret values.

## Quality Gates

Technical decode success is necessary but insufficient. Every final marketing
video must also pass `creative_qa_report`:

- pain is explicit by three seconds;
- copy is written from the consumer viewpoint;
- one claim survives the full video;
- product or evidence proof is visible;
- visual and spoken ideas match;
- pacing does not collapse into a screenshot slideshow;
- identity and style stay continuous;
- one CTA closes the video;
- the final file decodes cleanly.

Run the gate after visual inspection:

```bash
codexvideo qa projects/<id>/artifacts/creative_qa_report.json --write
```

## Extension Contract

New open-source capabilities should enter through one of four boundaries:

- a tool provider under `tools/`;
- a director or generic technology skill under `skills/` or `.agents/skills/`;
- a structured artifact schema under `schemas/artifacts/`;
- a consumer format or style mapping in `config/consumer_profiles.yaml`.

Do not copy an upstream application shell when a tool, contract, or skill is
the reusable unit. Record its license, pinned commit, integration boundary, and
active pipeline stage in `docs/CAPABILITY_PROVENANCE.md`.
