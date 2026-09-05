"""Contract tests for the renderer-neutral editable timeline tool."""

from __future__ import annotations

import json
from pathlib import Path

from schemas.artifacts import validate_artifact
from tools.editing.editable_timeline import EditableTimeline
from tools.tool_registry import ToolRegistry


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _project(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    project = tmp_path / "projects" / "demo"
    artifacts = project / "artifacts"
    video = project / "assets" / "video" / "hero.mp4"
    voice = project / "assets" / "audio" / "voice.wav"
    music = project / "assets" / "music" / "bed.wav"
    for path, payload in ((video, b"video"), (voice, b"voice"), (music, b"music")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    scene_plan = {
        "version": "1.0",
        "scenes": [
            {
                "id": "scene-1",
                "type": "broll",
                "description": "Consumer opens the product",
                "start_seconds": 0,
                "end_seconds": 5,
                "script_section_id": "script-1",
            }
        ],
    }
    asset_manifest = {
        "version": "1.0",
        "assets": [
            {
                "id": "hero-video",
                "type": "video",
                "path": "assets/video/hero.mp4",
                "source_tool": "screen_recorder",
                "scene_id": "scene-1",
                "duration_seconds": 8,
                "provider": "local",
            },
            {
                "id": "voice-main",
                "type": "narration",
                "path": "assets/audio/voice.wav",
                "source_tool": "tts_selector",
                "scene_id": "scene-1",
                "duration_seconds": 5,
            },
            {
                "id": "music-bed",
                "type": "music",
                "path": "assets/music/bed.wav",
                "source_tool": "music_search",
                "scene_id": "scene-1",
                "duration_seconds": 20,
                "license": "CC0",
            },
        ],
    }
    edit = {
        "version": "1.0",
        "cuts": [
            {
                "id": "scene-1",
                "source": "hero-video",
                "audio_track": 1,
                "in_seconds": 1,
                "out_seconds": 6,
                "speed": 1,
                "layer": "primary",
                "transition_out": "fade",
                "transition_duration": 0.25,
            }
        ],
        "audio": {
            "narration": {
                "segments": [
                    {"asset_id": "voice-main", "start_seconds": 0, "end_seconds": 5}
                ]
            },
            "music": {"asset_id": "music-bed", "volume": 0.18, "ducking": True},
        },
        "renderer_family": "product-reveal",
        "render_runtime": "hyperframes",
        "composition_mode": "atelier",
    }
    return (
        project,
        _write(artifacts / "scene_plan.json", scene_plan),
        _write(artifacts / "asset_manifest.json", asset_manifest),
        _write(artifacts / "edit_decisions.json", edit),
    )


def test_export_builds_portable_valid_project(tmp_path):
    project, scene_path, asset_path, edit_path = _project(tmp_path)
    output = project / "editable"
    result = EditableTimeline().execute(
        {
            "operation": "export",
            "project_dir": str(project),
            "project_id": "demo",
            "title": "Demo Product",
            "scene_plan_path": str(scene_path),
            "asset_manifest_path": str(asset_path),
            "edit_decisions_path": str(edit_path),
            "output_dir": str(output),
        }
    )

    assert result.success is True, result.error
    timeline = result.data["timeline"]
    validate_artifact("editable_timeline", timeline)
    assert timeline["metadata"]["track_count"] == 3
    assert timeline["metadata"]["element_count"] == 3
    assert timeline["settings"]["timebase_ticks_per_second"] == 120000
    assert timeline["settings"]["frame_rate"] == {"numerator": 30, "denominator": 1}
    assert timeline["tracks"][0]["elements"][0]["timeline"]["duration_ticks"] == 600000
    assert (output / "media" / "hero-video.mp4").read_bytes() == b"video"
    assert (project / "artifacts" / "editable_timeline.json").is_file()
    assert (output / "adapters" / "opencut-draft.json").is_file()
    assert (output / "manifest.json").is_file()


def test_apply_undo_and_import_round_trip(tmp_path):
    project, scene_path, asset_path, edit_path = _project(tmp_path)
    output = project / "editable"
    exported = EditableTimeline().execute(
        {
            "operation": "export",
            "project_dir": str(project),
            "scene_plan_path": str(scene_path),
            "asset_manifest_path": str(asset_path),
            "edit_decisions_path": str(edit_path),
            "output_dir": str(output),
        }
    )
    timeline_path = exported.data["timeline_path"]

    changed = EditableTimeline().execute(
        {
            "operation": "apply",
            "timeline_path": timeline_path,
            "commands": [
                {
                    "id": "op-move",
                    "type": "move",
                    "target_id": "scene-1",
                    "payload": {"start_seconds": 0.5},
                    "actor": "human",
                    "created_at": "2026-07-17T00:00:00+00:00",
                },
                {
                    "id": "op-volume",
                    "type": "set_volume",
                    "target_id": "music-1-music-bed",
                    "payload": {"volume": 0.1},
                    "actor": "agent",
                    "created_at": "2026-07-17T00:00:01+00:00",
                },
                {
                    "id": "op-speed",
                    "type": "set_speed",
                    "target_id": "scene-1",
                    "payload": {"speed": 1.25},
                    "actor": "agent",
                    "created_at": "2026-07-17T00:00:02+00:00",
                },
            ],
        }
    )
    assert changed.success is True, changed.error
    assert len(changed.data["timeline"]["operations"]) == 3
    scene = next(
        element
        for track in changed.data["timeline"]["tracks"]
        for element in track["elements"]
        if element["id"] == "scene-1"
    )
    assert scene["timeline"]["duration_seconds"] == 4
    assert scene["timeline"]["duration_ticks"] == 480000

    undone = EditableTimeline().execute({"operation": "undo", "timeline_path": timeline_path})
    assert undone.success is True, undone.error
    scene = next(
        element
        for track in undone.data["timeline"]["tracks"]
        for element in track["elements"]
        if element["id"] == "scene-1"
    )
    assert scene["timeline"]["speed"] == 1
    assert scene["timeline"]["duration_seconds"] == 5
    assert undone.data["timeline"]["operations"][-1]["status"] == "undone"

    imported = EditableTimeline().execute(
        {
            "operation": "import",
            "timeline_path": timeline_path,
            "output_path": str(project / "artifacts" / "edit_decisions.roundtrip.json"),
        }
    )
    assert imported.success is True, imported.error
    validate_artifact("edit_decisions", imported.data["edit_decisions"])
    assert imported.data["edit_decisions"]["render_runtime"] == "hyperframes"
    assert imported.data["edit_decisions"]["metadata"]["operation_count"] == 3


def test_registry_discovers_editable_timeline():
    registry = ToolRegistry()
    registry.discover()
    tool = registry.get("editable_timeline")
    assert tool is not None
    assert tool.capability == "project_interchange"
