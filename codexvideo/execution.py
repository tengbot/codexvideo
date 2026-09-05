"""Governed tool dispatch and checkpoint persistence, without creative orchestration."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from jsonschema import validate

from lib.checkpoint import _enforce_stage_prerequisites, write_checkpoint
from lib.pipeline_loader import load_pipeline_readonly
from lib.production_integrity import content_hash, validate_stage_inputs
from lib.render_binding import file_fingerprint
from tools.base_tool import ToolRuntime, ToolStatus
from tools.cost_tracker import BudgetMode, CostTracker
from tools.tool_registry import registry


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _context(project: Path, stage: str) -> tuple[dict, dict]:
    marker = _read(project / "project.json")
    manifest = load_pipeline_readonly(marker["pipeline_type"])
    selected = next((item for item in manifest["stages"] if item["name"] == stage), None)
    if selected is None:
        raise ValueError(f"Unknown stage: {stage}")
    return marker, selected


def persist_stage(project: Path, stage: str, status: str, approval_note: str | None = None,
                  error: str | None = None) -> dict:
    project = project.expanduser().resolve()
    marker, selected = _context(project, stage)
    names = [*selected.get("produces", []), *selected.get("optional_produces", [])]
    artifacts = {name: _read(project / "artifacts" / f"{name}.json") for name in names
                 if (project / "artifacts" / f"{name}.json").is_file()}
    checkpoint = write_checkpoint(
        project.parent, marker["project_id"], stage, status, artifacts,
        human_approved=bool(approval_note and approval_note.strip()),
        metadata={"approval_note": approval_note} if approval_note else {}, error=error,
    )
    return {"checkpoint": str(checkpoint), "status": status, "stage": stage}


def invoke_tool(project: Path, stage: str, tool_name: str, inputs: dict, request_id: str,
                execute: bool = False, approval_path: Path | None = None) -> dict:
    project = project.expanduser().resolve()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", request_id):
        raise ValueError("request_id must be a short alphanumeric identifier")
    marker, selected = _context(project, stage)
    registry.ensure_discovered()
    tool = registry.get(tool_name)
    if tool is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    allowed = set(selected.get("tools_available", [])) | set(selected.get("required_tools", [])) | set(selected.get("optional_tools", []))
    selectors = [registry.get(name) for name in allowed]
    if tool_name not in allowed and not any(item and item.provider == "selector" and
            item.capability == tool.capability for item in selectors):
        raise ValueError(f"Tool {tool_name} is not declared for stage {stage}")
    if tool.provider == "selector" and inputs.get("operation") != "rank":
        raise ValueError("Dispatch the explicitly approved concrete provider, not an automatic selector")
    inputs = {**inputs, "project_dir": str(project)}
    validate(inputs, tool.input_schema)
    dependencies = []
    for key, value in inputs.items():
        if key.endswith("_path") and not key.startswith("output") and isinstance(value, str):
            path = Path(value).expanduser()
            if path.is_file():
                dependencies.append(file_fingerprint(path))
    fingerprint = content_hash({"stage": stage, "tool": tool_name, "version": tool.version,
                                "inputs": inputs, "dependencies": dependencies})
    estimate = float(tool.estimate_cost(inputs))
    if not math.isfinite(estimate) or estimate < 0:
        raise ValueError("Provider returned an invalid cost estimate")
    paid_or_unknown = estimate > 0 or tool.runtime in {ToolRuntime.API, ToolRuntime.HYBRID}
    approval = {
        "project_id": marker["project_id"], "request_id": request_id, "tool": tool_name,
        "input_sha256": fingerprint, "max_cost_usd": estimate,
        "approved": False, "user_statement": "",
    }
    plan = {"request_id": request_id, "tool": tool_name, "provider": tool.provider,
            "input_sha256": fingerprint, "estimated_usd": estimate,
            "approval_required": paid_or_unknown, "approval_template": approval}
    if not execute:
        return {**plan, "status": "prepared", "executed": False}
    _enforce_stage_prerequisites(project.parent, marker["project_id"], marker["pipeline_type"], stage, "completed")
    validate_stage_inputs(project, selected)
    if tool.get_status() != ToolStatus.AVAILABLE:
        raise ValueError(f"Tool is not available: {tool_name}; no fallback was executed")
    ceiling = estimate
    if paid_or_unknown:
        if approval_path is None:
            raise ValueError("Explicit per-call approval is required; prepare and review this request first")
        given = _read(approval_path)
        for field in ("project_id", "request_id", "tool", "input_sha256"):
            if given.get(field) != approval[field]:
                raise ValueError(f"Approval does not match this request: {field}")
        if given.get("approved") is not True or not str(given.get("user_statement", "")).strip():
            raise ValueError("Approval must record the user's explicit authorization")
        ceiling = float(given["max_cost_usd"])
        if not math.isfinite(ceiling) or ceiling < estimate or ceiling <= 0:
            raise ValueError("Paid/unknown calls require a positive approved ceiling covering the estimate")
    policy = _read(project / "artifacts/consumer_request.json")["execution"]
    lock = project / ".execution-lock"
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError("Project execution is already locked; inspect the prior process before recovery") from exc
    try:
        history = project / "history/tool-runs" / request_id
        if history.exists():
            raise ValueError("Request ID was already dispatched; inspect its receipt, do not resubmit blindly")
        tracker = CostTracker(budget_total_usd=policy["budget_usd"], reserve_pct=0,
                              single_action_approval_usd=ceiling,
                              require_approval_for_new_paid_tool=False, mode=BudgetMode.CAP,
                              cost_log_path=project / "cost_log.json")
        # The current approved project policy wins over a previous log's ceiling.
        tracker.budget_total_usd = float(policy["budget_usd"])
        entry_id = tracker.estimate(tool_name, request_id, ceiling)
        tracker.reserve(entry_id)
        history.mkdir(parents=True)
        receipt = {**plan, "status": "started", "reserved_usd": ceiling, "cost_entry_id": entry_id}
        path = history / "receipt.json"
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        try:
            result = tool.execute(inputs)
            # Keep uncertain charges reserved. Tool-reported spend is not a billing receipt.
            reported = float(result.cost_usd)
            if not math.isfinite(reported) or reported < 0:
                raise ValueError("Provider returned an invalid reported cost")
            pending = paid_or_unknown and (reported == 0 or not result.success)
            if not pending:
                tracker.reconcile(entry_id, reported, result.success)
            receipt.update(status="completed" if result.success else "failed",
                           result=asdict(result), reconciliation_pending=pending,
                           provider_billing_verified=False, cost_ceiling_exceeded=reported > ceiling)
            if reported > ceiling:
                receipt["status"] = "needs_attention"
        except Exception as exc:
            receipt.update(status="uncertain", error=type(exc).__name__,
                           reconciliation_pending=paid_or_unknown, provider_billing_verified=False)
            if not paid_or_unknown:
                tracker.reconcile(entry_id, 0, False)
        path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return {"status": receipt["status"], "receipt": str(path), "executed": True,
                "reconciliation_pending": receipt["reconciliation_pending"]}
    finally:
        lock.rmdir()
