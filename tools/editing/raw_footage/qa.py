"""Visual timeline and deterministic cut-boundary QA for rendered edits."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from tools.base_tool import (
    BaseTool,
    Determinism,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

from .models import load_transcript, probe_media, read_json, run_command, timeline_boundaries, write_json
from .ported_video_use import compute_envelope, find_silences, words_in_range


class TimelineView(BaseTool):
    name = "timeline_view"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_START

    capability = "raw_footage_editing"
    provider = "openmontage"
    capabilities = [
        "timeline_contact_sheet",
        "rms_waveform_context",
        "transcript_word_labels",
        "silence_gap_shading",
        "timestamp_labels",
    ]
    best_for = ["Reviewing a cut boundary without scrubbing the complete video"]
    not_good_for = ["Replacing final human playback review"]
    input_schema = {
        "type": "object",
        "required": ["video_path", "output_path"],
        "properties": {
            "video_path": {"type": "string"},
            "output_path": {"type": "string"},
            "start_seconds": {"type": "number", "minimum": 0},
            "end_seconds": {"type": "number", "minimum": 0},
            "samples": {"type": "integer", "minimum": 2, "maximum": 12},
            "label": {"type": "string"},
            "transcript_path": {"type": "string"},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=128, network_required=False
    )
    side_effects = ["writes a PNG timeline contact sheet"]
    user_visible_verification = ["Inspect frame continuity and waveform around the labeled interval"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            return self._build(inputs)
        except (OSError, ValueError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc))

    def _build(self, inputs: dict[str, Any]) -> ToolResult:
        from PIL import Image, ImageDraw, ImageFont

        video_path = Path(inputs["video_path"]).expanduser().resolve()
        output_path = Path(inputs["output_path"]).expanduser().resolve()
        info = probe_media(video_path)
        start = max(0.0, float(inputs.get("start_seconds") or 0))
        end = min(
            info["duration_seconds"],
            float(inputs.get("end_seconds") or info["duration_seconds"]),
        )
        if end <= start:
            raise ValueError("timeline view end_seconds must be after start_seconds")
        samples = int(inputs.get("samples") or 8)
        last_frame_time = min(end, max(start, info["duration_seconds"] - 1 / max(info["fps"], 25)))
        timestamps = [
            start + (last_frame_time - start) * index / (samples - 1)
            for index in range(samples)
        ]
        frame_width = 260
        label_height = 36
        waveform_height = 140
        transcript_path = inputs.get("transcript_path")
        transcript = (
            load_transcript(Path(transcript_path).expanduser().resolve())
            if transcript_path
            else None
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="timeline-view-", dir=output_path.parent) as temp_value:
            temp_dir = Path(temp_value)
            frames: list[Any] = []
            for index, timestamp in enumerate(timestamps):
                frame_path = temp_dir / f"frame-{index:02d}.png"
                self._extract_frame(video_path, frame_path, timestamp, frame_width)
                if not frame_path.is_file():
                    timestamp = max(start, timestamp - max(0.15, 3 / max(info["fps"], 25)))
                    timestamps[index] = timestamp
                    self._extract_frame(video_path, frame_path, timestamp, frame_width)
                if not frame_path.is_file():
                    raise RuntimeError(f"FFmpeg produced no frame near {timestamp:.3f}s")
                frames.append(Image.open(frame_path).convert("RGB"))
            frame_height = frames[0].height
            canvas_width = frame_width * samples
            canvas = Image.new(
                "RGB",
                (canvas_width, label_height + frame_height + waveform_height),
                "#111318",
            )
            draw = ImageDraw.Draw(canvas, "RGBA")
            font_path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
            font = ImageFont.truetype(str(font_path), 18) if font_path.is_file() else ImageFont.load_default()
            small_font = ImageFont.truetype(str(font_path), 13) if font_path.is_file() else ImageFont.load_default()
            label = str(inputs.get("label") or f"{start:.3f}s - {end:.3f}s")
            draw.text((12, 8), label, fill="#F5F7FA", font=font)
            for index, (frame, timestamp) in enumerate(zip(frames, timestamps)):
                x = index * frame_width
                canvas.paste(frame, (x, label_height))
                draw.rectangle((x + 5, label_height + 5, x + 91, label_height + 29), fill="#111318")
                draw.text((x + 10, label_height + 7), f"{timestamp:.3f}s", fill="#FFFFFF", font=font)
                frame.close()
            waveform_y = label_height + frame_height
            draw.rectangle(
                (0, waveform_y, canvas_width, waveform_y + waveform_height),
                fill=(10, 11, 14, 255),
            )
            words = words_in_range(transcript, start, end)
            silences = find_silences(words, start, end, threshold=0.4) if words else []

            def time_to_x(value: float) -> int:
                return int((value - start) / max(0.001, end - start) * canvas_width)

            for silence_start, silence_end in silences:
                draw.rectangle(
                    (
                        time_to_x(silence_start),
                        waveform_y,
                        time_to_x(silence_end),
                        waveform_y + waveform_height,
                    ),
                    fill=(50, 80, 120, 110),
                )
            envelope = compute_envelope(video_path, start, end, samples=max(canvas_width, 200))
            midpoint = waveform_y + waveform_height // 2
            amplitude = waveform_height // 2 - 12
            top = []
            bottom = []
            for index, value in enumerate(envelope):
                x = int(index * (canvas_width - 1) / max(1, len(envelope) - 1))
                offset = int(float(value) * amplitude)
                top.append((x, midpoint - offset))
                bottom.append((x, midpoint + offset))
            if top:
                draw.polygon(top + list(reversed(bottom)), fill=(54, 211, 153, 70))
                draw.line(top, fill=(54, 211, 153, 255), width=1)
                draw.line(bottom, fill=(54, 211, 153, 255), width=1)
            last_label_x = -999
            for word in words:
                word_start = float(word["start_seconds"])
                word_end = float(word["end_seconds"])
                center_x = (time_to_x(word_start) + time_to_x(word_end)) // 2
                if center_x - last_label_x < 34:
                    continue
                draw.line(
                    (center_x, waveform_y, center_x, waveform_y + 7),
                    fill=(180, 186, 196, 255),
                    width=1,
                )
                draw.text(
                    (center_x + 2, waveform_y + 8),
                    str(word.get("text") or ""),
                    fill=(245, 247, 250, 255),
                    font=small_font,
                )
                last_label_x = center_x
            canvas.save(output_path, format="PNG", optimize=True)
        return ToolResult(
            success=True,
            data={
                "timeline_view_path": str(output_path),
                "timestamps": timestamps,
                "word_labels": len(words),
                "silence_gaps": len(silences),
            },
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _extract_frame(video_path: Path, frame_path: Path, timestamp: float, width: int) -> None:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:-2,format=rgb24",
                "-c:v",
                "png",
                "-threads",
                "1",
                str(frame_path),
            ]
        )


class CutBoundaryQA(BaseTool):
    name = "cut_boundary_qa"
    version = "1.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "raw_footage_editing"
    provider = "openmontage"
    capabilities = [
        "full_decode_check",
        "black_frame_detection",
        "silence_detection",
        "clipping_detection",
        "every_boundary_visualization",
        "strict_revision_gate",
        "attempt_history",
    ]
    best_for = ["Producing durable evidence that every EDL boundary was checked"]
    not_good_for = ["Judging whether the creative concept is persuasive"]
    input_schema = {
        "type": "object",
        "required": ["video_path", "edit_decisions_path", "project_dir"],
        "properties": {
            "video_path": {"type": "string"},
            "edit_decisions_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "master_subtitles_path": {"type": "string"},
            "output_transcript_path": {"type": "string"},
            "silence_threshold_seconds": {"type": "number", "minimum": 0.2},
            "attempt": {"type": "integer", "minimum": 1, "maximum": 3},
            "strict": {"type": "boolean", "default": True},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=512, network_required=False
    )
    side_effects = ["writes cut QA JSON and PNG evidence"]
    user_visible_verification = [
        "Open the overview and every boundary PNG",
        "Confirm full decode, browser-safe codec, audio level, and silence results",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            return self._inspect(inputs)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc))

    def _inspect(self, inputs: dict[str, Any]) -> ToolResult:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("FFmpeg and FFprobe are required")
        video_path = Path(inputs["video_path"]).expanduser().resolve()
        edit_path = Path(inputs["edit_decisions_path"]).expanduser().resolve()
        project_dir = Path(inputs["project_dir"]).expanduser().resolve()
        attempt = int(inputs.get("attempt") or 1)
        if not 1 <= attempt <= 3:
            raise ValueError("attempt must be between 1 and 3")
        strict = bool(inputs.get("strict", True))
        review_dir = project_dir / "review" / "cut-boundaries" / f"attempt-{attempt:02d}"
        review_dir.mkdir(parents=True, exist_ok=True)
        edit = read_json(edit_path)
        validate_artifact("edit_decisions", edit)
        info = probe_media(video_path)
        output_transcript_path = inputs.get("output_transcript_path")
        if output_transcript_path and not Path(output_transcript_path).is_file():
            output_transcript_path = None

        decode = run_command(
            ["ffmpeg", "-v", "error", "-i", str(video_path), "-f", "null", "-"],
            check=False,
        )
        black_result = run_command(
            [
                "ffmpeg",
                "-v",
                "info",
                "-i",
                str(video_path),
                "-vf",
                "blackdetect=d=0.04:pic_th=0.98:pix_th=0.10",
                "-an",
                "-f",
                "null",
                "-",
            ],
            check=False,
        )
        black_intervals = [
            (float(start), float(end))
            for start, end in re.findall(
                r"black_start:([0-9.]+).*?black_end:([0-9.]+)", black_result.stderr
            )
        ]
        silence_result = run_command(
            [
                "ffmpeg",
                "-v",
                "info",
                "-i",
                str(video_path),
                "-af",
                "silencedetect=n=-42dB:d=0.35",
                "-f",
                "null",
                "-",
            ],
            check=False,
        )
        silence_starts = [float(value) for value in re.findall(r"silence_start: ([0-9.]+)", silence_result.stderr)]
        silence_ends = [float(value) for value in re.findall(r"silence_end: ([0-9.]+)", silence_result.stderr)]
        silence_intervals = [
            {"start_seconds": round(start, 3), "end_seconds": round(end, 3)}
            for start, end in zip(silence_starts, silence_ends)
            if end >= start
        ]
        volume_result = run_command(
            ["ffmpeg", "-v", "info", "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"],
            check=False,
        )
        max_match = re.search(r"max_volume: (-?[0-9.]+) dB", volume_result.stderr)
        max_volume = float(max_match.group(1)) if max_match else None
        silence_threshold = float(inputs.get("silence_threshold_seconds") or 2.5)
        unexpected_silence = any(
            interval["end_seconds"] - interval["start_seconds"] >= silence_threshold
            for interval in silence_intervals
        )

        view_tool = TimelineView()
        overview_path = review_dir / "timeline-overview.png"
        overview = view_tool.execute(
            {
                "video_path": str(video_path),
                "output_path": str(overview_path),
                "start_seconds": 0,
                "end_seconds": info["duration_seconds"],
                "samples": 8,
                "label": "Full edit overview",
                "transcript_path": output_transcript_path,
                "project_dir": str(project_dir),
            }
        )
        if not overview.success:
            raise RuntimeError(overview.error or "Could not build overview")

        boundaries = []
        for index, boundary in enumerate(timeline_boundaries(edit["cuts"]), start=1):
            view_path = review_dir / f"boundary-{index:02d}-{boundary:.3f}s.png"
            view = view_tool.execute(
                {
                    "video_path": str(video_path),
                    "output_path": str(view_path),
                    "start_seconds": max(0, boundary - 0.45),
                    "end_seconds": min(info["duration_seconds"], boundary + 0.45),
                    "samples": 6,
                    "label": f"Boundary {index} at {boundary:.3f}s",
                    "transcript_path": output_transcript_path,
                    "project_dir": str(project_dir),
                }
            )
            if not view.success:
                raise RuntimeError(view.error or f"Could not build boundary {index}")
            black_at_boundary = any(start <= boundary + 0.08 and end >= boundary - 0.08 for start, end in black_intervals)
            boundaries.append(
                {
                    "id": f"boundary-{index:02d}",
                    "time_seconds": boundary,
                    "timeline_view_path": str(view_path),
                    "black_frame_detected": black_at_boundary,
                    "status": "review" if black_at_boundary else "pass",
                }
            )

        issues: list[str] = []
        if decode.returncode != 0:
            issues.append(f"Full decode failed: {decode.stderr.strip()[-500:]}")
        if info["codec"] != "h264" or info["pixel_format"] != "yuv420p":
            issues.append(f"Compatibility profile is {info['codec']}/{info['pixel_format']}, expected h264/yuv420p")
        if not info["has_audio"]:
            issues.append("Output has no audio stream")
        if max_volume is not None and max_volume >= -0.1:
            issues.append(f"Audio peak is close to clipping at {max_volume:.1f} dB")
        if unexpected_silence:
            issues.append(f"Audio contains silence longer than {silence_threshold:.1f}s")
        if any(boundary["black_frame_detected"] for boundary in boundaries):
            issues.append("A black frame overlaps at least one cut boundary")
        status = "fail" if decode.returncode != 0 or not info["has_audio"] else ("revise" if issues else "pass")
        master_subtitles = inputs.get("master_subtitles_path")
        if master_subtitles and not Path(master_subtitles).is_file():
            master_subtitles = None
        report = {
            "version": "1.0",
            "output_path": str(video_path),
            "status": status,
            "technical": {
                "decode_ok": decode.returncode == 0,
                "duration_seconds": round(info["duration_seconds"], 3),
                "width": info["width"],
                "height": info["height"],
                "fps": round(info["fps"], 3),
                "codec": info["codec"],
                "pixel_format": info["pixel_format"],
                "has_audio": info["has_audio"],
                "size_bytes": info["size_bytes"],
            },
            "audio": {
                "max_volume_db": max_volume,
                "clipping_detected": max_volume is not None and max_volume >= -0.1,
                "unexpected_silence": unexpected_silence,
                "silence_intervals": silence_intervals,
            },
            "boundaries": boundaries,
            "artifacts": {
                "overview": str(overview_path),
                "master_subtitles": str(master_subtitles) if master_subtitles else None,
            },
            "issues": issues,
            "metadata": {
                "edit_decisions": str(edit_path),
                "black_intervals": black_intervals,
                "output_transcript": str(output_transcript_path) if output_transcript_path else None,
                "offline": True,
                "attempt": attempt,
                "retry_allowed": status != "pass" and attempt < 3,
                "repair_required": status != "pass",
            },
        }
        validate_artifact("cut_qa_report", report)
        report_path = project_dir / "artifacts" / "cut_qa_report.json"
        history_path = project_dir / "history" / f"cut_qa_report_attempt_{attempt:02d}.json"
        write_json(history_path, report)
        write_json(report_path, report)
        accepted = status == "pass" if strict else status != "fail"
        return ToolResult(
            success=accepted,
            data={
                "report": report,
                "report_path": str(report_path),
                "history_path": str(history_path),
            },
            artifacts=[str(report_path), str(history_path), str(overview_path)]
            + [boundary["timeline_view_path"] for boundary in boundaries],
            error=("; ".join(issues) or "Cut review requires revision") if not accepted else None,
        )
