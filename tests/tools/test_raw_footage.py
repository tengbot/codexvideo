from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from schemas.artifacts import validate_artifact
from tools.editing.raw_footage.grade import RawFootageGrade
from tools.editing.raw_footage import models as raw_models
from tools.editing.raw_footage import render as raw_render
from tools.editing.raw_footage.models import load_transcript, parse_frame_rate, resolve_safe_path
from tools.editing.raw_footage.qa import CutBoundaryQA, TimelineView
from tools.editing.raw_footage.render import RawEditRender
from tools.editing.raw_footage.transcript import RawTranscript
from tools.tool_registry import ToolRegistry


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _make_fixture_video(path: Path, duration: float = 2.4) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=320x180:rate=30:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )


def _make_color_video(path: Path, color: str, size: str, duration: float, *, audio: bool) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={size}:r=30:d={duration}",
    ]
    if audio:
        command.extend(
            ["-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={duration}"]
        )
    command.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])
    if audio:
        command.extend(["-c:a", "aac", "-shortest"])
    command.append(str(path))
    subprocess.run(command, check=True)


def _make_fractional_fps_video(path: Path, duration: float = 0.8) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size=160x90:rate=24000/1001:duration={duration}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:sample_rate=48000:duration={duration}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )


def test_registry_discovers_native_raw_footage_tools():
    registry = ToolRegistry()
    discovered = set(registry.discover("tools"))
    assert {
        "raw_transcript",
        "raw_footage_grade",
        "raw_edit_render",
        "timeline_view",
        "cut_boundary_qa",
    } <= discovered


def test_ported_source_has_pinned_commit_and_mit_license():
    module = Path("tools/editing/raw_footage/ported_video_use.py").read_text(encoding="utf-8")
    license_text = Path(
        "tools/editing/raw_footage/THIRD_PARTY_LICENSES/video-use-MIT.txt"
    ).read_text(encoding="utf-8")
    assert "9575612f066aa517354790a645fd90f9f95a743b" in module
    assert "Copyright (c) 2026 Browser Use" in license_text


def test_probe_prefers_average_fps_and_applies_display_rotation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    source = tmp_path / "rotated.mp4"
    source.write_bytes(b"fixture")
    payload = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "30000/1001",
                "r_frame_rate": "30/1",
                "side_data_list": [{"rotation": -90}],
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "2.0", "size": "7"},
    }

    class ProbeResult:
        stdout = json.dumps(payload)

    monkeypatch.setattr(raw_models, "run_command", lambda *_args, **_kwargs: ProbeResult())
    info = raw_models.probe_media(source)

    assert info["fps_rate"] == "30000/1001"
    assert info["fps"] == pytest.approx(29.97003, rel=1e-5)
    assert (info["coded_width"], info["coded_height"]) == (1920, 1080)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["rotation"] == 270


@pytest.mark.parametrize(
    ("value", "expected"),
    [(30, "30/1"), (29.97, "2997/100"), ("30000/1001", "30000/1001")],
)
def test_parse_frame_rate_preserves_exact_rationals(value, expected):
    assert parse_frame_rate(value) == expected


@pytest.mark.parametrize("value", [0, -1, "0/0", "abc", "1/0"])
def test_parse_frame_rate_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="fps"):
        parse_frame_rate(value)


def test_subtitle_style_uses_system_fallback_unless_font_is_explicit():
    fallback = RawEditRender._subtitle_force_style({}, 1280)
    explicit = RawEditRender._subtitle_force_style({"font": "Inter"}, 1280)
    assert "FontName=" not in fallback
    assert "FontName=Inter" in explicit


def test_subtitle_preflight_explains_missing_libass(monkeypatch: pytest.MonkeyPatch):
    class FilterResult:
        returncode = 0
        stdout = " T.. scale V->V Scale the input video"
        stderr = ""

    monkeypatch.setattr(raw_render, "run_command", lambda *_args, **_kwargs: FilterResult())
    with pytest.raises(RuntimeError, match="libass subtitles filter"):
        RawEditRender._require_subtitles_filter()


