"""Persist and verify stage artifacts for versioned consumer projects."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from lib.pipeline_loader import load_pipeline_readonly
from schemas.artifacts import validate_artifact


def content_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def strict_project(project: Path) -> bool:
    marker = project / "project.json"
    return marker.is_file() and json.loads(marker.read_text(encoding="utf-8")).get("integrity_version") == 1


def _snapshot(name: str, value: Any) -> Any:
    if name == "decision_log":
        return {"sha256": content_hash(value), "decision_count": len(value["decisions"])}
    return content_hash(value)


def validate_stage_inputs(project: Path, stage: dict[str, Any]) -> dict[str, Any]:
    values = {}
    for name in stage.get("required_artifacts_in", []):
        path = project / "artifacts" / f"{name}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        validate_artifact(name, value)
        if name == "script_qa_report" and (value["overall_status"] != "pass" or
                not all(check["passes"] for check in value["checks"].values())):
            raise ValueError("Script QA must pass before downstream production")
        if name == "creative_qa_report":
            from tools.analysis.creative_qa import CreativeQA
            reviewed = CreativeQA().execute({"report_path": str(path)})
            if not reviewed.success:
                raise ValueError(f"Creative QA blocks delivery: {reviewed.error}")
        values[name] = value
    return values


def snapshot_stage(project: Path, checkpoint: dict[str, Any]) -> dict[str, Any]:
    stage = next(s for s in load_pipeline_readonly(checkpoint["pipeline_type"])["stages"]
                 if s["name"] == checkpoint["stage"])
    produces = stage.get("produces", [])
    missing = set(produces) - checkpoint["artifacts"].keys()
    if missing:
        raise ValueError(f"Stage {checkpoint['stage']} is missing declared outputs: {sorted(missing)}")
    produces = [*produces, *(name for name in stage.get("optional_produces", [])
                             if name in checkpoint["artifacts"])]
    snapshot = {}
    for name, value in validate_stage_inputs(project, stage).items():
        snapshot[name] = _snapshot(name, value)
    for name in produces:
        value = checkpoint["artifacts"][name]
        validate_artifact(name, value)
    for name in produces:
        value = checkpoint["artifacts"][name]
        path = project / "artifacts" / f"{name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
        snapshot[name] = _snapshot(name, value)
    return snapshot


def verify_stage(project: Path, checkpoint: dict[str, Any]) -> None:
    hashes = checkpoint.get("metadata", {}).get("artifact_hashes")
    if hashes is None:
        if strict_project(project):
            raise ValueError(f"Stage {checkpoint['stage']} has no artifact integrity snapshot")
        return
    for name, expected in hashes.items():
        if not name.replace("_", "").isalnum():
            raise ValueError(f"Invalid artifact name: {name}")
        value = json.loads((project / "artifacts" / f"{name}.json").read_text(encoding="utf-8"))
        # New decisions may be appended, but prior approvals must not be rewritten.
        if name == "decision_log" and isinstance(expected, dict):
            value = {**value, "decisions": value["decisions"][:expected["decision_count"]]}
            expected = expected["sha256"]
        if content_hash(value) != expected:
            raise ValueError(f"Stage {checkpoint['stage']} is stale: {name} changed")
