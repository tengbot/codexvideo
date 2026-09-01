# Native Raw-Footage Editing

OpenMontage can turn existing takes plus local timing data into a reviewed MP4
without a hosted editing or transcription provider.

```text
local video + local SRT/word JSON
  -> source_transcript.json
  -> takes_packed.md
  -> human/agent-reviewed edit_decisions.json
  -> per-cut FFmpeg render and concat
  -> final subtitle pass
  -> two-pass loudness normalization
  -> cut_qa_report.json + timeline PNGs
```

The five discoverable tools are `raw_transcript`, `raw_footage_grade`,
`raw_edit_render`, `timeline_view`, and `cut_boundary_qa`. Source paths are constrained by
`allowed_roots`, original recordings remain unchanged, and output is normalized
to H.264/AAC/yuv420p with MP4 faststart.

The implementation includes adapted algorithms from the MIT-licensed
`browser-use/video-use` commit `92c2b34e`, wrapped in OpenMontage-native tool
contracts. It does not install or invoke that package or its hosted API
dependencies. See `tools/editing/raw_footage/NOTICE.md` and the preserved
third-party license.
