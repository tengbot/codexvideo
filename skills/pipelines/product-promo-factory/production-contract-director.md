# Production Contract Director

Materialize the approved proposal into a `production_preset` before any paid or
compute-heavy work starts. Copy the approved renderer family, runtime,
composition mode, output profiles, voice choice, and cost ceilings exactly. A
pending proposal produces a pending preset with null runtime choices; it never
silently selects a renderer or provider.

Define the batch axes explicitly and allow no more than two changed dimensions
per experiment by default. Use content-addressed caching, preserve source media,
and rerun only failed or stale stages. Each stage policy must state its retry
limit and cost ceiling so a resume operation cannot repeat successful paid work.

This contract independently adapts the resumable task, reusable settings,
material reuse, and batch-production ideas associated with MoneyPrinterTurbo.
Do not import its application shell or create a runtime dependency on that
project. Record the audited upstream commit and MIT license in the artifact.
