"""Contracts for the CodexVideo consumer front door."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from codexvideo.catalog import choose_format, choose_style, load_catalog
from codexvideo.project import create_project, resume_project
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.analysis.creative_qa import CreativeQA
from tools.tool_registry import ToolRegistry
from styles.playbook_loader import load_playbook
from lib.render_binding import bind_render


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
    assert choose_format(
        requested="auto", prompt="", source_url=None, has_source_media=True
    ) == "clip"
    assert choose_style("product-promo", "auto") == "cinematic-saas"
    assert load_playbook("clean-professional")["identity"]["name"] == "Clean Professional"
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
    assert result["status"] == "planning_ready"
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
    assert {
        "consumer_request",
        "capability_manifest",
        "run_plan",
        "creative_qa_report",
        "source_ingest_manifest",
    }.issubset(ARTIFACT_NAMES)
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("creative_qa") is not None


def test_creative_qa_fails_critical_checks_and_passes_reviewed_report(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.analysis.creative_qa.verify_playable_video", lambda _: "unit decode fixture")
    video = tmp_path / "unit-video.mp4"
    video.write_bytes(b"unit fixture; decoder tested separately")
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
        "render_binding": bind_render(video, tmp_path),
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


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg not installed")
def test_create_with_media_routes_to_clip_and_prepares_source(tmp_path: Path):
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=24:duration=0.8",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000:duration=0.8",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
    )

    result = create_project(
        prompt="",
        source_url=None,
        title="Prepared source",
        project_id="prepared-source",
        requested_format="auto",
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
        projects_dir=tmp_path / "projects",
        source_media_paths=[source],
    )

    project = Path(result["project_dir"])
    assert result["format"] == "clip"
    assert result["status"] == "planning_ready"
    assert result["source_ingest"][0]["status"] == "ready"
    for name in ("source_media_review", "source_ingest_manifest"):
        artifact = json.loads(
            (project / "artifacts" / f"{name}.json").read_text(encoding="utf-8")
        )
        validate_artifact(name, artifact)
    request = json.loads(
        (project / "artifacts" / "consumer_request.json").read_text(encoding="utf-8")
    )
    assert request["subject"]["source_media"] == [str(source)]
    run_plan = json.loads(
        (project / "artifacts" / "run_plan.json").read_text(encoding="utf-8")
    )
    assert "cut_qa_report" in run_plan["quality_gates"]


def test_image_only_source_stays_on_generated_route_without_cut_gate(tmp_path: Path):
    image = tmp_path / "reference.png"
    Image.new("RGB", (800, 600), "white").save(image)
    result = create_project(
        prompt="",
        source_url=None,
        title="Reference image",
        project_id="reference-image",
        requested_format="auto",
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
        projects_dir=tmp_path / "projects",
        source_media_paths=[image],
    )

    run_plan = json.loads(
        (Path(result["project_dir"]) / "artifacts" / "run_plan.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["format"] == "faceless"
    assert result["source_ingest"] == []
    assert "cut_qa_report" not in run_plan["quality_gates"]


def test_unsupported_source_media_is_rejected_before_project_creation(tmp_path: Path):
    source = tmp_path / "notes.txt"
    source.write_text("not media", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported source media format"):
        create_project(
            prompt="",
            source_url=None,
            title="Unsupported",
            project_id="unsupported",
            requested_format="auto",
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
            projects_dir=tmp_path / "projects",
            source_media_paths=[source],
        )