def test_srt_import_is_monotonic_and_packable(tmp_path: Path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg not installed")
    source = tmp_path / "source.mp4"
    _make_fixture_video(source)
    srt = tmp_path / "source.srt"
    srt.write_text(
        "1\n00:00:00,100 --> 00:00:01,000\nHello there.\n\n"
        "2\n00:00:01,100 --> 00:00:02,200\nThis stays local.\n",
        encoding="utf-8",
    )
    output = tmp_path / "source.words.json"
    result = RawTranscript().execute(
        {
            "operation": "import_srt",
            "source_path": str(source),
            "transcript_path": str(srt),
            "output_path": str(output),
            "source_id": "fixture",
            "speaker_id": "host",
            "language": "en",
        }
    )
    assert result.success, result.error
    transcript = load_transcript(output)
    assert transcript["timing_quality"] == "cue_interpolated"
    assert [word["text"] for word in transcript["words"]] == [
        "Hello",
        "there.",
        "This",
        "stays",
        "local.",
    ]
    packed = RawTranscript().execute(
        {"operation": "pack", "transcript_paths": [str(output)], "output_path": str(tmp_path / "packed.md")}
    )
    assert packed.success, packed.error
    assert "**host**: Hello there." in Path(packed.data["packed_transcript_path"]).read_text()
    timeline = TimelineView().execute(
        {
            "video_path": str(source),
            "output_path": str(tmp_path / "timeline.png"),
            "start_seconds": 0,
            "end_seconds": 2.3,
            "samples": 4,
            "transcript_path": str(output),
        }
    )
    assert timeline.success, timeline.error
    assert timeline.data["word_labels"] == 5


def test_ported_auto_grade_returns_bounded_filter(tmp_path: Path):
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg not installed")
    source = tmp_path / "dark.mp4"
    _make_color_video(source, "0x181818", "160x90", 1.0, audio=False)
    result = RawFootageGrade().execute(
        {
            "operation": "analyze",
            "input_path": str(source),
            "mode": "auto",
            "duration_seconds": 1.0,
        }
    )
    assert result.success, result.error
    assert result.data["source_commit"].startswith("9575612f")
    assert result.data["filter"].startswith("eq=")
    assert {"y_mean", "y_std", "sat_mean"} <= result.data["stats"].keys()


def test_path_resolution_rejects_escape(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"not media")
    with pytest.raises(ValueError, match="outside allowed roots"):
        resolve_safe_path(str(outside), base=allowed, allowed_roots=[allowed])


def test_word_exact_cut_inside_word_is_rejected_when_enforced():
    transcript = {
        "timing_quality": "word_exact",
        "words": [
            {
                "id": "w1",
                "text": "inside",
                "start_seconds": 1.0,
                "end_seconds": 1.5,
                "speaker_id": "host",
                "type": "word",
            }
        ],
    }
    with pytest.raises(ValueError, match="falls inside"):
        RawEditRender._check_cut_boundaries(
            {"id": "bad-cut", "in_seconds": 1.2, "out_seconds": 1.7},
            transcript,
            enforce=True,
        )
    assert RawEditRender._quality_settings("draft") == ("ultrafast", 28)
    assert RawEditRender._quality_settings("final") == ("fast", 20)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_render_and_boundary_qa_end_to_end(tmp_path: Path):
    source = tmp_path / "source.mp4"
    _make_fixture_video(source)
    srt = tmp_path / "source.srt"
    srt.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nFirst local sentence.\n\n"
        "2\n00:00:01,000 --> 00:00:02,300\nSecond local sentence.\n",
        encoding="utf-8",
    )
    transcript_path = tmp_path / "project" / "artifacts" / "source_transcript.json"
    transcript_result = RawTranscript().execute(
        {
            "operation": "import_srt",
            "source_path": str(source),
            "transcript_path": str(srt),
            "output_path": str(transcript_path),
            "source_id": "fixture",
            "speaker_id": "host",
        }
    )
    assert transcript_result.success, transcript_result.error

    edit_path = tmp_path / "project" / "artifacts" / "edit_decisions.json"
    edit = {
        "version": "1.0",
        "cuts": [
            {"id": "cut-1", "source": str(source), "in_seconds": 0.0, "out_seconds": 0.8, "reason": "opening"},
            {"id": "cut-2", "source": str(source), "in_seconds": 1.0, "out_seconds": 2.2, "reason": "body"},
        ],
        "subtitles": {"enabled": True, "max_words_per_line": 4, "position": "bottom-center"},
        "render_runtime": "ffmpeg",
    }
    validate_artifact("edit_decisions", edit)
    _write_json(edit_path, edit)
    output = tmp_path / "project" / "renders" / "fixture.mp4"
    render = RawEditRender().execute(
        {
            "edit_decisions_path": str(edit_path),
            "output_path": str(output),
            "project_dir": str(tmp_path / "project"),
            "allowed_roots": [str(tmp_path)],
            "transcript_paths": {str(source): str(transcript_path)},
            "width": 320,
            "height": 180,
            "fps": 30,
            "threads": 1,
        }
    )
    assert render.success, render.error
    assert output.is_file() and output.stat().st_size > 10_000
    report = json.loads(Path(render.data["render_report_path"]).read_text())
    validate_artifact("render_report", report)
    assert report["outputs"][0]["codec"] == "h264"
    assert report["outputs"][0]["resolution"] == "320x180"

    qa = CutBoundaryQA().execute(
        {
            "video_path": str(output),
            "edit_decisions_path": str(edit_path),
            "project_dir": str(tmp_path / "project"),
            "master_subtitles_path": render.data["master_subtitles_path"],
            "output_transcript_path": render.data["output_transcript_path"],
        }
    )
    assert qa.success, qa.error
    qa_report = qa.data["report"]
    validate_artifact("cut_qa_report", qa_report)
    assert qa_report["status"] == "pass"
    assert qa_report["technical"]["decode_ok"] is True
    assert len(qa_report["boundaries"]) == 1
    assert Path(qa_report["boundaries"][0]["timeline_view_path"]).is_file()
    assert qa_report["metadata"]["attempt"] == 1
    assert Path(qa.data["history_path"]).is_file()


