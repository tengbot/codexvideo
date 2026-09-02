"""Consumer project scaffolding and resumable run-plan generation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backlot.state import load_board_state
from codexvideo.catalog import choose_format, choose_style, destination_settings, load_catalog
from lib.checkpoint import init_project
from lib.pipeline_loader import get_stage_order, load_pipeline
from schemas.artifacts import validate_artifact
from tools.tool_registry import ToolRegistry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:64] or "codexvideo-project").strip("-")


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_capability_manifest(
    required_capabilities: list[str],
    optional_capabilities: list[str],
    provider_pack: str,
) -> dict[str, Any]:
    registry = ToolRegistry()
    registry.discover()
    summary = registry.provider_menu_summary()
    by_capability = {item["capability"]: item for item in summary["capabilities"]}

    def status_for(capability: str) -> dict[str, Any]:
        item = by_capability.get(capability, {})
        return {
            "capability": capability,
            "configured": int(item.get("configured", 0)),
            "total": int(item.get("total", 0)),
            "available_providers": item.get("available_providers", []),
        }

    required = [status_for(name) for name in required_capabilities]
    optional = [status_for(name) for name in optional_capabilities]
    missing_required = [item["capability"] for item in required if item["configured"] == 0]
    catalog = load_catalog()
    if provider_pack not in catalog["provider_packs"] and provider_pack != "auto":
        raise ValueError(f"Unknown provider pack: {provider_pack}")

    packs = []
    for pack_id, pack in catalog["provider_packs"].items():
        env_vars = pack.get("env_vars", [])
        configured = all(bool(os.environ.get(name)) for name in env_vars)
        packs.append({
            "id": pack_id,
            "label": pack["label"],
            "configured": configured,
            "env_vars": env_vars,
            "unlocks": pack["unlocks"],
            "note": pack["note"],
        })

    manifest = {
        "version": "1.0",
        "generated_at": _now(),
        "composition_runtimes": summary["composition_runtimes"],
        "required": required,
        "optional": optional,
        "missing_required": missing_required,
        "planning_ready": not missing_required,
        "selected_provider_pack": provider_pack,
        "provider_packs": packs,
        "runtime_warnings": summary["runtime_warnings"],
    }
    validate_artifact("capability_manifest", manifest)
    return manifest


def create_project(
    *,
    prompt: str,
    source_url: str | None,
    title: str | None,
    project_id: str | None,
    requested_format: str,
    requested_style: str,
    destination: str,
    aspect: str | None,
    language: str,
    duration_seconds: int | None,
    audience: str,
    budget_usd: float,
    flow: str,
    storyboard: bool,
    provider_pack: str,
    variants: int,
    projects_dir: Path,
) -> dict[str, Any]:
    catalog = load_catalog()
    format_id = choose_format(requested=requested_format, prompt=prompt, source_url=source_url)
    format_config = catalog["formats"][format_id]
    style_id = choose_style(format_id, requested_style)
    style = catalog["styles"][style_id]
    delivery = destination_settings(destination, aspect)
    duration = duration_seconds or int(format_config["default_duration_seconds"])
    resolved_title = title or (source_url or prompt or format_config["label"])
    resolved_id = project_id or slugify(resolved_title)

    manifest = load_pipeline(format_config["pipeline"])
    stage_order = get_stage_order(manifest)
    project_dir = init_project(
        resolved_id,
        title=resolved_title,
        pipeline_type=format_config["pipeline"],
        pipeline_dir=projects_dir,
        style_playbook=style["playbook"],
    )

    consumer_request = {
        "version": "1.0",
        "project_id": resolved_id,
        "created_at": _now(),
        "subject": {"title": resolved_title, "source_url": source_url, "prompt": prompt},
        "intent": {
            "format": format_id,
            "audience": audience,
            "consumer_problem": "to_be_researched",
            "desired_action": "one_clear_cta",
        },
        "delivery": {
            "destination": destination,
            "aspect": delivery["aspect"],
            "width": delivery["width"],
            "height": delivery["height"],
            "fps": delivery["fps"],
            "language": language,
            "duration_seconds": duration,
        },
        "creative": {
            "style_id": style_id,
            "consumer_viewpoint": True,
            "hook_policy": "explicit_pain_by_three_seconds",
            "proof_policy": "visible_first_party_or_labeled_evidence",
            "cta_policy": "one_final_action",
            "rules": style["rules"],
        },
        "execution": {
            "flow": flow,
            "storyboard": storyboard,
            "preview_first": True,
            "budget_usd": budget_usd,
            "provider_policy": "explicit_choice_no_silent_fallback",
            "provider_pack": provider_pack,
            "variants": variants,
        },
    }
    validate_artifact("consumer_request", consumer_request)

    capabilities = build_capability_manifest(
        format_config["required_capabilities"],
        format_config["optional_capabilities"],
        provider_pack,
    )
    run_plan = {
        "version": "1.0",
        "project_id": resolved_id,
        "created_at": _now(),
        "pipeline": format_config["pipeline"],
        "format": format_id,
        "style": {
            "id": style_id,
            "playbook": style["playbook"],
            "runtime_preference": style["runtime_preference"],
            "shotcraft_categories": style["shotcraft_categories"],
        },
        "stage_order": stage_order,
        "next_stage": stage_order[0],
        "status": "ready" if capabilities["planning_ready"] else "needs_setup",
        "preview": {
            "required_before_batch": True,
            "max_duration_seconds": min(15, duration),
            "max_variants": 1,
            "approval_required_before_paid_batch": True,
        },
        "cost_policy": {
            "planning_cost_usd": 0.0,
            "budget_ceiling_usd": budget_usd,
            "media_estimate_status": "pending_provider_and_asset_plan",
            "first_paid_use_requires_approval": True,
        },
        "resume": {
            "policy": "failed_or_stale_only",
            "input_hash": _stable_hash(consumer_request),
            "preserve_originals": True,
        },
        "quality_gates": [
            "script_qa_report",
            "proof_plan",
            "creative_qa_report",
            "technical_decode",
        ],
    }
    validate_artifact("run_plan", run_plan)

    artifacts_dir = project_dir / "artifacts"
    for name, artifact in (
        ("consumer_request", consumer_request),
        ("capability_manifest", capabilities),
        ("run_plan", run_plan),
    ):
        with open(artifacts_dir / f"{name}.json", "w", encoding="utf-8") as handle:
            json.dump(artifact, handle, indent=2, ensure_ascii=False)

    qa_template = {
        "version": "1.0",
        "project_id": resolved_id,
        "evaluated_at": None,
        "checks": {
            name: {"score": 0.0, "passes": False, "evidence": "pending review"}
            for name in (
                "hook_pain", "consumer_viewpoint", "single_claim", "proof_visible",
                "visual_copy_match", "pacing", "brand_continuity", "cta", "technical_decode",
            )
        },
        "overall_score": 0.0,
        "overall_status": "pending",
        "blocking_issues": ["final render has not been reviewed"],
    }
    with open(artifacts_dir / "creative_qa_report.json", "w", encoding="utf-8") as handle:
        json.dump(qa_template, handle, indent=2)

    task_path = project_dir / "CODEX_TASK.md"
    task_path.write_text(_task_markdown(consumer_request, run_plan, capabilities), encoding="utf-8")

    marker_path = project_dir / "project.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker.update({
        "consumer_format": format_id,
        "consumer_style": style_id,
        "source_url": source_url,
        "language": language,
        "destination": destination,
        "aspect": delivery["aspect"],
        "run_plan": "artifacts/run_plan.json",
    })
    marker_path.write_text(json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "project_id": resolved_id,
        "project_dir": str(project_dir),
        "pipeline": format_config["pipeline"],
        "format": format_id,
        "style": style_id,
        "status": run_plan["status"],
        "next_stage": run_plan["next_stage"],
        "missing_required": capabilities["missing_required"],
        "task_file": str(task_path),
    }


def resume_project(project_dir: Path) -> dict[str, Any]:
    state = load_board_state(project_dir)
    active = next(
        (stage for stage in state["stages"] if stage["status"] in {"in_progress", "awaiting_human"}),
        None,
    )
    pending = next((stage for stage in state["stages"] if stage["status"] == "pending"), None)
    next_stage = (active or pending or {"name": None})["name"]
    return {
        "project_id": state["project_id"],
        "pipeline": state["pipeline"]["pipeline_type"],
        "next_stage": next_stage,
        "awaiting_human": bool(active and active["status"] == "awaiting_human"),
        "completed": [stage["name"] for stage in state["stages"] if stage["status"] == "completed"],
        "render_count": len(state["media"]["renders"]),
    }


def _task_markdown(request: dict[str, Any], plan: dict[str, Any], capabilities: dict[str, Any]) -> str:
    subject = request["subject"]
    delivery = request["delivery"]
    return f"""# CodexVideo Production Task

