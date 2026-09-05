from tools.audio.kokoro_tts import KokoroTTS


def test_missing_models_fail_without_creating_output(tmp_path):
    result = KokoroTTS().execute({"text": "Hello", "model_path": str(tmp_path / "missing.onnx"),
                                  "voices_path": str(tmp_path / "missing.bin"),
                                  "output_path": str(tmp_path / "voice.wav")})
    assert not result.success
    assert "no download" in result.error
    assert not (tmp_path / "voice.wav").exists()
