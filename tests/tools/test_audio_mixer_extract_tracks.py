from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.audio.audio_mixer import AudioMixer


def _make_two_track_video(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=160x90:r=24:d=0.8",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=mono:d=0.8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=0.8",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-map",
            "2:a:0",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_extract_selects_audio_track_and_rejects_silence(tmp_path: Path):
    source = tmp_path / "multi-track.mp4"
    _make_two_track_video(source)

    silent_output = tmp_path / "silent.wav"
    silent = AudioMixer().execute(
        {
            "operation": "extract",
            "input_path": str(source),
            "output_path": str(silent_output),
            "audio_track": 0,
        }
    )
    assert not silent.success
    assert "is silent" in silent.error
    assert not silent_output.exists()

    speech_output = tmp_path / "speech.wav"
    speech = AudioMixer().execute(
        {
            "operation": "extract",
            "input_path": str(source),
            "output_path": str(speech_output),
            "audio_track": 1,
        }
    )
    assert speech.success, speech.error
    assert speech.data["audio_track"] == 1
    assert speech.data["audio_track_count"] == 2
    assert speech.data["peak_dbfs"] > -60
    assert speech_output.is_file()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_extract_reports_available_track_range(tmp_path: Path):
    source = tmp_path / "multi-track.mp4"
    _make_two_track_video(source)
    result = AudioMixer().execute(
        {"operation": "extract", "input_path": str(source), "audio_track": 2}
    )
    assert not result.success
    assert "numbered 0-1" in result.error


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_extract_can_keep_intentionally_silent_track_without_nonstandard_json(tmp_path: Path):
    source = tmp_path / "multi-track.mp4"
    _make_two_track_video(source)
    output = tmp_path / "kept-silence.wav"
    result = AudioMixer().execute(
        {
            "operation": "extract",
            "input_path": str(source),
            "output_path": str(output),
            "audio_track": 0,
            "reject_silence": False,
        }
    )
    assert result.success, result.error
    assert result.data["peak_dbfs"] is None
    assert output.is_file()