Execute this project with `{plan['pipeline']}`. Read the JSON artifacts in `artifacts/`
before making creative decisions and resume from the first incomplete checkpoint.

## Input

- Product or subject: {subject['title']}
- Source URL: {subject.get('source_url') or 'none'}
- User request: {subject['prompt']}
- Audience: {request['intent']['audience']}
- Delivery: {delivery['duration_seconds']}s, {delivery['aspect']}, {delivery['language']}, {delivery['destination']}
- Consumer style: {plan['style']['id']}

## Non-negotiable Creative Contract

1. Verify product truth before writing claims.
2. Research 20-50 consumer pains and select one audience job.
3. State the explicit consumer pain in spoken copy and the first visual by 3.0 seconds.
4. Keep one core claim, visible proof, and one final CTA.
5. Use the selected style rules and exact Shotcraft recipes where appropriate.
6. Reject random stock, static screenshot slideshows, and decorative motion without proof.
7. Produce a low-cost preview before any paid batch.
8. Never substitute a provider, model, voice, or runtime without recording the choice.
9. Complete both technical QA and `creative_qa_report.json` before delivery.

## Capability State

- Planning ready: {str(capabilities['planning_ready']).lower()}
- Missing required capabilities: {', '.join(capabilities['missing_required']) or 'none'}
- Provider pack: {capabilities['selected_provider_pack']}

## Run Order

{' -> '.join(plan['stage_order'])}
"""
