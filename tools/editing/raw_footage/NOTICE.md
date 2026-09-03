# Provenance

This module contains both original OpenMontage code and adapted portions of
`browser-use/video-use` (MIT License, copyright Browser Use), pinned from commit
`9575612f066aa517354790a645fd90f9f95a743b`. Adapted algorithms live in
`ported_video_use.py`, `models.py`, `render.py`, and
`../../audio/audio_mixer.py`; the full upstream license is preserved under
`THIRD_PARTY_LICENSES/video-use-MIT.txt`.

No `video-use` package, hosted service, ElevenLabs API, or Scribe API is used at
runtime. OpenMontage accepts local SRT or local word-timing JSON and performs all
editing and verification with FFmpeg, FFprobe, NumPy, Pillow, and Python.
