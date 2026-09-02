"""Deterministic creative-quality gate for completed video reviews."""

from __future__ import annotations

import json
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
            "report_path": {"type": "string"},
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
