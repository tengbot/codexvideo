"""Deterministic creative-quality gate for completed video reviews."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from lib.render_binding import bind_render, validate_render_binding, verify_playable_video
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


class CreativeQA(BaseTool):
    name = "creative_qa"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT
    capability = "analysis"
    provider = "codexvideo"
    capabilities = ["creative_quality_gate", "consumer_viewpoint_gate", "marketing_video_gate"]
    best_for = ["Separating creative acceptance from technical decode QA"]
    not_good_for = ["Replacing human or agent visual inspection"]
    input_schema = {
        "type": "object",
        "required": ["report_path"],
        "properties": {
            "operation": {"enum": ["prepare", "evaluate"], "default": "evaluate"},
            "report_path": {"type": "string"},
            "video_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "output_path": {"type": ["string", "null"]},
            "minimum_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
    }
    output_schema = {"type": "object"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=64, disk_mb=8, network_required=False)

    _CRITICAL = (
        "hook_pain",
        "consumer_viewpoint",
        "proof_visible",
        "visual_copy_match",
        "cta",
        "technical_decode",
    )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            path = Path(inputs["report_path"])
            report = json.loads(path.read_text(encoding="utf-8"))
            validate_artifact("creative_qa_report", report)
            checks = report["checks"]
            if inputs.get("operation") == "prepare":
                verify_playable_video(Path(inputs["video_path"]))
                report["render_binding"] = bind_render(
                    Path(inputs["video_path"]), Path(inputs.get("project_dir") or path.parent.parent)
                )
                report["evaluated_at"] = None
                report["overall_status"] = "pending"
                report["overall_score"] = 0.0
                report["blocking_issues"] = ["new render requires visual and audio review"]
                for check in checks.values():
                    check.update(score=0.0, passes=False, evidence="pending review of bound render")
                validate_artifact("creative_qa_report", report)
                path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                return ToolResult(success=True, data={"creative_qa_report": report}, artifacts=[str(path)])
            validate_render_binding(report.get("render_binding"))
            decode_evidence = verify_playable_video(Path(report["render_binding"]["video"]["path"]))
            checks["technical_decode"] = {"score": 1.0, "passes": True, "evidence": decode_evidence}
            minimum = float(inputs.get("minimum_score", 0.80))
            score = round(sum(float(check["score"]) for check in checks.values()) / len(checks), 3)
            blocking = [name for name in self._CRITICAL if not checks[name]["passes"]]
            for name, check in checks.items():
                if check["score"] < 0.6 and name not in blocking:
                    blocking.append(name)
            passed = score >= minimum and not blocking
            report["evaluated_at"] = datetime.now(timezone.utc).isoformat()
            report["overall_score"] = score
            report["overall_status"] = "pass" if passed else "fail"
            report["blocking_issues"] = blocking
            validate_artifact("creative_qa_report", report)
            artifacts = []
            if inputs.get("output_path"):
                output = Path(inputs["output_path"])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, indent=2), encoding="utf-8")
                artifacts.append(str(output))
            return ToolResult(
                success=passed,
                data={"creative_qa_report": report},
                artifacts=artifacts,
                error=None if passed else f"Creative QA failed: {blocking}",
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"creative QA failed: {exc}")
