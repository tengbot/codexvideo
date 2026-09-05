"""Editable timeline interchange for agent and human post-production.

This module keeps OpenMontage's renderer contracts intact while exposing a
neutral, track-based project that can round-trip through future editor adapters.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
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


class EditableTimeline(BaseTool):
    name = "editable_timeline"
    version = "1.0.0"
    tier = ToolTier.CORE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "project_interchange"
    provider = "openmontage"
    capabilities = [
        "editable_timeline_export",
        "editable_timeline_import",
        "timeline_commands",
        "timeline_undo",
    ]
    best_for = [
        "Exporting an OpenMontage cut as a portable multi-track edit project",
        "Applying auditable human or agent edit commands",
        "Round-tripping timing, trim, text, transform, and audio decisions",
        "Preparing for OpenCut, OTIO, or NLE adapters without changing renderers",
    ]
    not_good_for = [
        "Rendering the final video",
        "Replacing HyperFrames or Remotion compositions",
        "Direct OpenCut import before OpenCut ships a stable Editor API",
    ]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["export", "import", "apply", "undo", "validate"],
            },
            "edit_decisions_path": {"type": "string"},
            "scene_plan_path": {"type": "string"},
            "asset_manifest_path": {"type": "string"},
            "timeline_path": {"type": "string"},
            "artifact_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "output_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "project_id": {"type": "string"},
            "title": {"type": "string"},
            "portable": {"type": "boolean"},
            "settings": {"type": "object"},
            "commands": {"type": "array", "items": {"type": "object"}},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "timeline": {"type": "object"},
            "timeline_path": {"type": "string"},
            "artifact_path": {"type": "string"},
            "edit_decisions": {"type": "object"},
            "edit_decisions_path": {"type": "string"},
            "files_written": {"type": "array", "items": {"type": "string"}},
        },
    }
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=256, network_required=False
    )
    side_effects = ["writes an editable project or round-tripped edit decisions"]
    user_visible_verification = [
        "Open timeline.json and confirm tracks, clips, audio, and provenance are present",
        "Apply a timing command, undo it, and confirm the original timeline is restored",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            operation = inputs["operation"]
            if operation == "export":
                return self._export(inputs)
            if operation == "import":
                return self._import(inputs)
            if operation == "apply":
                return self._apply(inputs)
            if operation == "undo":
                return self._undo(inputs)
            if operation == "validate":
                timeline_path = self._required_path(inputs, "timeline_path")
                timeline = self._read_json(timeline_path)
                validate_artifact("editable_timeline", timeline)
                return ToolResult(
                    success=True,
                    data={"timeline": timeline, "timeline_path": str(timeline_path)},
                )
            return ToolResult(success=False, error=f"Unsupported operation: {operation}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:  # schema validators expose several exception types
            return ToolResult(success=False, error=f"editable timeline failed: {exc}")

    def _export(self, inputs: dict[str, Any]) -> ToolResult:
        edit_path = self._required_path(inputs, "edit_decisions_path")
        edit = self._read_json(edit_path)
        validate_artifact("edit_decisions", edit)

        scene_path = self._optional_path(inputs.get("scene_plan_path"))
        asset_path = self._optional_path(inputs.get("asset_manifest_path"))
        scene_plan = self._read_json(scene_path) if scene_path else {"version": "1.0", "scenes": []}
        assets = self._read_json(asset_path) if asset_path else {"version": "1.0", "assets": []}
        if scene_path:
            validate_artifact("scene_plan", scene_plan)
        if asset_path:
            validate_artifact("asset_manifest", assets)

        output_dir = Path(inputs.get("output_dir") or edit_path.parent.parent / "editable")
        output_dir.mkdir(parents=True, exist_ok=True)
        project_dir = Path(inputs.get("project_dir") or edit_path.parent.parent)
        input_settings = inputs.get("settings") or {}
        settings = {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "timebase_ticks_per_second": 120000,
            "background_color": "#000000",
            **input_settings,
        }
        settings["timebase_ticks_per_second"] = 120000
        if "frame_rate" not in input_settings:
            settings["frame_rate"] = self._rational_frame_rate(settings["fps"])
        project_id = inputs.get("project_id") or project_dir.name or "openmontage-project"
        title = inputs.get("title") or project_id.replace("-", " ").title()

        timeline = self._build_timeline(
            project_id=project_id,
            title=title,
            settings=settings,
            edit=edit,
            scene_plan=scene_plan,
            asset_manifest=assets,
            source_artifacts={
                "edit_decisions": str(edit_path),
                **({"scene_plan": str(scene_path)} if scene_path else {}),
                **({"asset_manifest": str(asset_path)} if asset_path else {}),
            },
        )

        files_written: list[str] = []
        if inputs.get("portable", True):
            self._stage_media(timeline, assets, project_dir, output_dir, files_written)

        timeline_path = output_dir / "timeline.json"
        validate_artifact("editable_timeline", timeline)
        self._write_json(timeline_path, timeline)
        files_written.append(str(timeline_path))

        artifact_path = Path(
            inputs.get("artifact_path")
            or project_dir / "artifacts" / "editable_timeline.json"
        )
        if artifact_path.resolve() != timeline_path.resolve():
            self._write_json(artifact_path, timeline)
            files_written.append(str(artifact_path))

        adapter_path = output_dir / "adapters" / "opencut-draft.json"
        adapter_path.parent.mkdir(parents=True, exist_ok=True)
        adapter = self._opencut_draft(timeline)
        self._write_json(adapter_path, adapter)
        files_written.append(str(adapter_path))

        readme_path = output_dir / "README.md"
        readme_path.write_text(self._pack_readme(), encoding="utf-8")
        files_written.append(str(readme_path))

        manifest_path = output_dir / "manifest.json"
        manifest = self._bundle_manifest(output_dir)
        self._write_json(manifest_path, manifest)
        files_written.append(str(manifest_path))

        return ToolResult(
            success=True,
            data={
                "timeline": timeline,
                "timeline_path": str(timeline_path),
                "artifact_path": str(artifact_path),
                "files_written": files_written,
            },
            artifacts=[str(artifact_path), str(timeline_path)],
        )

    def _import(self, inputs: dict[str, Any]) -> ToolResult:
        timeline_path = self._required_path(inputs, "timeline_path")
        timeline = self._read_json(timeline_path)
        validate_artifact("editable_timeline", timeline)
        edit = self._timeline_to_edit_decisions(timeline, timeline_path)
        validate_artifact("edit_decisions", edit)
        output_path = Path(
            inputs.get("output_path") or timeline_path.parent / "edit_decisions.roundtrip.json"
        )
        self._write_json(output_path, edit)
        return ToolResult(
            success=True,
            data={
                "edit_decisions": edit,
                "edit_decisions_path": str(output_path),
                "files_written": [str(output_path)],
            },
            artifacts=[str(output_path)],
        )

    def _apply(self, inputs: dict[str, Any]) -> ToolResult:
        timeline_path = self._required_path(inputs, "timeline_path")
        timeline = self._read_json(timeline_path)
        validate_artifact("editable_timeline", timeline)
        commands = inputs.get("commands") or []
        if not commands:
            return ToolResult(success=False, error="commands must contain at least one edit")
        for command in commands:
            self._apply_command(timeline, command, record=True)
        validate_artifact("editable_timeline", timeline)
        output_path = Path(inputs.get("output_path") or timeline_path)
        self._write_json(output_path, timeline)
        return ToolResult(
            success=True,
            data={
                "timeline": timeline,
                "timeline_path": str(output_path),
                "files_written": [str(output_path)],
            },
            artifacts=[str(output_path)],
        )

    def _undo(self, inputs: dict[str, Any]) -> ToolResult:
        timeline_path = self._required_path(inputs, "timeline_path")
        timeline = self._read_json(timeline_path)
        validate_artifact("editable_timeline", timeline)
        operation = next(
            (op for op in reversed(timeline["operations"]) if op["status"] == "applied"),
            None,
        )
        if operation is None:
            return ToolResult(success=False, error="No applied operation is available to undo")
        inverse_command = {
            "type": operation["type"],
            "target_id": operation["target_id"],
            "payload": deepcopy(operation["inverse"]),
            "actor": operation["actor"],
        }
        self._apply_command(timeline, inverse_command, record=False)
        operation["status"] = "undone"
        validate_artifact("editable_timeline", timeline)
        output_path = Path(inputs.get("output_path") or timeline_path)
        self._write_json(output_path, timeline)
        return ToolResult(
            success=True,
            data={
                "timeline": timeline,
                "timeline_path": str(output_path),
                "undone_operation_id": operation["id"],
                "files_written": [str(output_path)],
            },
            artifacts=[str(output_path)],
        )

    def _build_timeline(
        self,
        *,
        project_id: str,
        title: str,
        settings: dict[str, Any],
        edit: dict[str, Any],
        scene_plan: dict[str, Any],
        asset_manifest: dict[str, Any],
        source_artifacts: dict[str, str],
    ) -> dict[str, Any]:
        asset_map = {asset["id"]: asset for asset in asset_manifest.get("assets", [])}
        scene_map = {scene["id"]: scene for scene in scene_plan.get("scenes", [])}
        tracks = [
            self._track("track-video-background", "Background", "video", "background", "main", 0),
            self._track("track-video-primary", "Primary Video", "video", "primary", "main", 1),
            self._track("track-video-overlay", "Overlays", "video", "overlay", "overlay", 2),
            self._track("track-captions", "Captions", "text", "captions", "overlay", 3),
            self._track("track-narration", "Narration", "audio", "narration", "audio", 4),
            self._track("track-sfx", "Sound Effects", "audio", "sfx", "audio", 5),
            self._track("track-music", "Music", "audio", "music", "audio", 6),
        ]
        by_role = {track["role"]: track for track in tracks}

        cursor = 0.0
        for index, cut in enumerate(edit.get("cuts", [])):
            speed = float(cut.get("speed", 1.0) or 1.0)
            trim_start = float(cut["in_seconds"])
            trim_end = float(cut["out_seconds"])
            duration = max(0.0, (trim_end - trim_start) / speed)
            role = cut.get("layer", "primary")
            asset = asset_map.get(cut["source"])
            scene = scene_map.get(cut["id"]) or self._scene_for_index(scene_plan, index)
            element = self._element_from_source(
                element_id=cut["id"],
                name=cut.get("reason") or cut["id"],
                source_value=cut["source"],
                asset=asset,
                start=cursor,
                duration=duration,
                trim_start=trim_start,
                trim_end=trim_end,
                speed=speed,
                scene=scene,
            )
            if cut.get("transform"):
                element["transform"] = self._normalize_transform(cut["transform"])
            element["metadata"] = {
                **({"audio_track": cut["audio_track"]} if "audio_track" in cut else {}),
                "transition_in": cut.get("transition_in"),
                "transition_out": cut.get("transition_out"),
                "transition_duration": cut.get("transition_duration", 0),
                "position_hint": (cut.get("transform") or {}).get("position"),
            }
            by_role.get(role, by_role["primary"])["elements"].append(element)
            overlap = min(float(cut.get("transition_duration", 0) or 0), duration)
            cursor += max(0.0, duration - overlap)

        for index, overlay in enumerate(edit.get("overlays", [])):
            asset_id = overlay["asset_id"]
            asset = asset_map.get(asset_id)
            duration = max(0.0, overlay["end_seconds"] - overlay["start_seconds"])
            element = self._element_from_source(
                element_id=f"overlay-{index + 1}-{asset_id}",
                name=asset_id,
                source_value=asset_id,
                asset=asset,
                start=overlay["start_seconds"],
                duration=duration,
                trim_start=0,
                trim_end=duration,
                speed=1,
                scene=None,
            )
            element["transform"] = {
                **{k: v for k, v in overlay["position"].items() if k in {"x", "y", "width", "height"}},
                "opacity": overlay.get("opacity", 1),
            }
            element["metadata"] = {"animation": overlay.get("animation")}
            by_role["overlay"]["elements"].append(element)

        audio = edit.get("audio", {}) or {}
        for index, segment in enumerate((audio.get("narration") or {}).get("segments", [])):
            self._append_audio_element(
                by_role["narration"], asset_map, segment["asset_id"],
                segment["start_seconds"], segment.get("end_seconds"), index, 1.0,
            )
        for index, sfx in enumerate(audio.get("sfx", [])):
            self._append_audio_element(
                by_role["sfx"], asset_map, sfx.get("asset_id", f"sfx-{index + 1}"),
                sfx.get("start_seconds", 0), None, index, sfx.get("volume", 1.0),
            )
        music = audio.get("music") or edit.get("music")
        if music and music.get("asset_id"):
            self._append_audio_element(
                by_role["music"], asset_map, music["asset_id"], 0, cursor, 0,
                music.get("volume", 1.0),
            )
            by_role["music"]["elements"][0]["metadata"] = {
                "fade_in_seconds": music.get("fade_in_seconds", 0),
                "fade_out_seconds": music.get("fade_out_seconds", 0),
                "ducking": music.get("ducking", True),
            }

        subtitles = edit.get("subtitles") or {}
        if subtitles.get("enabled") and subtitles.get("source"):
            by_role["captions"]["elements"].append(
                {
                    "id": "captions-main",
                    "name": "Captions",
                    "kind": "subtitle",
                    "source": {"path": subtitles["source"], "media_type": "subtitle"},
                    "timeline": {
                        "start_seconds": 0,
                        "duration_seconds": cursor,
                        "trim_start_seconds": 0,
                        "start_ticks": 0,
                        "duration_ticks": self._ticks(cursor),
                        "trim_start_ticks": 0,
                        "speed": 1,
                    },
                    "metadata": {k: v for k, v in subtitles.items() if k != "source"},
                }
            )

        tracks = [track for track in tracks if track["elements"]]
        duration = max(
            (
                element["timeline"]["start_seconds"] + element["timeline"]["duration_seconds"]
                for track in tracks
                for element in track["elements"]
            ),
            default=0,
        )
        return {
            "version": "1.0",
            "project": {"id": project_id, "title": title},
            "settings": settings,
            "tracks": tracks,
            "operations": [],
            "interchange": {
                "format": "openmontage-editable-timeline",
                "render_runtime": edit["render_runtime"],
                **({"renderer_family": edit["renderer_family"]} if edit.get("renderer_family") else {}),
                **({"composition_mode": edit["composition_mode"]} if edit.get("composition_mode") else {}),
                "source_artifacts": source_artifacts,
                "adapters": {
                    "opencut": {
                        "status": "v0.3-concepts-ready",
                        "notes": "Uses OpenCut v0.3 timeline concepts; direct import still waits for a stable Editor API or MCP.",
                    },
                    "hyperframes": {
                        "status": "render-runtime",
                        "notes": "Complex HTML/GSAP scenes remain renderable as compositions or scene proxies.",
                    },
                    "remotion": {
                        "status": "render-runtime",
                        "notes": "React compositions remain renderable without flattening the source project.",
                    },
                },
            },
            "metadata": {
                "duration_seconds": round(duration, 6),
                "track_count": len(tracks),
                "element_count": sum(len(track["elements"]) for track in tracks),
                "source_edit_metadata": edit.get("metadata", {}),
                "editor_features": {
                    "integer_timebase": True,
                    "command_history": True,
                    "independent_scale_axes": True,
                    "speed_with_pitch_policy": True,
                    "masks": True,
                    "bezier_keyframes": True,
                },
            },
        }

    @staticmethod
    def _track(
        track_id: str, name: str, track_type: str, role: str, lane: str, order: int
    ) -> dict[str, Any]:
        return {
            "id": track_id,
            "name": name,
            "type": track_type,
            "role": role,
            "lane": lane,
            "order": order,
            "muted": False,
            "locked": False,
            "elements": [],
        }

    def _element_from_source(
        self,
        *,
        element_id: str,
        name: str,
        source_value: str,
        asset: dict[str, Any] | None,
        start: float,
        duration: float,
        trim_start: float,
        trim_end: float,
        speed: float,
        scene: dict[str, Any] | None,
    ) -> dict[str, Any]:
        kind = self._element_kind(asset, source_value)
        source = {
            "asset_id": asset["id"] if asset else source_value,
            "path": asset.get("path", source_value) if asset else source_value,
            "media_type": asset.get("type", kind) if asset else kind,
        }
        if asset and asset.get("original_url"):
            source["original_url"] = asset["original_url"]
        provenance = {
            **({"scene_id": scene["id"]} if scene else {}),
            **({"script_section_id": scene["script_section_id"]} if scene and scene.get("script_section_id") else {}),
            **({"source_tool": asset["source_tool"]} if asset and asset.get("source_tool") else {}),
            **({"provider": asset["provider"]} if asset and asset.get("provider") else {}),
            **({"model": asset["model"]} if asset and asset.get("model") else {}),
            **({"prompt": asset["prompt"]} if asset and asset.get("prompt") else {}),
            **({"license": asset["license"]} if asset and asset.get("license") else {}),
        }
        return {
            "id": element_id,
            "name": name,
            "kind": kind,
            "source": source,
            "timeline": {
                "start_seconds": round(float(start), 6),
                "duration_seconds": round(float(duration), 6),
                "trim_start_seconds": round(float(trim_start), 6),
                "trim_end_seconds": round(float(trim_end), 6),
                "start_ticks": self._ticks(start),
                "duration_ticks": self._ticks(duration),
                "trim_start_ticks": self._ticks(trim_start),
                "trim_end_ticks": self._ticks(trim_end),
                **(
                    {"source_duration_seconds": asset["duration_seconds"]}
                    if asset and asset.get("duration_seconds") is not None else {}
                ),
                "speed": float(speed),
            },
            **({"provenance": provenance} if provenance else {}),
            "regeneration": {
                "strategy": "preserve_timing" if asset and asset.get("prompt") else "manual_only",
                "status": "available" if asset and asset.get("prompt") else "protected",
                "protected_fields": ["timeline.start_seconds", "timeline.duration_seconds"],
            },
        }

    def _append_audio_element(
        self,
        track: dict[str, Any],
        asset_map: dict[str, dict[str, Any]],
        asset_id: str,
        start: float,
        end: float | None,
        index: int,
        volume: float,
    ) -> None:
        asset = asset_map.get(asset_id)
        duration = (
            max(0.0, float(end) - float(start))
            if end is not None
            else float((asset or {}).get("duration_seconds", 0))
        )
        element = self._element_from_source(
            element_id=f"{track['role']}-{index + 1}-{asset_id}",
            name=asset_id,
            source_value=asset_id,
            asset=asset,
            start=float(start),
            duration=duration,
            trim_start=0,
            trim_end=duration,
            speed=1,
            scene=None,
        )
        element["kind"] = "audio"
        element["audio"] = {
            "volume": float(volume),
            "pan": 0,
            "muted": False,
            "maintain_pitch": True,
        }
        track["elements"].append(element)

    @staticmethod
    def _scene_for_index(scene_plan: dict[str, Any], index: int) -> dict[str, Any] | None:
        scenes = scene_plan.get("scenes", [])
        return scenes[index] if index < len(scenes) else None

    @staticmethod
    def _element_kind(asset: dict[str, Any] | None, source: str) -> str:
        asset_type = (asset or {}).get("type")
        if asset_type in {"video", "animation"}:
            return "video"
        if asset_type in {"audio", "narration", "music", "sfx"}:
            return "audio"
        if asset_type in {"image", "diagram"}:
            return "image"
        suffix = Path(source).suffix.lower()
        if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
            return "video"
        if suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}:
            return "audio"
        if suffix in {".html", ".tsx", ".jsx"}:
            return "composition"
        return "image"

    @staticmethod
    def _normalize_transform(transform: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key in ("scale", "scale_x", "scale_y"):
            if transform.get(key) is not None:
                normalized[key] = transform[key]
        crop = transform.get("crop") or {}
        for key in ("x", "y", "width", "height"):
            if crop.get(key) is not None:
                normalized[key] = crop[key]
        return normalized

    def _stage_media(
        self,
        timeline: dict[str, Any],
        asset_manifest: dict[str, Any],
        project_dir: Path,
        output_dir: Path,
        files_written: list[str],
    ) -> None:
        asset_map = {asset["id"]: asset for asset in asset_manifest.get("assets", [])}
        copied: dict[Path, str] = {}
        media_dir = output_dir / "media"
        for track in timeline["tracks"]:
            for element in track["elements"]:
                source = element.get("source")
                if not source or not source.get("path"):
                    continue
                asset = asset_map.get(source.get("asset_id"))
                resolved = self._resolve_media_path(source["path"], project_dir)
                if not resolved or not resolved.is_file():
                    continue
                if resolved in copied:
                    source["path"] = copied[resolved]
                    continue
                media_dir.mkdir(parents=True, exist_ok=True)
                stem = self._safe_name((asset or {}).get("id") or resolved.stem)
                target = media_dir / f"{stem}{resolved.suffix.lower()}"
                counter = 2
                while target.exists() and target.resolve() != resolved.resolve():
                    target = media_dir / f"{stem}-{counter}{resolved.suffix.lower()}"
                    counter += 1
                if target.resolve() != resolved.resolve():
                    shutil.copy2(resolved, target)
                relative = target.relative_to(output_dir).as_posix()
                copied[resolved] = relative
                source["path"] = relative
                files_written.append(str(target))

    @staticmethod
    def _resolve_media_path(raw: str, project_dir: Path) -> Path | None:
        path = Path(raw).expanduser()
        candidates = [path] if path.is_absolute() else [project_dir / path, Path.cwd() / path]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    def _timeline_to_edit_decisions(
        self, timeline: dict[str, Any], timeline_path: Path
    ) -> dict[str, Any]:
        cuts: list[dict[str, Any]] = []
        overlays: list[dict[str, Any]] = []
        narration: list[dict[str, Any]] = []
        sfx: list[dict[str, Any]] = []
        music: dict[str, Any] | None = None
        subtitles: dict[str, Any] | None = None

        for track in timeline["tracks"]:
            role = track["role"]
            for element in sorted(
                track["elements"], key=lambda item: item["timeline"]["start_seconds"]
            ):
                source = element.get("source") or {}
                source_value = source.get("asset_id") or source.get("path") or source.get("original_url")
                timing = element["timeline"]
                if role in {"primary", "background"}:
                    speed = timing.get("speed", 1)
                    cut: dict[str, Any] = {
                        "id": element["id"],
                        "source": source_value,
                        "in_seconds": timing.get("trim_start_seconds", 0),
                        "out_seconds": timing.get("trim_start_seconds", 0)
                        + timing["duration_seconds"] * speed,
                        "speed": speed,
                        "layer": role,
                    }
                    if element.get("transform"):
                        cut["transform"] = self._edit_transform(element["transform"])
                    metadata = element.get("metadata") or {}
                    for key in ("transition_in", "transition_out", "transition_duration", "audio_track"):
                        if metadata.get(key) is not None:
                            cut[key] = metadata[key]
                    if element.get("name"):
                        cut["reason"] = element["name"]
                    cuts.append(cut)
                elif role == "overlay":
                    transform = element.get("transform") or {}
                    overlays.append(
                        {
                            "asset_id": source_value,
                            "start_seconds": timing["start_seconds"],
                            "end_seconds": timing["start_seconds"] + timing["duration_seconds"],
                            "position": {
                                "x": transform.get("x", 0),
                                "y": transform.get("y", 0),
                                **({"width": transform["width"]} if transform.get("width") is not None else {}),
                                **({"height": transform["height"]} if transform.get("height") is not None else {}),
                            },
                            **({"opacity": transform["opacity"]} if transform.get("opacity") is not None else {}),
                            **(
                                {"animation": element["metadata"]["animation"]}
                                if (element.get("metadata") or {}).get("animation") else {}
                            ),
                        }
                    )
                elif role == "narration":
                    narration.append(
                        {
                            "asset_id": source_value,
                            "start_seconds": timing["start_seconds"],
                            "end_seconds": timing["start_seconds"] + timing["duration_seconds"],
                        }
                    )
                elif role == "sfx":
                    sfx.append(
                        {
                            "asset_id": source_value,
                            "start_seconds": timing["start_seconds"],
                            "volume": (element.get("audio") or {}).get("volume", 1),
                        }
                    )
                elif role == "music":
                    metadata = element.get("metadata") or {}
                    music = {
                        "asset_id": source_value,
                        "volume": (element.get("audio") or {}).get("volume", 1),
                        "fade_in_seconds": metadata.get("fade_in_seconds", 0),
                        "fade_out_seconds": metadata.get("fade_out_seconds", 0),
                        "ducking": metadata.get("ducking", True),
                    }
                elif role == "captions":
                    metadata = element.get("metadata") or {}
                    subtitles = {
                        "enabled": True,
                        "source": source_value,
                        **{k: v for k, v in metadata.items() if k != "enabled"},
                    }

        interchange = timeline["interchange"]
        result: dict[str, Any] = {
            "version": "1.0",
            "cuts": cuts,
            **({"overlays": overlays} if overlays else {}),
            "audio": {
                **({"narration": {"segments": narration}} if narration else {}),
                **({"music": music} if music else {}),
                **({"sfx": sfx} if sfx else {}),
            },
            **({"subtitles": subtitles} if subtitles else {}),
            **(
                {"renderer_family": interchange["renderer_family"]}
                if interchange.get("renderer_family") else {}
            ),
            "render_runtime": interchange["render_runtime"],
            **(
                {"composition_mode": interchange["composition_mode"]}
                if interchange.get("composition_mode") else {}
            ),
            "metadata": {
                "editable_timeline_path": str(timeline_path),
                "timeline_edit_roundtrip": True,
                "operation_count": len(timeline["operations"]),
                "timeline_starts": {
                    element["id"]: element["timeline"]["start_seconds"]
                    for track in timeline["tracks"]
                    for element in track["elements"]
                },
            },
        }
        if not result["audio"]:
            result.pop("audio")
        return result

    @staticmethod
    def _edit_transform(transform: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if transform.get("scale") is not None:
            result["scale"] = transform["scale"]
        crop = {k: transform[k] for k in ("x", "y", "width", "height") if k in transform}
        if crop:
            result["crop"] = crop
        return result

    def _apply_command(
        self, timeline: dict[str, Any], command: dict[str, Any], *, record: bool
    ) -> None:
        command_type = command["type"]
        target_id = command["target_id"]
        payload = deepcopy(command.get("payload") or {})
        element = self._find_element(timeline, target_id)

        if command_type == "move":
            inverse = {"start_seconds": element["timeline"]["start_seconds"]}
            element["timeline"]["start_seconds"] = self._nonnegative(payload["start_seconds"])
        elif command_type == "trim":
            keys = ("trim_start_seconds", "trim_end_seconds", "duration_seconds")
            inverse = {key: element["timeline"].get(key) for key in keys if key in payload}
            for key in keys:
                if key in payload:
                    element["timeline"][key] = self._nonnegative(payload[key])
        elif command_type == "replace_asset":
            inverse = deepcopy(element.get("source") or {})
            element["source"] = deepcopy(payload)
        elif command_type == "set_volume":
            audio = element.setdefault("audio", {"volume": 1, "pan": 0, "muted": False})
            inverse = {"volume": audio.get("volume", 1)}
            audio["volume"] = max(0.0, min(2.0, float(payload["volume"])))
        elif command_type == "set_speed":
            timing = element["timeline"]
            inverse = {
                "speed": timing["speed"],
                "duration_seconds": timing["duration_seconds"],
                "maintain_pitch": (element.get("audio") or {}).get("maintain_pitch", True),
            }
            speed = float(payload["speed"])
            if speed <= 0:
                raise ValueError("Playback speed must be greater than zero")
            source_span = max(
                0.0,
                timing.get("trim_end_seconds", timing["duration_seconds"] * timing["speed"])
                - timing.get("trim_start_seconds", 0),
            )
            timing["speed"] = speed
            timing["duration_seconds"] = float(
                payload.get("duration_seconds", source_span / speed)
            )
            if element["kind"] == "audio":
                element.setdefault("audio", {})["maintain_pitch"] = bool(
                    payload.get("maintain_pitch", True)
                )
        elif command_type == "update_text":
            text = element.setdefault("text", {"content": ""})
            inverse = {"content": text.get("content", "")}
            text["content"] = str(payload["content"])
        elif command_type == "set_transform":
            inverse = deepcopy(element.get("transform") or {})
            element["transform"] = deepcopy(payload)
        elif command_type == "set_mask":
            inverse = deepcopy(element["mask"]) if element.get("mask") else {"_delete": True}
            if payload.get("_delete"):
                element.pop("mask", None)
            else:
                element["mask"] = deepcopy(payload)
        elif command_type == "set_keyframes":
            inverse = {"keyframes": deepcopy(element.get("keyframes") or [])}
            element["keyframes"] = self._normalize_keyframes(
                deepcopy(payload.get("keyframes") or [])
            )
        else:
            raise ValueError(f"Unsupported edit command: {command_type}")

        if record:
            timeline["operations"].append(
                {
                    "id": command.get("id") or self._operation_id(
                        timeline, command_type, target_id, payload
                    ),
                    "type": command_type,
                    "target_id": target_id,
                    "payload": payload,
                    "inverse": inverse,
                    "actor": command.get("actor", "agent"),
                    "status": "applied",
                    "created_at": command.get("created_at") or datetime.now(timezone.utc).isoformat(),
                }
            )

        self._sync_timing_ticks(element)

        timeline.setdefault("metadata", {})["duration_seconds"] = max(
            (
                item["timeline"]["start_seconds"] + item["timeline"]["duration_seconds"]
                for track in timeline["tracks"]
                for item in track["elements"]
            ),
            default=0,
        )

    @staticmethod
    def _find_element(timeline: dict[str, Any], element_id: str) -> dict[str, Any]:
        for track in timeline["tracks"]:
            for element in track["elements"]:
                if element["id"] == element_id:
                    return element
        raise ValueError(f"Timeline element not found: {element_id}")

    @staticmethod
    def _nonnegative(value: Any) -> float:
        number = float(value)
        if number < 0:
            raise ValueError("Timeline values cannot be negative")
        return number

    @staticmethod
    def _ticks(seconds: Any) -> int:
        return max(0, round(float(seconds) * 120000))

    @staticmethod
    def _rational_frame_rate(fps: Any) -> dict[str, int]:
        value = float(fps)
        common = {
            23.976: (24000, 1001),
            29.97: (30000, 1001),
            59.94: (60000, 1001),
        }
        for candidate, rational in common.items():
            if abs(value - candidate) < 0.001:
                return {"numerator": rational[0], "denominator": rational[1]}
        return {"numerator": round(value), "denominator": 1}

    def _sync_timing_ticks(self, element: dict[str, Any]) -> None:
        timing = element["timeline"]
        for seconds_key, ticks_key in (
            ("start_seconds", "start_ticks"),
            ("duration_seconds", "duration_ticks"),
            ("trim_start_seconds", "trim_start_ticks"),
            ("trim_end_seconds", "trim_end_ticks"),
        ):
            if seconds_key in timing:
                timing[ticks_key] = self._ticks(timing[seconds_key])

    def _normalize_keyframes(self, channels: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for channel in channels:
            for point in channel.get("points", []):
                if "time_seconds" in point:
                    point["time_ticks"] = self._ticks(point["time_seconds"])
        return channels

    @staticmethod
    def _operation_id(
        timeline: dict[str, Any], command_type: str, target_id: str, payload: dict[str, Any]
    ) -> str:
        raw = json.dumps(
            [len(timeline["operations"]), command_type, target_id, payload],
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"op-{hashlib.sha256(raw.encode()).hexdigest()[:12]}"

    @staticmethod
    def _opencut_draft(timeline: dict[str, Any]) -> dict[str, Any]:
        return {
            "format": "opencut-bridge-draft",
            "version": "1.0",
            "compatibility": "structural-draft-not-direct-import",
            "status": "v0.3-concepts-ready-awaiting-editor-api",
            "project": timeline["project"],
            "settings": timeline["settings"],
            "tracks": timeline["tracks"],
            "timebase": {
                "ticks_per_second": timeline["settings"]["timebase_ticks_per_second"],
                "frame_rate": timeline["settings"]["frame_rate"],
            },
            "notes": [
                "Aligned with OpenCut v0.3 integer timing, track lanes, masks, speed, and keyframe concepts.",
                "Use this draft as adapter input when the Editor API or MCP becomes stable.",
                "Complex HyperFrames and Remotion scenes should be exported as proxy clips for NLE editing.",
            ],
        }

    @staticmethod
    def _pack_readme() -> str:
        return """# OpenMontage Editable Project

