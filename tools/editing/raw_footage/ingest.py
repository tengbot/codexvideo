"""Content-addressed ingest for user-supplied video and audio sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from tools.audio.audio_mixer import AudioMixer
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

from .models import file_sha256, probe_audio_streams, probe_media, read_json, write_json
from .transcript import RawTranscript


class RawFootageIngest(BaseTool):
    name = "raw_footage_ingest"
    version = "1.0.0"
    tier = ToolTier.CORE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "source_ingest"
    provider = "openmontage"
    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    capabilities = [
        "source_fingerprinting",
        "audio_track_inventory",
        "audio_track_selection",
        "silent_track_guard",
        "content_addressed_audio_cache",
        "local_transcript_import",
    ]
    best_for = [
        "Preparing supplied footage before transcription or editorial review",
        "Avoiding duplicate audio extraction on resumed projects",
        "Finding a usable audio stream in OBS and multi-track recordings",
    ]
    not_good_for = [
        "Choosing between multiple speech tracks without human review",
        "Running a paid or hosted transcription provider",
    ]
    input_schema = {
        "type": "object",
        "required": ["input_path", "project_dir"],
        "properties": {
            "input_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "source_id": {"type": "string"},
            "audio_track": {
                "oneOf": [
                    {"type": "integer", "minimum": 0},
                    {"type": "string", "const": "auto"},
                ],
                "default": "auto",
            },
            "silence_threshold_db": {
                "type": "number",
                "minimum": -120,
                "maximum": 0,
                "default": -60,
            },
            "transcript_path": {"type": "string"},
            "language": {"type": "string", "default": "en"},
            "output_path": {"type": "string"},
            "force": {"type": "boolean", "default": False},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=2048, network_required=False
    )
    idempotency_key_fields = [
        "input_path",
        "audio_track",
        "silence_threshold_db",
        "transcript_path",
    ]
    side_effects = ["writes cached PCM audio and a source ingest manifest"]
    user_visible_verification = [
        "Confirm the selected audio track contains the intended speaker",
        "Review takes_packed.md before approving edit ranges",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            return self._ingest(inputs)
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc))

    def _ingest(self, inputs: dict[str, Any]) -> ToolResult:
        source = Path(inputs["input_path"]).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        project_dir = Path(inputs["project_dir"]).expanduser().resolve()
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        output_path = Path(
            inputs.get("output_path") or artifacts_dir / "source_ingest_manifest.json"
        ).expanduser().resolve()
        try:
            output_path.relative_to(project_dir)
        except ValueError as exc:
            raise ValueError("output_path must stay inside project_dir") from exc
        existing = self._load_existing(output_path)
        source_identity = self._source_identity(source, existing)
        source_id = str(inputs.get("source_id") or source.stem)
        language = str(inputs.get("language") or "en")
        requested_track = inputs.get("audio_track", "auto")
        if requested_track != "auto":
            requested_track = int(requested_track)
            if requested_track < 0:
                raise ValueError("audio_track must be zero or greater")
        threshold = float(inputs.get("silence_threshold_db", -60.0))
        if not -120.0 <= threshold <= 0.0:
            raise ValueError("silence_threshold_db must be between -120 and 0")

        transcript_input = self._optional_file(inputs.get("transcript_path"))
        transcript_sha = file_sha256(transcript_input) if transcript_input else None
        if not inputs.get("force") and self._cache_is_valid(
            existing,
            source_identity=source_identity,
            source_id=source_id,
            requested_track=requested_track,
            silence_threshold_db=threshold,
            transcript_input=transcript_input,
            transcript_sha=transcript_sha,
            language=language,
        ):
            existing["cache"]["status"] = "hit"
            write_json(output_path, existing)
            return self._result(existing, output_path)

        media = probe_media(source)
        audio_streams = probe_audio_streams(source)
        cache_key = source_identity["sha256"][:16]
        cache_dir = project_dir / "cache" / "source-ingest" / cache_key
        cache_dir.mkdir(parents=True, exist_ok=True)
        warnings: list[str] = []
        selected_track: int | None = None
        selected_path: Path | None = None
        selection_policy = "none"

        measured_tracks = [
            {
                **stream,
                "peak_dbfs": None,
                "status": "not_measured",
            }
            for stream in audio_streams
        ]
        if audio_streams:
            tracks_to_measure = (
                [requested_track]
                if isinstance(requested_track, int)
                else [stream["track"] for stream in audio_streams]
            )
            if isinstance(requested_track, int) and requested_track >= len(audio_streams):
                raise ValueError(
                    f"audio_track {requested_track} is unavailable; {source.name} has "
                    f"{len(audio_streams)} audio track(s), numbered 0-{len(audio_streams) - 1}"
                )

            for track in tracks_to_measure:
                wav_path = cache_dir / f"track-{track}.wav"
                extracted = AudioMixer().execute(
                    {
                        "operation": "extract",
                        "input_path": str(source),
                        "output_path": str(wav_path),
                        "audio_track": track,
                        "reject_silence": False,
                        "silence_threshold_db": threshold,
                    }
                )
                if not extracted.success:
                    raise RuntimeError(extracted.error or f"Could not extract audio track {track}")
                peak = extracted.data.get("peak_dbfs")
                measured_tracks[track]["peak_dbfs"] = peak
                measured_tracks[track]["status"] = (
                    "usable" if peak is not None and peak >= threshold else "silent"
                )

            usable = [track for track in measured_tracks if track["status"] == "usable"]
            if not usable:
                for wav_path in cache_dir.glob("track-*.wav"):
                    wav_path.unlink(missing_ok=True)
                raise ValueError(
                    f"All measured audio tracks are silent below {threshold:.1f} dBFS"
                )
            if isinstance(requested_track, int):
                selected_track = requested_track
                selection_policy = "explicit"
                if measured_tracks[selected_track]["status"] != "usable":
                    raise ValueError(
                        f"Audio track {selected_track} is silent below {threshold:.1f} dBFS"
                    )
            elif len(audio_streams) == 1:
                selected_track = 0
                selection_policy = "only_track"
            else:
                selected_track = max(
                    usable,
                    key=lambda item: (
                        float(item["peak_dbfs"])
                        if item["peak_dbfs"] is not None
                        else float("-inf")
                    ),
                )["track"]
                selection_policy = "loudest_non_silent"
                if len(usable) > 1:
                    warnings.append(
                        "Multiple non-silent tracks found; the loudest was selected automatically. "
                        "Confirm it contains the intended speaker before ASR."
                    )
            selected_path = cache_dir / f"track-{selected_track}.wav"
            for wav_path in cache_dir.glob("track-*.wav"):
                if wav_path != selected_path:
                    wav_path.unlink(missing_ok=True)
        else:
            warnings.append("Source has no audio stream; continue with visual-only review.")

        transcript = self._import_transcript(
            transcript_input,
            source=source,
            source_id=source_id,
            language=language,
            artifacts_dir=artifacts_dir,
            source_sha=source_identity["sha256"],
            transcript_sha=transcript_sha,
        )
        manifest = {
            "version": "1.0",
            "source": {
                "id": source_id,
                "path": str(source),
                **source_identity,
                "media": media,
            },
            "audio": {
                "track_count": len(audio_streams),
                "tracks": measured_tracks,
                "selected_track": selected_track,
                "selected_path": str(selected_path) if selected_path else None,
                "selection_policy": selection_policy,
                "silence_threshold_db": threshold,
            },
            "transcript": {
                **transcript,
                "input_sha256": transcript_sha,
            },
            "cache": {
                "status": "miss",
                "key": cache_key,
                "directory": str(cache_dir),
            },
            "warnings": warnings,
            "next_action": self._next_action(transcript, selected_path),
        }
        validate_artifact("source_ingest_manifest", manifest)
        write_json(output_path, manifest)
        return self._result(manifest, output_path)

    @staticmethod
    def _optional_file(value: Any) -> Path | None:
        if not value:
            return None
        path = Path(str(value)).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    @staticmethod
    def _load_existing(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            manifest = read_json(path)
            validate_artifact("source_ingest_manifest", manifest)
            return manifest
        except Exception:
            return None

    @staticmethod
    def _source_identity(source: Path, existing: dict[str, Any] | None) -> dict[str, Any]:
        stat = source.stat()
        if existing:
            previous = existing.get("source") or {}
            if (
                previous.get("path") == str(source)
                and previous.get("size_bytes") == stat.st_size
                and previous.get("mtime_ns") == stat.st_mtime_ns
                and previous.get("sha256")
            ):
                return {
                    "sha256": previous["sha256"],
                    "size_bytes": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
        return {
            "sha256": file_sha256(source),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
        }

    @staticmethod
    def _cache_is_valid(
        existing: dict[str, Any] | None,
        *,
        source_identity: dict[str, Any],
        source_id: str,
        requested_track: str | int,
        silence_threshold_db: float,
        transcript_input: Path | None,
        transcript_sha: str | None,
        language: str,
    ) -> bool:
        if not existing or existing.get("source", {}).get("sha256") != source_identity["sha256"]:
            return False
        if existing.get("source", {}).get("id") != source_id:
            return False
        audio = existing.get("audio") or {}
        selected = audio.get("selected_track")
        if isinstance(requested_track, int) and selected != requested_track:
            return False
        if requested_track == "auto" and audio.get("selection_policy") == "explicit":
            return False
        if audio.get("silence_threshold_db") != silence_threshold_db:
            return False
        selected_path = audio.get("selected_path")
        if selected_path and not Path(selected_path).is_file():
            return False
        transcript = existing.get("transcript") or {}
        if transcript.get("language") != language:
            return False
        if transcript_input:
            if transcript.get("input_path") != str(transcript_input):
                return False
            if transcript.get("input_sha256") != transcript_sha:
                return False
        elif transcript.get("input_path") is not None:
            return False
        for key in ("artifact_path", "packed_path"):
            path = transcript.get(key)
            if path and not Path(path).is_file():
                return False
        return True

    @staticmethod
    def _import_transcript(
        transcript_path: Path | None,
        *,
        source: Path,
        source_id: str,
        language: str,
        artifacts_dir: Path,
        source_sha: str,
        transcript_sha: str | None,
    ) -> dict[str, Any]:
        if transcript_path is None:
            return {
                "status": "missing",
                "language": language,
                "input_path": None,
                "artifact_path": None,
                "packed_path": None,
                "timing_quality": None,
            }
        artifact_path = artifacts_dir / "source_transcript.json"
        operation = "import_srt" if transcript_path.suffix.lower() == ".srt" else "import_json"
        imported = RawTranscript().execute(
            {
                "operation": operation,
                "source_path": str(source),
                "transcript_path": str(transcript_path),
                "output_path": str(artifact_path),
                "source_id": source_id,
                "language": language,
                "source_sha256": source_sha,
                "transcript_sha256": transcript_sha,
            }
        )
        if not imported.success:
            raise RuntimeError(imported.error or "Could not import transcript")
        packed_path = artifacts_dir / "takes_packed.md"
        packed = RawTranscript().execute(
            {
                "operation": "pack",
                "transcript_path": str(artifact_path),
                "output_path": str(packed_path),
            }
        )
        if not packed.success:
            raise RuntimeError(packed.error or "Could not pack transcript")
        return {
            "status": "imported",
            "language": language,
            "input_path": str(transcript_path),
            "artifact_path": str(artifact_path),
            "packed_path": str(packed_path),
            "timing_quality": imported.data["transcript"]["timing_quality"],
        }

    @staticmethod
    def _next_action(transcript: dict[str, Any], selected_path: Path | None) -> str:
        if transcript["status"] == "imported":
            return "Review takes_packed.md, then approve or revise the edit ranges."
        if selected_path:
            return (
                "Run an approved local or configured ASR tool on selected_path, then re-run "
                "raw_footage_ingest with transcript_path."
            )
        return "Review the source visually and decide whether narration must be created."

    @staticmethod
    def _result(manifest: dict[str, Any], output_path: Path) -> ToolResult:
        artifacts = [str(output_path)]
        selected = manifest["audio"].get("selected_path")
        if selected:
            artifacts.append(selected)
        for key in ("artifact_path", "packed_path"):
            path = manifest["transcript"].get(key)
            if path:
                artifacts.append(path)
        return ToolResult(
            success=True,
            data={"manifest": manifest, "manifest_path": str(output_path)},
            artifacts=artifacts,
        )
