"""Deterministic FFmpeg renderer for raw-footage edit decision lists."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import time
from datetime import datetime, timezone
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

from .models import (
    group_subtitle_cues,
    load_transcript,
    parse_frame_rate,
    probe_media,
    read_json,
    resolve_safe_path,
    run_command,
    trim_words_to_cut,
    write_json,
    write_srt,
)
from .ported_video_use import auto_grade_for_clip, get_preset, measure_loudness


class RawEditRender(BaseTool):
    name = "raw_edit_render"
    version = "1.1.0"
    tier = ToolTier.CORE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "raw_footage_editing"
    provider = "openmontage"
    capabilities = [
        "edl_render",
        "cut_audio_fades",
        "hdr_to_sdr",
        "bounded_auto_grade",
        "overlay_pts_alignment",
        "subtitle_final_pass",
        "two_pass_loudness_normalization",
        "cut_boundary_padding_validation",
        "source_fps_preservation",
        "rotation_aware_media_probe",
        "subtitle_runtime_preflight",
        "font_fallback_safe_subtitles",
    ]
    best_for = [
        "Rendering reviewed source ranges without changing original media",
        "Making H.264/AAC/yuv420p MP4 files that play in browsers and social apps",
        "Building subtitles from the same source timing used for the edit",
    ]
    not_good_for = ["Generating footage", "Choosing editorial ranges without an EDL"]
    input_schema = {
        "type": "object",
        "required": ["edit_decisions_path", "output_path", "project_dir"],
        "properties": {
            "edit_decisions_path": {"type": "string"},
            "output_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "allowed_roots": {"type": "array", "items": {"type": "string"}},
            "transcript_paths": {"type": "object"},
            "overlay_paths": {"type": "object"},
            "grade": {"type": "string"},
            "quality": {"type": "string", "enum": ["draft", "preview", "final"]},
            "enforce_word_boundaries": {"type": "boolean"},
            "width": {"type": "integer", "minimum": 64},
            "height": {"type": "integer", "minimum": 64},
            "fps": {
                "oneOf": [
                    {"type": "number", "exclusiveMinimum": 0},
                    {"type": "string", "pattern": "^[0-9]+(?:\\.[0-9]+)?$|^[0-9]+/[0-9]+$"},
                ]
            },
            "threads": {"type": "integer", "minimum": 1},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=4096, network_required=False
    )
    side_effects = ["writes rendered video, subtitles, and render report"]
    user_visible_verification = [
        "Decode the complete output with FFmpeg",
        "Inspect every cut boundary with cut_boundary_qa",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            return self._render(inputs, started)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc), duration_seconds=time.monotonic() - started)

    def _render(self, inputs: dict[str, Any], started: float) -> ToolResult:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise RuntimeError("FFmpeg and FFprobe are required")
        project_dir = Path(inputs["project_dir"]).expanduser().resolve()
        project_dir.mkdir(parents=True, exist_ok=True)
        edit_path = Path(inputs["edit_decisions_path"]).expanduser().resolve()
        edit = read_json(edit_path)
        validate_artifact("edit_decisions", edit)
        cuts = edit["cuts"]
        if not cuts:
            raise ValueError("edit_decisions.cuts must contain at least one cut")

        width = int(inputs.get("width") or 720)
        height = int(inputs.get("height") or 1280)
        threads = min(4, int(inputs.get("threads") or 2))
        grade_mode = str(inputs.get("grade") or "none")
        quality = str(inputs.get("quality") or "final")
        preset, crf = self._quality_settings(quality)
        output_path = Path(inputs["output_path"]).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        allowed_roots = [Path(value) for value in inputs.get("allowed_roots", [str(project_dir)])]
        first_source = resolve_safe_path(
            cuts[0]["source"], base=edit_path.parent, allowed_roots=allowed_roots
        )
        first_source_info = probe_media(first_source)
        requested_fps = inputs.get("fps")
        fps = (
            parse_frame_rate(requested_fps)
            if requested_fps is not None
            else str(first_source_info.get("fps_rate") or "30/1")
        )
        transcripts = self._load_transcripts(inputs.get("transcript_paths") or {})
        overlay_paths = inputs.get("overlay_paths") or {}
        master_srt = project_dir / "artifacts" / "master_subtitles.srt"
        output_transcript_path = project_dir / "artifacts" / "output_transcript.json"
        boundary_warnings: list[str] = []
        grade_analyses: list[dict[str, Any]] = []
        source_fps_rates: dict[str, str] = {}

        with tempfile.TemporaryDirectory(prefix="raw-edit-", dir=project_dir) as temp_value:
            temp_dir = Path(temp_value)
            segment_paths: list[Path] = []
            subtitle_words: list[dict[str, Any]] = []
            timeline_cursor = 0.0
            hdr_sources: list[str] = []
            for index, cut in enumerate(cuts):
                source = resolve_safe_path(
                    cut["source"], base=edit_path.parent, allowed_roots=allowed_roots
                )
                source_info = probe_media(source)
                source_fps_rates[str(source)] = str(source_info.get("fps_rate") or "unknown")
                source_in = float(cut["in_seconds"])
                source_out = float(cut["out_seconds"])
                speed = float(cut.get("speed") or 1.0)
                if source_out <= source_in:
                    raise ValueError(f"Cut {cut['id']} has a non-positive duration")
                if source_out > source_info["duration_seconds"] + 0.15:
                    raise ValueError(
                        f"Cut {cut['id']} ends at {source_out:.3f}s, beyond {source_info['duration_seconds']:.3f}s"
                    )
                duration = (source_out - source_in) / speed
                segment_path = temp_dir / f"segment-{index:04d}.mp4"
                transcript = self._match_transcript(transcripts, cut["source"], source)
                if transcript:
                    boundary_warnings.extend(
                        self._check_cut_boundaries(
                            cut,
                            transcript,
                            enforce=bool(inputs.get("enforce_word_boundaries", False)),
                        )
                    )
                is_hdr = source_info["color_transfer"] in {"smpte2084", "arib-std-b67"}
                if is_hdr:
                    hdr_sources.append(str(source))
                grade_filter, grade_stats = self._resolve_grade(
                    grade_mode,
                    source,
                    source_in,
                    source_out - source_in,
                )
                grade_analyses.append(
                    {
                        "cut_id": cut["id"],
                        "mode": grade_mode,
                        "filter": grade_filter,
                        "stats": grade_stats,
                    }
                )
                self._render_segment(
                    source=source,
                    output=segment_path,
                    source_in=source_in,
                    source_duration=source_out - source_in,
                    output_duration=duration,
                    speed=speed,
                    width=width,
                    height=height,
                    fps=fps,
                    threads=threads,
                    has_audio=bool(source_info["has_audio"]),
                    is_hdr=is_hdr,
                    grade_filter=grade_filter,
                    encoder_preset=preset,
                    crf=crf,
                )
                segment_paths.append(segment_path)
                if transcript:
                    subtitle_words.extend(
                        trim_words_to_cut(
                            transcript,
                            source_in=source_in,
                            source_out=source_out,
                            timeline_start=timeline_cursor,
                            speed=speed,
                        )
                    )
                timeline_cursor += duration

            concat_path = temp_dir / "concat.mp4"
            self._concat_segments(segment_paths, concat_path)
            subtitles = edit.get("subtitles") or {}
            subtitle_enabled = bool(subtitles.get("enabled", bool(subtitle_words)))
            output_transcript = self._write_output_transcript(
                output_transcript_path,
                output_path,
                subtitle_words,
                timeline_cursor,
                transcripts,
            )
            if subtitle_enabled and subtitle_words:
                cues = group_subtitle_cues(
                    subtitle_words, max_words=int(subtitles.get("max_words_per_line") or 7)
                )
                write_srt(master_srt, cues)
            else:
                master_srt = None
            overlays = edit.get("overlays") or []
            if overlays or master_srt:
                visual_path = temp_dir / "composited.mp4"
                self._compose_final(
                    concat_path,
                    visual_path,
                    overlays=overlays,
                    overlay_paths=overlay_paths,
                    subtitle_path=master_srt,
                    subtitle_settings=subtitles,
                    edit_path=edit_path,
                    allowed_roots=allowed_roots,
                    height=height,
                    threads=threads,
                    encoder_preset=preset,
                    crf=crf,
                )
            else:
                visual_path = concat_path
            self._normalise_loudness(visual_path, output_path, threads=threads)

        final_info = probe_media(output_path)
        warnings = list(dict.fromkeys(boundary_warnings))
        if any(
            transcript["timing_quality"] == "cue_interpolated"
            for transcript in transcripts.values()
        ):
            warnings.append("SRT cue timing was interpolated and is not word-exact")
        report = {
            "version": "1.0",
            "outputs": [
                {
                    "path": str(output_path),
                    "format": "mp4",
                    "codec": final_info["codec"],
                    "audio_codec": "aac" if final_info["has_audio"] else "none",
                    "resolution": f"{final_info['width']}x{final_info['height']}",
                    "fps": round(final_info["fps"], 3),
                    "duration_seconds": round(final_info["duration_seconds"], 3),
                    "file_size_bytes": final_info["size_bytes"],
                    "platform_target": "social-vertical" if height > width else "web",
                }
            ],
            "render_time_seconds": round(time.monotonic() - started, 3),
            "warnings": warnings,
            "verification_notes": [
                "Rendered each cut independently with short audio fades",
                "Applied subtitles after visual concatenation",
                "Shifted overlay PTS to output windows before applying subtitles",
                "Applied two-pass EBU R128 loudness normalization when measurement succeeded",
                "Original source media was not modified",
                "Preserved the first source frame rate unless an explicit fps override was provided",
            ],
            "metadata": {
                "edit_decisions": str(edit_path),
                "master_subtitles": str(master_srt) if master_srt else None,
                "output_transcript": str(output_transcript_path) if output_transcript else None,
                "hdr_sources_tonemapped": sorted(set(hdr_sources)),
                "grade": grade_mode,
                "grade_analyses": grade_analyses,
                "quality": quality,
                "overlay_count": len(edit.get("overlays") or []),
                "ported_video_use_commit": "9575612f066aa517354790a645fd90f9f95a743b",
                "fps_policy": "explicit" if requested_fps is not None else "preserve_first_source",
                "render_fps_rate": fps,
                "source_fps_rates": source_fps_rates,
                "offline": True,
                "threads": threads,
            },
        }
        validate_artifact("render_report", report)
        report_path = project_dir / "artifacts" / "render_report.json"
        write_json(report_path, report)
        self._append_project_memory(project_dir, edit_path, output_path, report_path)
        duration = time.monotonic() - started
        artifacts = [str(output_path), str(report_path)]
        if master_srt:
            artifacts.append(str(master_srt))
        if output_transcript:
            artifacts.append(str(output_transcript_path))
        return ToolResult(
            success=True,
            data={
                "output_path": str(output_path),
                "render_report_path": str(report_path),
                "master_subtitles_path": str(master_srt) if master_srt else None,
                "output_transcript_path": str(output_transcript_path) if output_transcript else None,
            },
            artifacts=artifacts,
            duration_seconds=duration,
        )

    @staticmethod
    def _load_transcripts(paths: dict[str, Any]) -> dict[str, dict[str, Any]]:
        transcripts: dict[str, dict[str, Any]] = {}
        for key, value in paths.items():
            transcript = load_transcript(Path(str(value)).expanduser().resolve())
            transcripts[str(key)] = transcript
            transcripts[transcript["source_id"]] = transcript
            transcripts[Path(transcript["source_path"]).name] = transcript
            transcripts[str(Path(transcript["source_path"]).resolve())] = transcript
        return transcripts

    @staticmethod
    def _match_transcript(
        transcripts: dict[str, dict[str, Any]], source_value: str, source: Path
    ) -> dict[str, Any] | None:
        return (
            transcripts.get(source_value)
            or transcripts.get(str(source))
            or transcripts.get(source.name)
            or transcripts.get(source.stem)
        )

    @staticmethod
    def _quality_settings(quality: str) -> tuple[str, int]:
        settings = {
            "draft": ("ultrafast", 28),
            "preview": ("medium", 22),
            "final": ("fast", 20),
        }
        if quality not in settings:
            raise ValueError(f"Unknown quality mode: {quality}")
        return settings[quality]

    @staticmethod
    def _resolve_grade(
        grade: str,
        source: Path,
        start: float,
        duration: float,
    ) -> tuple[str, dict[str, float]]:
        if grade == "auto":
            return auto_grade_for_clip(source, start=start, duration=duration)
        if "=" in grade or "," in grade:
            return grade, {}
        try:
            return get_preset(grade), {}
        except KeyError as exc:
            raise ValueError(str(exc)) from exc

    @staticmethod
    def _check_cut_boundaries(
        cut: dict[str, Any],
        transcript: dict[str, Any],
        *,
        enforce: bool,
    ) -> list[str]:
        source_in = float(cut["in_seconds"])
        source_out = float(cut["out_seconds"])
        words = [word for word in transcript["words"] if word.get("type") == "word"]
        if not words:
            return []
        problems: list[str] = []
        for edge_name, edge in (("in", source_in), ("out", source_out)):
            crossing = next(
                (
                    word
                    for word in words
                    if float(word["start_seconds"]) + 0.001 < edge < float(word["end_seconds"]) - 0.001
                ),
                None,
            )
            if crossing:
                problems.append(
                    f"Cut {cut['id']} {edge_name} edge {edge:.3f}s falls inside '{crossing['text']}'"
                )
        selected = [
            word
            for word in words
            if float(word["end_seconds"]) > source_in and float(word["start_seconds"]) < source_out
        ]
        if selected:
            in_padding = float(selected[0]["start_seconds"]) - source_in
            out_padding = source_out - float(selected[-1]["end_seconds"])
            if source_in > 0.001 and not 0.03 <= in_padding <= 0.2:
                problems.append(
                    f"Cut {cut['id']} leading padding is {in_padding:.3f}s; recommended 0.030-0.200s"
                )
            if not 0.03 <= out_padding <= 0.2:
                problems.append(
                    f"Cut {cut['id']} trailing padding is {out_padding:.3f}s; recommended 0.030-0.200s"
                )
        if enforce and transcript["timing_quality"] == "word_exact" and problems:
            raise ValueError("; ".join(problems))
        return problems

    @staticmethod
    def _write_output_transcript(
        path: Path,
        output_path: Path,
        words: list[dict[str, Any]],
        duration: float,
        transcripts: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not words:
            path.unlink(missing_ok=True)
            return None
        normalized = []
        for index, word in enumerate(words, start=1):
            normalized.append({**word, "id": f"ow{index:06d}"})
        qualities = {item["timing_quality"] for item in transcripts.values()}
        timing_quality = "word_exact" if qualities == {"word_exact"} else "cue_interpolated"
        artifact = {
            "version": "1.0",
            "source_id": "rendered-output",
            "source_path": str(output_path),
            "language": next(iter(transcripts.values()))["language"] if transcripts else "en",
            "duration_seconds": round(duration, 3),
            "timing_quality": timing_quality,
            "words": normalized,
            "metadata": {
                "timeline": "output",
                "ported_video_use_rule": "word.start - segment_start + segment_offset",
            },
        }
        validate_artifact("source_transcript", artifact)
        write_json(path, artifact)
        return artifact

    @staticmethod
    def _atempo(speed: float) -> str:
        factors: list[float] = []
        while speed > 2.0:
            factors.append(2.0)
            speed /= 2.0
        while speed < 0.5:
            factors.append(0.5)
            speed /= 0.5
        factors.append(speed)
        return ",".join(f"atempo={factor:.6f}" for factor in factors)

    def _render_segment(
        self,
        *,
        source: Path,
        output: Path,
        source_in: float,
        source_duration: float,
        output_duration: float,
        speed: float,
        width: int,
        height: int,
        fps: str,
        threads: int,
        has_audio: bool,
        is_hdr: bool,
        grade_filter: str,
        encoder_preset: str,
        crf: int,
    ) -> None:
        command = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
        if not has_audio:
            command.extend(
                ["-f", "lavfi", "-t", f"{output_duration:.6f}", "-i", "anullsrc=r=48000:cl=stereo"]
            )
        scale = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1"
        )
        if is_hdr:
            scale = (
                "zscale=t=linear:npl=100,format=gbrpf32le,"
                "tonemap=hable:desat=0,zscale=p=bt709:t=bt709:m=bt709:r=tv," + scale
            )
        grade_chain = f",{grade_filter}" if grade_filter else ""
        video_filter = (
            f"trim=start={source_in:.6f}:duration={source_duration:.6f},setpts=PTS-STARTPTS,"
            f"setpts=PTS/{speed:.6f},{scale}{grade_chain},fps={fps},format=yuv420p"
        )
        fade = min(0.03, output_duration / 3)
        audio_input = "[0:a:0]" if has_audio else "[1:a:0]"
        audio_filter = (
            f"{audio_input}atrim=start={source_in if has_audio else 0:.6f}:"
            f"duration={source_duration if has_audio else output_duration:.6f},"
            f"asetpts=PTS-STARTPTS,{self._atempo(speed) if has_audio else 'anull'},"
            f"afade=t=in:st=0:d={fade:.3f},"
            f"afade=t=out:st={max(0, output_duration - fade):.6f}:d={fade:.3f}[a]"
        )
        command.extend(
            [
                "-filter_complex",
                f"[0:v:0]{video_filter}[v];{audio_filter}",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-t",
                f"{output_duration:.6f}",
                "-c:v",
                "libx264",
                "-preset",
                encoder_preset,
                "-crf",
                str(crf),
                "-profile:v",
                "high",
                "-level",
                "4.1",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-threads",
                str(threads),
                str(output),
            ]
        )
        run_command(command)

    @staticmethod
    def _concat_segments(paths: list[Path], output: Path) -> None:
        list_path = output.with_suffix(".txt")
        lines = [f"file '{str(path).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in paths]
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        run_command(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output),
            ]
        )

    @staticmethod
    def _compose_final(
        source: Path,
        output: Path,
        *,
        overlays: list[dict[str, Any]],
        overlay_paths: dict[str, Any],
        subtitle_path: Path | None,
        subtitle_settings: dict[str, Any],
        edit_path: Path,
        allowed_roots: list[Path],
        height: int,
        threads: int,
        encoder_preset: str,
        crf: int,
    ) -> None:
        command = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
        resolved_overlays: list[tuple[dict[str, Any], Path]] = []
        for overlay in overlays:
            asset_id = str(overlay["asset_id"])
            path_value = str(overlay_paths.get(asset_id) or asset_id)
            overlay_path = resolve_safe_path(
                path_value,
                base=edit_path.parent,
                allowed_roots=allowed_roots,
            )
            command.extend(["-i", str(overlay_path)])
            resolved_overlays.append((overlay, overlay_path))

        filter_parts: list[str] = []
        for index, (overlay, _) in enumerate(resolved_overlays, start=1):
            position = overlay["position"]
            chain = f"[{index}:v]"
            if position.get("width") and position.get("height"):
                chain += f"scale={int(position['width'])}:{int(position['height'])},"
            opacity = float(overlay.get("opacity", 1.0))
            if opacity < 1.0:
                chain += f"format=rgba,colorchannelmixer=aa={opacity:.4f},"
            start = float(overlay["start_seconds"])
            chain += f"setpts=PTS-STARTPTS+{start:.6f}/TB[overlay{index}]"
            filter_parts.append(chain)

        current = "[0:v:0]"
        for index, (overlay, _) in enumerate(resolved_overlays, start=1):
            start = float(overlay["start_seconds"])
            end = float(overlay["end_seconds"])
            position = overlay["position"]
            output_label = f"[video{index}]"
            filter_parts.append(
                f"{current}[overlay{index}]overlay=x={position['x']}:y={position['y']}:"
                f"enable='between(t,{start:.6f},{end:.6f})':eof_action=pass{output_label}"
            )
            current = output_label

        if subtitle_path:
            RawEditRender._require_subtitles_filter()
            escaped = (
                str(subtitle_path)
                .replace("\\", "\\\\")
                .replace(":", "\\:")
                .replace("'", "\\'")
            )
            force_style = RawEditRender._subtitle_force_style(subtitle_settings, height)
            filter_parts.append(
                f"{current}subtitles=filename='{escaped}':force_style='{force_style}'[outv]"
            )
            output_label = "[outv]"
        else:
            output_label = current

        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                output_label,
                "-map",
                "0:a:0",
                "-c:v",
                "libx264",
                "-preset",
                encoder_preset,
                "-crf",
                str(crf),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                "-threads",
                str(threads),
                str(output),
            ]
        )
        run_command(command)

    @staticmethod
    def _require_subtitles_filter() -> None:
        result = run_command(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or not re.search(r"^\s*\S+\s+subtitles\s", output, re.MULTILINE):
            raise RuntimeError(
                "This FFmpeg build does not provide the libass subtitles filter. "
                "Install an FFmpeg build with libass or use a Remotion caption route "
                "before starting the final render."
            )

    @staticmethod
    def _subtitle_force_style(settings: dict[str, Any], height: int) -> str:
        position = settings.get("position") or "bottom-center"
        alignment = {"top-center": 8, "center": 5, "bottom-center": 2}.get(position, 2)
        margin_v = 90 if height >= 1000 else 36
        font_size = int(settings.get("font_size") or (28 if height >= 1000 else 22))
        style = []
        if settings.get("font"):
            style.append(f"FontName={settings['font']}")
        style.extend(
            [
                f"FontSize={font_size}",
                "PrimaryColour=&H00FFFFFF",
                "OutlineColour=&H00101010",
                "BorderStyle=1",
                "Outline=3",
                "Shadow=0",
                f"Alignment={alignment}",
                f"MarginV={margin_v}",
            ]
        )
        return ",".join(style)

    @staticmethod
    def _normalise_loudness(source: Path, output: Path, *, threads: int) -> None:
        target = "loudnorm=I=-14:LRA=11:TP=-1.0"
        stats = measure_loudness(source, integrated=-14.0, true_peak=-1.0, range_lu=11.0)
        audio_filter = target
        if stats:
            audio_filter = (
                f"{target}:measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:"
                f"measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:"
                f"offset={stats['target_offset']}:linear=true:print_format=summary"
            )
        run_command(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                "-c:v",
                "copy",
                "-af",
                audio_filter,
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                "-threads",
                str(threads),
                str(output),
            ]
        )

    @staticmethod
    def _append_project_memory(project_dir: Path, edit_path: Path, output: Path, report: Path) -> None:
        memory_path = project_dir / "project.md"
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = (
            f"\n## Raw-footage render {stamp}\n\n"
            f"- EDL: `{edit_path}`\n"
            f"- Output: `{output}`\n"
            f"- Report: `{report}`\n"
            "- Runtime: local FFmpeg; no external transcription or editing API.\n"
        )
        with memory_path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
