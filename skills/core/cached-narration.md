# Cached Local Narration

`kokoro_tts` is optional. It requires existing kokoro-onnx, ONNX Runtime,
SoundFile, model and voice files; it never installs packages or downloads models.
The default files are the HyperFrames Kokoro cache under `~/.cache/hyperframes/tts`.

Use short English phrases and an explicit voice. Synthesize a sample before
the remaining phrases. One CPU thread is enforced. Existing eSpeak data is
copied into a short-lived short path to support long checkout paths on macOS.
This is a pronunciation dictionary, not a new downloaded model.

Measured file duration is phrase timing, not forced alignment or word timing.
Use phrase captions or run an explicitly selected aligner. Never fabricate word
timestamps or claim human voice approval from a successful synthesis result.
