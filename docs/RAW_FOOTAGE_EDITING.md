# Native Raw-Footage Editing

OpenMontage can turn existing takes plus local timing data into a reviewed MP4
without a hosted editing or transcription provider.

```text
local video + local SRT/word JSON
  -> fingerprint source, inventory audio tracks, reject silence, cache PCM audio
  -> source_transcript.json
  -> takes_packed.md
  -> human/agent-reviewed edit_decisions.json
  -> per-cut FFmpeg render and concat
  -> final subtitle pass
  -> two-pass loudness normalization
  -> cut_qa_report.json + timeline PNGs
```

The six discoverable tools are `raw_footage_ingest`, `raw_transcript`,
`raw_footage_grade`, `raw_edit_render`, `timeline_view`, and
`cut_boundary_qa`. Original recordings remain unchanged, and output is
normalized to H.264/AAC/yuv420p with MP4 faststart.

Start with the consumer entry point:

```bash
codexvideo create --media /path/to/source.mp4 --type clip --language en
```

This runs `raw_footage_ingest`, writes a strong source fingerprint, samples the
source for review, inventories every audio track, selects a non-silent track,
and caches only the selected WAV. Pass `--audio-track N` when the automatic
choice is not the intended speaker. Add `--transcript /path/to/source.srt` to
import approved local timing; no transcription provider or local ASR model is
started automatically. Re-running unchanged inputs hits the content-addressed
cache.

After transcript and cut approval, export `editable_timeline`, render with
`raw_edit_render`, and call `cut_boundary_qa` with `strict=true` and attempts
1 through 3. Each attempt keeps its own report and review images; `revise` and
`fail` remain blocking results. Unless `fps` is explicitly set,
`raw_edit_render` preserves the first source's exact average frame rate and
applies display-matrix rotation when probing dimensions. Subtitle rendering
preflights FFmpeg's libass filter before the expensive render begins.

The implementation includes adapted algorithms from the MIT-licensed
`browser-use/video-use` commit `9575612f`, wrapped in OpenMontage-native tool
contracts. It does not install or invoke that package or its hosted API
dependencies. See `tools/editing/raw_footage/NOTICE.md` and the preserved
third-party license.
