"""Contracts for the CodexVideo consumer front door."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codexvideo.catalog import choose_format, choose_style, load_catalog
from codexvideo.project import create_project, resume_project
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.analysis.creative_qa import CreativeQA
from tools.tool_registry import ToolRegistry


def _create(tmp_path: Path, *, prompt: str, format_id: str, project_id: str) -> dict:
    return create_project(
        prompt=prompt,
        source_url="https://example.com" if format_id == "product-promo" else None,
        title=project_id,
        project_id=project_id,
        requested_format=format_id,
        requested_style="auto",
        destination="tiktok",
        aspect=None,
        language="en",
        duration_seconds=24,
        audience="English-speaking consumers",
        budget_usd=3.0,
        flow="automation",
        storyboard=False,
        provider_pack="auto",
        variants=1,
        projects_dir=tmp_path,
    )


def test_catalog_routes_plain_language_formats_and_styles():
    catalog = load_catalog()
    assert set(catalog["formats"]) == {
        "product-promo", "faceless", "ai-podcast", "avatar", "screen-demo", "clip"
    }
    assert choose_format(requested="auto", prompt="two-host podcast", source_url=None) == "ai-podcast"
    assert choose_format(requested="auto", prompt="", source_url="https://example.com") == "product-promo"
    assert choose_style("product-promo", "auto") == "cinematic-saas"
    with pytest.raises(ValueError):
        choose_style("clip", "cinematic-saas")


@pytest.mark.parametrize(
    ("format_id", "pipeline", "prompt"),
    [
        ("product-promo", "product-promo-factory", "Sell this product from the consumer viewpoint"),
        ("faceless", "faceless-narrative", "Create a faceless narration"),
        ("ai-podcast", "ai-dialogue-podcast", "Create a two-host conversation"),
    ],
)
def test_golden_flows_create_resumable_projects(tmp_path, format_id, pipeline, prompt):
    result = _create(tmp_path, prompt=prompt, format_id=format_id, project_id=f"golden-{format_id}")
    project = Path(result["project_dir"])
    assert result["pipeline"] == pipeline
    assert result["status"] == "ready"
    assert (project / "CODEX_TASK.md").is_file()
    assert "explicit consumer pain" in (project / "CODEX_TASK.md").read_text(encoding="utf-8")

    for artifact_name in ("consumer_request", "capability_manifest", "run_plan", "creative_qa_report"):
        artifact = json.loads((project / "artifacts" / f"{artifact_name}.json").read_text(encoding="utf-8"))
        validate_artifact(artifact_name, artifact)

    run_plan = json.loads((project / "artifacts/run_plan.json").read_text(encoding="utf-8"))
    assert run_plan["preview"]["required_before_batch"] is True
    assert run_plan["cost_policy"]["media_estimate_status"] == "pending_provider_and_asset_plan"
    assert resume_project(project)["next_stage"] == run_plan["stage_order"][0]


def test_front_door_artifacts_and_creative_qa_tool_are_registered():
    assert {"consumer_request", "capability_manifest", "run_plan", "creative_qa_report"}.issubset(ARTIFACT_NAMES)
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("creative_qa") is not None


def test_creative_qa_fails_critical_checks_and_passes_reviewed_report(tmp_path):
    report_path = tmp_path / "creative_qa_report.json"
    checks = {
        name: {"score": 0.9, "passes": True, "evidence": f"verified {name}"}
        for name in (
            "hook_pain", "consumer_viewpoint", "single_claim", "proof_visible",
            "visual_copy_match", "pacing", "brand_continuity", "cta", "technical_decode",
        )
    }
    report = {
        "version": "1.0",
        "project_id": "qa-project",
        "evaluated_at": None,
        "checks": checks,
        "overall_score": 0.0,
        "overall_status": "pending",
        "blocking_issues": [],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    passed = CreativeQA().execute({"report_path": str(report_path), "output_path": str(report_path)})
    assert passed.success is True
    assert passed.data["creative_qa_report"]["overall_status"] == "pass"

    report["checks"]["hook_pain"] = {"score": 0.2, "passes": False, "evidence": "pain is hidden"}
    report_path.write_text(json.dumps(report), encoding="utf-8")
    failed = CreativeQA().execute({"report_path": str(report_path)})
    assert failed.success is False
    assert "hook_pain" in failed.data["creative_qa_report"]["blocking_issues"]
