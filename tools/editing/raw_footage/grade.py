"""OpenMontage tool wrapper around the MIT-licensed video-use grade logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

from .models import run_command
from .ported_video_use import PRESETS, auto_grade_for_clip, get_preset


class RawFootageGrade(BaseTool):
    name = "raw_footage_grade"
    version = "1.0.0"
    tier = ToolTier.ENHANCE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_START

    capability = "raw_footage_editing"
    provider = "openmontage"
    capabilities = ["signalstats_analysis", "bounded_auto_grade", "grade_presets"]
    best_for = ["Subtle per-range cleanup before raw-footage concatenation"]
    not_good_for = ["Replacing creative color decisions or a calibrated grading suite"]
    input_schema = {
        "type": "object",
        "required": ["operation", "input_path"],
        "properties": {
            "operation": {"type": "string", "enum": ["analyze", "apply"]},
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "mode": {"type": "string"},
            "filter": {"type": "string"},
            "start_seconds": {"type": "number", "minimum": 0},
            "duration_seconds": {"type": "number", "minimum": 0.05},
            "threads": {"type": "integer", "minimum": 1},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=1024, network_required=False
    )
    side_effects = ["optionally writes a locally graded MP4"]
    user_visible_verification = ["Compare sampled luma and saturation before accepting the filter"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            source = Path(inputs["input_path"]).expanduser().resolve()
            if not source.is_file():
                raise FileNotFoundError(source)
            start = float(inputs.get("start_seconds") or 0)
            duration_value = inputs.get("duration_seconds")
            duration = float(duration_value) if duration_value is not None else None
            mode = str(inputs.get("mode") or "auto")
            if inputs.get("filter") is not None:
                filter_value = str(inputs["filter"])
                stats: dict[str, float] = {}
            elif mode == "auto":
                filter_value, stats = auto_grade_for_clip(source, start=start, duration=duration)
            else:
                filter_value = get_preset(mode)
                stats = {}
            if inputs["operation"] == "analyze":
                return ToolResult(
                    success=True,
                    data={
                        "filter": filter_value,
                        "stats": stats,
                        "mode": mode,
                        "available_presets": sorted(PRESETS),
                        "source_commit": "9575612f066aa517354790a645fd90f9f95a743b",
                    },
                )
            output = Path(inputs["output_path"]).expanduser().resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            threads = min(4, int(inputs.get("threads") or 2))
            command = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
            if filter_value:
                command.extend(
                    [
                        "-vf",
                        filter_value,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "copy",
                    ]
                )
            else:
                command.extend(["-c", "copy"])
            command.extend(["-movflags", "+faststart", "-threads", str(threads), str(output)])
            run_command(command)
            return ToolResult(
                success=True,
                data={"output_path": str(output), "filter": filter_value, "stats": stats},
                artifacts=[str(output)],
            )
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc))
