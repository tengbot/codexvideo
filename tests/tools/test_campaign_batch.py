"""Contract and local-media tests for modular campaign batch production."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from schemas.artifacts import validate_artifact
from tools.editing.campaign_batch import CampaignBatch
from tools.subtitle.subtitle_gen import SubtitleGen
from tools.tool_registry import ToolRegistry


def _write_json(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _write_srt(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"1\n00:00:00,050 --> 00:00:00,300\n{text}\n",
        encoding="utf-8",
    )
    return path


def _media_clip(path: Path, color: str, frequency: int) -> Path:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required for campaign batch media tests")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=320x180:r=30:d=0.4",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=0.4",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
    )
    return path


def _campaign(project: Path, *, mode: str = "explicit") -> tuple[Path, dict]:
    modules = [
        {
            "id": "hook-a",
            "role": "hook",
            "source_path": "assets/hook-a.mp4",
            "captions_path": "assets/hook-a.srt",
        },
        {
            "id": "hook-b",
            "role": "hook",
            "source_path": "assets/hook-b.mp4",
            "captions_path": "assets/hook-b.srt",
        },
        {
            "id": "body-a",
            "role": "body",
            "source_path": "assets/body-a.mp4",
            "captions_path": "assets/body-a.srt",
        },
        {
            "id": "cta-a",
            "role": "cta",
            "source_path": "assets/cta-a.mp4",
            "captions_path": "assets/cta-a.srt",
        },
    ]
    colors = {
        "hook-a": ("red", 220),
        "hook-b": ("blue", 260),
        "body-a": ("green", 300),
        "cta-a": ("yellow", 340),
    }
    for module in modules:
        color, frequency = colors[module["id"]]
        _media_clip(project / module["source_path"], color, frequency)
        _write_srt(project / module["captions_path"], module["id"])

    variants = (
        [
            {
                "id": "control",
                "selection": {
                    "hook": "hook-a",
                    "body": "body-a",
                    "cta": "cta-a",
                },
            },
            {
                "id": "hook-test",
                "selection": {
                    "hook": "hook-b",
                    "body": "body-a",
                    "cta": "cta-a",
                },
            },
        ]
        if mode == "explicit"
        else []
    )
    campaign = {
        "version": "1.0",
        "campaign_id": "demo-campaign",
        "title": "Demo Campaign",
        "modules": modules,
        "variants": variants,
        "profiles": [
            {
                "id": "landscape",
                "width": 320,
                "height": 180,
                "fps": 30,
                "fit": "contain",
                "background_color": "#000000",
                "crf": 28,
                "preset": "ultrafast",
            },
            {
                "id": "square",
                "width": 180,
                "height": 180,
                "fps": 30,
                "fit": "contain",
                "background_color": "#111111",
                "crf": 28,
                "preset": "ultrafast",
            },
        ],
        "experiment": {
            "mode": mode,
            **(
                {
                    "control_variant_id": "control",
                    "max_changed_dimensions": 1,
                }
                if mode == "explicit"
                else {}
            ),
        },
        "output_dir": "outputs",
    }
    return _write_json(project / "campaign.json", campaign), campaign


def test_campaign_schema_and_registry(tmp_path: Path):
    campaign_path, campaign = _campaign(tmp_path / "project")
    validate_artifact("campaign_plan", campaign)

    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("campaign_batch")
    assert tool is not None
    assert tool.capability == "campaign_post"
    assert tool.get_status().value == "available"

    validated = CampaignBatch().execute(
        {"operation": "validate", "campaign_path": str(campaign_path)}
    )
    assert validated.success is True, validated.error
    assert validated.data["variant_count"] == 2
    assert validated.data["delivery_count"] == 4


def test_full_factorial_materializes_all_combinations(tmp_path: Path):
    project = tmp_path / "project"
    campaign_path, campaign = _campaign(project, mode="full_factorial")
    body_b = {
        "id": "body-b",
        "role": "body",
        "source_path": "assets/body-b.mp4",
    }
    cta_b = {
        "id": "cta-b",
        "role": "cta",
        "source_path": "assets/cta-b.mp4",
    }
    _media_clip(project / body_b["source_path"], "purple", 380)
    _media_clip(project / cta_b["source_path"], "white", 420)
    campaign["modules"].extend([body_b, cta_b])
    campaign["profiles"] = [campaign["profiles"][0]]
    _write_json(campaign_path, campaign)

    planned = CampaignBatch().execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is True, planned.error
    run = planned.data["batch_run"]
    validate_artifact("batch_run", run)
    assert run["summary"] == {
        "total": 8,
        "planned": 8,
        "running": 0,
        "qa_passed": 0,
        "failed": 0,
    }


def test_controlled_experiment_rejects_three_changed_dimensions(tmp_path: Path):
    project = tmp_path / "project"
    campaign_path, campaign = _campaign(project)
    body_b = {
        "id": "body-b",
        "role": "body",
        "source_path": "assets/body-b.mp4",
    }
    cta_b = {
        "id": "cta-b",
        "role": "cta",
        "source_path": "assets/cta-b.mp4",
    }
    _media_clip(project / body_b["source_path"], "purple", 380)
    _media_clip(project / cta_b["source_path"], "white", 420)
    campaign["modules"].extend([body_b, cta_b])
    campaign["variants"].append(
        {
            "id": "invalid-three-way-change",
            "selection": {
                "hook": "hook-b",
                "body": "body-b",
                "cta": "cta-b",
            },
        }
    )
    campaign["experiment"]["max_changed_dimensions"] = 2
    _write_json(campaign_path, campaign)

    planned = CampaignBatch().execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is False
    assert "changes 3 dimensions" in planned.error


def test_render_resume_and_subtitle_offsets(tmp_path: Path):
    project = tmp_path / "project"
    campaign_path, _ = _campaign(project)
    tool = CampaignBatch()
    planned = tool.execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is True, planned.error

    rendered = tool.execute(
        {"operation": "run", "run_path": planned.data["run_path"]}
    )
    assert rendered.success is True, rendered.error
    assert rendered.data["rendered_jobs"] == 4
    assert rendered.data["failed_jobs"] == 0
    assert rendered.data["batch_run"]["summary"]["qa_passed"] == 4

    for job in rendered.data["batch_run"]["jobs"]:
        output = Path(job["output_path"])
        assert output.is_file()
        assert job["qa"]["passed"] is True
        assert job["qa"]["decode_clean"] is True
        assert job["qa"]["faststart"] is True

    combined = (
        project
        / "outputs"
        / ".work"
        / "control--landscape.srt"
    ).read_text(encoding="utf-8")
    assert "hook-a" in combined
    assert "body-a" in combined
    assert "cta-a" in combined
    assert "00:00:00,450 --> 00:00:00,700" in combined
    assert "00:00:00,850 --> 00:00:01,100" in combined

    attempts_before = {
        job["id"]: job["attempts"] for job in rendered.data["batch_run"]["jobs"]
    }
    resumed = CampaignBatch().execute(
        {"operation": "resume", "run_path": planned.data["run_path"]}
    )
    assert resumed.success is True, resumed.error
    assert resumed.data["rendered_jobs"] == 0
    assert resumed.data["cached_jobs"] == 4
    assert {
        job["id"]: job["attempts"] for job in resumed.data["batch_run"]["jobs"]
    } == attempts_before


def test_reflow_requires_profile_specific_module_sources(tmp_path: Path):
    project = tmp_path / "project"
    campaign_path, campaign = _campaign(project)
    campaign["profiles"] = [
        {
            "id": "portrait-reflow",
            "width": 180,
            "height": 320,
            "fps": 30,
            "fit": "reflow",
        }
    ]
    _write_json(campaign_path, campaign)

    planned = CampaignBatch().execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is False
    assert "requires reflow source" in planned.error


def test_source_change_requires_replan(tmp_path: Path):
    project = tmp_path / "project"
    campaign_path, campaign = _campaign(project)
    campaign["variants"] = [campaign["variants"][0]]
    campaign["profiles"] = [campaign["profiles"][0]]
    _write_json(campaign_path, campaign)
    planned = CampaignBatch().execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is True, planned.error

    _media_clip(project / "assets/hook-a.mp4", "black", 500)
    run = CampaignBatch().execute(
        {"operation": "run", "run_path": planned.data["run_path"]}
    )
    assert run.success is False
    assert "Inputs changed for job" in run.error
    assert "operation=plan again" in run.error

    replanned = CampaignBatch().execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert replanned.success is True, replanned.error
    assert replanned.data["batch_run"]["summary"]["planned"] == 1


def test_failed_job_resumes_without_rebuilding_passed_jobs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    project = tmp_path / "project"
    campaign_path, campaign = _campaign(project)
    campaign["variants"] = [campaign["variants"][0]]
    campaign["profiles"] = [campaign["profiles"][0]]
    _write_json(campaign_path, campaign)
    tool = CampaignBatch()
    planned = tool.execute(
        {"operation": "plan", "campaign_path": str(campaign_path)}
    )
    assert planned.success is True, planned.error

    original_render = tool._render_job
    attempts = {"count": 0}

    def fail_once(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("transient encoder failure")
        return original_render(**kwargs)

    monkeypatch.setattr(tool, "_render_job", fail_once)
    failed = tool.execute(
        {"operation": "run", "run_path": planned.data["run_path"]}
    )
    assert failed.success is False
    assert failed.data["batch_run"]["summary"]["failed"] == 1
    assert failed.data["batch_run"]["jobs"][0]["attempts"] == 1

    resumed = tool.execute(
        {"operation": "resume", "run_path": planned.data["run_path"]}
    )
    assert resumed.success is True, resumed.error
    assert resumed.data["batch_run"]["summary"]["qa_passed"] == 1
    assert resumed.data["batch_run"]["jobs"][0]["attempts"] == 2


def test_phrase_corrections_preserve_timing_and_fix_brand_sequence(tmp_path: Path):
    segments = [
        {
            "start": 0,
            "end": 2,
            "text": "Video chat. M-compares",
            "words": [
                {"word": " Video", "start": 0.0, "end": 0.3},
                {"word": " chat.", "start": 0.3, "end": 0.6},
                {"word": " M", "start": 1.0, "end": 1.1},
                {"word": "-compares", "start": 1.1, "end": 2.0},
            ],
        }
    ]
    output = tmp_path / "brand.srt"
    result = SubtitleGen().execute(
        {
            "segments": segments,
            "format": "srt",
            "output_path": str(output),
            "phrase_corrections": {
                "video chat m compares": "VideoChat.im compares"
            },
        }
    )
    assert result.success is True, result.error
    content = output.read_text(encoding="utf-8")
    assert "VideoChat.im compares" in content
    assert "00:00:00,000 --> 00:00:02,000" in content
