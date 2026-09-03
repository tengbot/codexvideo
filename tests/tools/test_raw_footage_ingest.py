from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.editing.raw_footage.ingest import RawFootageIngest
from tools.tool_registry import ToolRegistry


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


def test_source_ingest_contract_is_discoverable():
    assert "source_ingest_manifest" in ARTIFACT_NAMES
    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("raw_footage_ingest")
    assert tool is not None
    assert tool.capability == "source_ingest"


def test_source_ingest_rejects_manifest_outside_project(tmp_path: Path):
    source = tmp_path / "source.wav"
    source.write_bytes(b"not reached")
    result = RawFootageIngest().execute(
        {
            "input_path": str(source),
            "project_dir": str(tmp_path / "project"),
            "output_path": str(tmp_path / "outside.json"),
        }
    )
    assert result.success is False
    assert "inside project_dir" in (result.error or "")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_ingest_selects_non_silent_track_imports_transcript_and_resumes(tmp_path: Path):
    source = tmp_path / "recording.mp4"
    _make_two_track_video(source)
    subtitles = tmp_path / "recording.srt"
    subtitles.write_text(
        "1\n00:00:00,050 --> 00:00:00,700\nA useful source sentence.\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    inputs = {
        "input_path": str(source),
        "project_dir": str(project),
        "audio_track": "auto",
        "transcript_path": str(subtitles),
        "language": "en",
    }

    first = RawFootageIngest().execute(inputs)
    assert first.success, first.error
    manifest = first.data["manifest"]
    validate_artifact("source_ingest_manifest", manifest)
    assert manifest["cache"]["status"] == "miss"
    assert manifest["audio"]["track_count"] == 2
    assert manifest["audio"]["selected_track"] == 1
    assert manifest["audio"]["selection_policy"] == "loudest_non_silent"
    assert manifest["audio"]["tracks"][0]["status"] == "silent"
    assert manifest["audio"]["tracks"][1]["status"] == "usable"
    assert Path(manifest["audio"]["selected_path"]).is_file()
    assert manifest["transcript"]["status"] == "imported"
    assert Path(manifest["transcript"]["packed_path"]).is_file()
    assert len(manifest["source"]["sha256"]) == 64

    transcript = json.loads(
        Path(manifest["transcript"]["artifact_path"]).read_text(encoding="utf-8")
    )
    assert transcript["metadata"]["source_sha256"] == manifest["source"]["sha256"]

    second = RawFootageIngest().execute(inputs)
    assert second.success, second.error
    assert second.data["manifest"]["cache"]["status"] == "hit"
    assert second.data["manifest"]["audio"]["selected_path"] == manifest["audio"]["selected_path"]