This directory is the renderer-neutral handoff for human or agent editing.

- `timeline.json`: canonical multi-track project and command history.
- `media/`: portable media referenced by the timeline.
- `adapters/opencut-draft.json`: structural bridge for a future stable OpenCut API.
- `manifest.json`: SHA-256 inventory for transport verification.

Use the `editable_timeline` tool to apply edits, undo the latest edit, validate
the project, or import the timeline back into `edit_decisions` before rendering.
HyperFrames and Remotion remain the final render runtimes.
"""

    @staticmethod
    def _bundle_manifest(output_dir: Path) -> dict[str, Any]:
        files = []
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file() or path.name == "manifest.json":
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append(
                {
                    "path": path.relative_to(output_dir).as_posix(),
                    "sha256": digest,
                    "size_bytes": path.stat().st_size,
                }
            )
        return {"version": "1.0", "files": files}

    @staticmethod
    def _safe_name(value: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)
        return safe.strip("-") or "asset"

    @staticmethod
    def _required_path(inputs: dict[str, Any], key: str) -> Path:
        value = inputs.get(key)
        if not value:
            raise ValueError(f"{key} is required")
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(f"{key} not found: {path}")
        return path

    @staticmethod
    def _optional_path(value: Any) -> Path | None:
        if not value:
            return None
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(f"artifact path not found: {path}")
        return path

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"JSON object required: {path}")
        return data

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
