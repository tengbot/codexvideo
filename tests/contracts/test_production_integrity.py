import json
from pathlib import Path

import pytest

from lib.checkpoint import CheckpointValidationError, init_project, write_checkpoint
from lib.production_integrity import _snapshot, verify_stage
from lib.render_binding import bind_render, validate_render_binding
from tests.contracts.test_phase0_contracts import sample_artifact
from tools.analysis.creative_qa import CreativeQA
from tools.editing.raw_footage.qa import CutBoundaryQA
from tools.base_tool import ToolResult
from tools.publishers.export_bundle import ExportBundle


def _report(project):
    path = project / "artifacts/creative_qa_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "version": "1.0", "project_id": "fixture", "evaluated_at": None,
        "overall_status": "pass", "overall_score": 1.0, "blocking_issues": [],
        "checks": {name: {"score": 1.0, "passes": True, "evidence": "unit review"} for name in (
            "hook_pain", "consumer_viewpoint", "single_claim", "proof_visible", "visual_copy_match",
            "pacing", "brand_continuity", "cta", "technical_decode",
        )},
    }
    path.write_text(json.dumps(report))
    return path, report


def test_unbound_perfect_scores_cannot_pass(tmp_path):
    path, _ = _report(tmp_path)
    result = CreativeQA().execute({"report_path": str(path)})
    assert not result.success and "unbound" in result.error


def test_new_binding_resets_previous_approval(tmp_path, monkeypatch):
    path, _ = _report(tmp_path)
    video = tmp_path / "fixture.mp4"
    video.write_bytes(b"test")
    monkeypatch.setattr("tools.analysis.creative_qa.verify_playable_video", lambda _: "unit decode fixture")
    result = CreativeQA().execute({"operation": "prepare", "report_path": str(path), "video_path": str(video)})
    assert result.success
    report = result.data["creative_qa_report"]
    assert report["overall_status"] == "pending"
    assert not any(check["passes"] for check in report["checks"].values())


def test_changed_video_or_script_invalidates_review(tmp_path):
    video = tmp_path / "fixture.mp4"
    video.write_bytes(b"video v1")
    script = tmp_path / "artifacts/script.json"
    script.parent.mkdir()
    script.write_text('{"text":"first"}')
    binding = bind_render(video, tmp_path)
    validate_render_binding(binding, video)
    script.write_text('{"text":"changed"}')
    with pytest.raises(ValueError, match="stale"):
        validate_render_binding(binding)
    binding = bind_render(video, tmp_path)
    video.write_bytes(b"video v2")
    with pytest.raises(ValueError, match="match"):
        validate_render_binding(binding, video)


def test_consumer_export_cannot_omit_review_gate(tmp_path):
    (tmp_path / "project.json").write_text('{}')
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/consumer_request.json").write_text('{}')
    video = tmp_path / "fixture.mp4"
    video.write_bytes(b"not reviewed")
    result = ExportBundle().execute({"video_path": str(video), "title": "Fixture", "export_dir": str(tmp_path / "out")})
    assert not result.success and "Delivery gate" in result.error
    assert not (tmp_path / "out").exists()
    result = ExportBundle().execute({"video_path": str(video), "title": "Fixture", "project_dir": str(tmp_path / "unrelated")})
    assert not result.success and "does not own" in result.error


def test_decision_log_allows_append_but_not_approval_rewrite(tmp_path):
    path = tmp_path / "artifacts/decision_log.json"
    path.parent.mkdir()
    original = {"version": "1.0", "project_id": "unit", "decisions": [{"decision_id": "one", "user_approved": True}]}
    checkpoint = {"stage": "proposal", "metadata": {"artifact_hashes": {"decision_log": _snapshot("decision_log", original)}}}
    appended = {**original, "decisions": [*original["decisions"], {"decision_id": "two"}]}
    path.write_text(json.dumps(appended))
    verify_stage(tmp_path, checkpoint)
    appended["decisions"][0]["user_approved"] = False
    path.write_text(json.dumps(appended))
    with pytest.raises(ValueError, match="stale"):
        verify_stage(tmp_path, checkpoint)


def test_cut_qa_attempt_slots_are_immutable_and_bounded(tmp_path, monkeypatch):
    video = tmp_path / "fixture.mp4"
    video.write_bytes(b"one render")
    tool = CutBoundaryQA()
    slots = []
    def inspect(inputs):
        slots.append(inputs["_review_slot"])
        return ToolResult(success=True, data={"attempt": inputs["attempt"]})
    monkeypatch.setattr(tool, "_inspect", inspect)
    inputs = {"video_path": str(video), "project_dir": str(tmp_path)}
    assert tool.execute(inputs).data["attempt"] == 1
    repeated = tool.execute({**inputs, "attempt": 1})
    assert not repeated.success and "immutable" in repeated.error
    assert tool.execute(inputs).data["attempt"] == 2
    assert tool.execute(inputs).data["attempt"] == 3
    assert not tool.execute(inputs).success
    assert len(set(slots)) == 3
    assert all((Path(slot) / "started.json").is_file() for slot in slots)


def test_strict_checkpoint_detects_changed_inputs_and_blocks_next_stage(tmp_path):
    project = init_project("run", title="Fixture", pipeline_type="framework-smoke", pipeline_dir=tmp_path)
    marker_path = project / "project.json"
    marker = json.loads(marker_path.read_text())
    marker["integrity_version"] = 1
    marker_path.write_text(json.dumps(marker))
    checkpoint = write_checkpoint(tmp_path, "run", "research", "completed", {
        "research_brief": sample_artifact("research_brief"),
    }, human_approved=True)
    value = json.loads(checkpoint.read_text())
    verify_stage(project, value)
    artifact = project / "artifacts/research_brief.json"
    changed = json.loads(artifact.read_text())
    changed["topic"] = "changed evidence"
    artifact.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="stale"):
        verify_stage(project, value)
    with pytest.raises(CheckpointValidationError, match="PREREQUISITE"):
        write_checkpoint(tmp_path, "run", "script", "completed", {
            "script": sample_artifact("script"),
        }, human_approved=True)