def test_cut_boundary_qa_caps_attempts_at_three(tmp_path: Path):
    result = CutBoundaryQA().execute(
        {
            "video_path": str(tmp_path / "missing.mp4"),
            "edit_decisions_path": str(tmp_path / "missing.json"),
            "project_dir": str(tmp_path),
            "attempt": 4,
        }
    )
    assert not result.success
    assert "attempt must be between 1 and 3" in result.error


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_render_preserves_fractional_source_fps_by_default(tmp_path: Path):
    source = tmp_path / "source-23976.mp4"
    _make_fractional_fps_video(source)
    project = tmp_path / "project"
    edit_path = project / "artifacts" / "edit_decisions.json"
    edit = {
        "version": "1.0",
        "cuts": [
            {
                "id": "fractional",
                "source": str(source),
                "in_seconds": 0.0,
                "out_seconds": 0.7,
            }
        ],
        "render_runtime": "ffmpeg",
    }
    validate_artifact("edit_decisions", edit)
    _write_json(edit_path, edit)
    output = project / "renders" / "fractional.mp4"

    result = RawEditRender().execute(
        {
            "edit_decisions_path": str(edit_path),
            "output_path": str(output),
            "project_dir": str(project),
            "allowed_roots": [str(tmp_path)],
            "width": 160,
            "height": 90,
            "threads": 1,
        }
    )

    assert result.success, result.error
    report = json.loads(Path(result.data["render_report_path"]).read_text())
    assert report["metadata"]["fps_policy"] == "preserve_first_source"
    assert report["metadata"]["render_fps_rate"] == "24000/1001"
    assert report["outputs"][0]["fps"] == pytest.approx(23.976, rel=1e-3)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_overlay_is_pts_shifted_into_its_output_window(tmp_path: Path):
    from PIL import Image

    source = tmp_path / "black.mp4"
    overlay = tmp_path / "red.mp4"
    _make_color_video(source, "black", "160x90", 1.4, audio=True)
    _make_color_video(overlay, "red", "40x40", 0.5, audio=False)
    project = tmp_path / "project"
    edit_path = project / "artifacts" / "edit_decisions.json"
    edit = {
        "version": "1.0",
        "cuts": [
            {"id": "base", "source": str(source), "in_seconds": 0.0, "out_seconds": 1.2}
        ],
        "overlays": [
            {
                "asset_id": "red-card",
                "start_seconds": 0.4,
                "end_seconds": 0.9,
                "position": {"x": 0, "y": 0, "width": 40, "height": 40},
            }
        ],
        "render_runtime": "ffmpeg",
    }
    validate_artifact("edit_decisions", edit)
    _write_json(edit_path, edit)
    output = project / "renders" / "overlay.mp4"
    result = RawEditRender().execute(
        {
            "edit_decisions_path": str(edit_path),
            "output_path": str(output),
            "project_dir": str(project),
            "allowed_roots": [str(tmp_path)],
            "overlay_paths": {"red-card": str(overlay)},
            "width": 160,
            "height": 90,
            "fps": 30,
            "threads": 1,
        }
    )
    assert result.success, result.error
    report = json.loads(Path(result.data["render_report_path"]).read_text())
    assert report["metadata"]["overlay_count"] == 1

    pixels = []
    for index, timestamp in enumerate((0.2, 0.55, 1.0)):
        frame = tmp_path / f"frame-{index}.png"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                str(timestamp),
                "-i",
                str(output),
                "-frames:v",
                "1",
                "-c:v",
                "png",
                "-threads",
                "1",
                str(frame),
            ],
            check=True,
        )
        with Image.open(frame) as image:
            pixels.append(image.convert("RGB").getpixel((10, 10)))
    assert pixels[0][0] < 40
    assert pixels[1][0] > 150 and pixels[1][1] < 80
    assert pixels[2][0] < 40
