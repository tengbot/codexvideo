"""Regression cases found by the September production audit."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from codexvideo.catalog import choose_format, destination_settings
from codexvideo.project import resume_project
from tools.editing.raw_footage.ingest import RawFootageIngest
from tools.editing.raw_footage.render import RawEditRender


@pytest.mark.parametrize("destination", ["tiktok", "youtube", "x"])
@pytest.mark.parametrize("aspect,dimensions", [
    ("9:16", (1080, 1920)), ("16:9", (1920, 1080)), ("1:1", (1080, 1080)),
])
def test_aspect_override_changes_dimensions(destination, aspect, dimensions):
    settings = destination_settings(destination, aspect)
    assert (settings["width"], settings["height"]) == dimensions
    assert settings["aspect"] == aspect


@pytest.mark.parametrize("status", ["failed", "pending", "in_progress", "awaiting_human", "invalid", "stale"])
def test_resume_never_skips_an_unfinished_predecessor(monkeypatch, tmp_path, status):
    monkeypatch.setattr("codexvideo.project.load_board_state", lambda _: {
        "project_id": "fixture", "pipeline": {"pipeline_type": "faceless-narrative"},
        "stages": [{"name": "script", "status": status}, {"name": "assets", "status": "in_progress"}],
        "media": {"renders": []},
    })
    result = resume_project(tmp_path)
    assert result["next_stage"] == "script"
    assert result["stage_status"] == status
    assert result["awaiting_human"] == (status == "awaiting_human")


@pytest.mark.parametrize("prompt,expected", [
    ("做一个两个人对话的播客视频", "ai-podcast"),
    ("做一个无脸视频", "faceless"),
    ("录屏操作演示", "screen-demo"),
])
def test_chinese_format_intent_takes_precedence_over_url(prompt, expected):
    assert choose_format(requested="auto", prompt=prompt, source_url="https://example.com") == expected


@pytest.fixture
def multitrack_source(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and FFprobe required")
    source = tmp_path / "two-tracks.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=12:d=1",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000:duration=1",
        "-map", "0:v", "-map", "1:a", "-map", "2:a", "-t", "1",
        "-c:v", "libx264", "-threads", "1", "-preset", "ultrafast", "-c:a", "aac", str(source),
    ], check=True, capture_output=True)
    return source


def test_ingested_audio_selection_survives_complete_render(multitrack_source):
    source = multitrack_source
    project = source.parent
    result = RawFootageIngest().execute({"input_path": str(source), "project_dir": str(project)})
    assert result.success, result.error
    manifest = json.loads((project / "artifacts/source_ingest_manifest.json").read_text())
    assert manifest["audio"]["selected_track"] == 1
    edit_path = project / "artifacts/edit_decisions.json"
    edit_path.write_text(json.dumps({"version": "1.0", "render_runtime": "ffmpeg", "cuts": [
        {"id": "cut", "source": str(source), "in_seconds": 0, "out_seconds": 1},
    ]}))
    output = project / "renders/output.mp4"
    rendered = RawEditRender().execute({
        "edit_decisions_path": str(edit_path), "project_dir": str(project),
        "output_path": str(output), "width": 160, "height": 90, "threads": 1, "quality": "draft",
    })
    assert rendered.success, rendered.error
    measured = subprocess.run([
        "ffmpeg", "-v", "info", "-threads", "1", "-i", str(output),
        "-vn", "-af", "volumedetect", "-f", "null", "-",
    ], capture_output=True, text=True, check=True)
    peak = re.search(r"max_volume: ([-\d.]+) dB", measured.stderr)
    assert peak and float(peak.group(1)) > -50, measured.stderr


def test_multitrack_source_requires_a_selection(multitrack_source):
    source = multitrack_source
    with pytest.raises(ValueError, match="multi-track"):
        RawEditRender._source_audio_track(source, {}, source.parent)
    assert RawEditRender._source_audio_track(source, {"audio_track": 1}, source.parent) == 1
    with pytest.raises(ValueError, match="unavailable"):
        RawEditRender._source_audio_track(source, {"audio_track": 2}, source.parent)


def test_changed_source_cannot_reuse_ingest_selection(multitrack_source):
    source = multitrack_source
    result = RawFootageIngest().execute({"input_path": str(source), "project_dir": str(source.parent)})
    assert result.success, result.error
    manifest_path = source.parent / "artifacts/source_ingest_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="stale"):
        RawEditRender._source_audio_track(source, {}, source.parent)
