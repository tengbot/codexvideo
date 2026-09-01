# Provenance

This module contains both original OpenMontage code and adapted portions of
`browser-use/video-use` (MIT License, copyright Browser Use), pinned from commit
`92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`. Adapted algorithms live in
`ported_video_use.py`; the full upstream license is preserved under
`THIRD_PARTY_LICENSES/video-use-MIT.txt`.

No `video-use` package, hosted service, ElevenLabs API, or Scribe API is used at
runtime. OpenMontage accepts local SRT or local word-timing JSON and performs all
editing and verification with FFmpeg, FFprobe, NumPy, Pillow, and Python.
