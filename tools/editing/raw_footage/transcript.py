"""Import local timing data into OpenMontage's provider-neutral transcript."""

from __future__ import annotations

import json
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

from .models import (
    cues_to_words,
    file_sha256,
    load_transcript,
    parse_srt,
    probe_media,
    read_json,
    write_json,
)
from .ported_video_use import group_into_phrases


class RawTranscript(BaseTool):
    name = "raw_transcript"
    version = "1.0.0"
    tier = ToolTier.CORE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "raw_footage_editing"
    provider = "openmontage"
    capabilities = ["local_srt_import", "local_word_timing_import", "transcript_packing"]
    best_for = [
        "Turning existing SRT files into a reusable word-timed edit contract",
        "Importing word timings produced by any local ASR or forced aligner",
        "Packing multiple takes into a compact, reviewable text document",
    ]
    not_good_for = [
        "Calling a hosted transcription provider",
        "Inventing word-exact timing from an SRT cue",
    ]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["import_srt", "import_json", "pack"]},
            "source_path": {"type": "string"},
            "transcript_path": {"type": "string"},
            "transcript_paths": {"type": "array", "items": {"type": "string"}},
            "output_path": {"type": "string"},
            "source_id": {"type": "string"},
            "speaker_id": {"type": "string"},
            "language": {"type": "string"},
            "silence_threshold": {"type": "number", "minimum": 0.1},
            "source_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "transcript_sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=32, network_required=False
    )
    side_effects = ["writes a source_transcript artifact or packed transcript"]
    user_visible_verification = [
        "Confirm source, speaker, and timing quality in source_transcript.json",
        "Read takes_packed.md before selecting edit ranges",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            operation = inputs["operation"]
            if operation == "pack":
                return self._pack(inputs)
            return self._import(inputs, from_srt=operation == "import_srt")
        except (OSError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as exc:
            return ToolResult(success=False, error=str(exc))

    def _import(self, inputs: dict[str, Any], *, from_srt: bool) -> ToolResult:
        source_path = Path(inputs["source_path"]).expanduser().resolve()
        transcript_path = Path(inputs["transcript_path"]).expanduser().resolve()
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        if not transcript_path.is_file():
            raise FileNotFoundError(transcript_path)
        source_id = str(inputs.get("source_id") or source_path.stem)
        speaker_id = str(inputs.get("speaker_id") or source_id)
        language = str(inputs.get("language") or "en")
        media = probe_media(source_path)

        if from_srt:
            words = cues_to_words(parse_srt(transcript_path), speaker_id)
            timing_quality = "cue_interpolated"
        else:
            payload = read_json(transcript_path)
            if payload.get("version") == "1.0" and "source_id" in payload:
                validate_artifact("source_transcript", payload)
                words = payload["words"]
                timing_quality = payload["timing_quality"]
            else:
                words = self._normalise_words(payload, speaker_id)
                timing_quality = "word_exact"

        duration = max(
            float(media["duration_seconds"]),
            max((float(word["end_seconds"]) for word in words), default=0.0),
        )
        artifact = {
            "version": "1.0",
            "source_id": source_id,
            "source_path": str(source_path),
            "language": language,
            "duration_seconds": round(duration, 3),
            "timing_quality": timing_quality,
            "words": words,
            "metadata": {
                "imported_from": str(transcript_path),
                "source_sha256": str(inputs.get("source_sha256") or file_sha256(source_path)),
                "source_size_bytes": source_path.stat().st_size,
                "source_mtime_ns": source_path.stat().st_mtime_ns,
                "transcript_sha256": str(
                    inputs.get("transcript_sha256") or file_sha256(transcript_path)
                ),
                "offline": True,
                "phrase_packing_algorithm": "browser-use/video-use@9575612f",
            },
        }
        validate_artifact("source_transcript", artifact)
        output_path = Path(inputs.get("output_path") or transcript_path.with_suffix(".words.json"))
        write_json(output_path, artifact)
        load_transcript(output_path)
        return ToolResult(
            success=True,
            data={"transcript": artifact, "transcript_path": str(output_path)},
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _normalise_words(payload: dict[str, Any], speaker_id: str) -> list[dict[str, Any]]:
        candidates = payload.get("words")
        if not isinstance(candidates, list):
            candidates = [
                word
                for segment in payload.get("segments", [])
                for word in (segment.get("words") or [])
            ]
        words: list[dict[str, Any]] = []
        for index, item in enumerate(candidates or [], start=1):
            text = str(item.get("text") or item.get("word") or "").strip()
            start = item.get("start_seconds", item.get("start"))
            end = item.get("end_seconds", item.get("end"))
            if not text or start is None or end is None:
                continue
            word = {
                "id": str(item.get("id") or f"w{index:06d}"),
                "text": text,
                "start_seconds": round(float(start), 3),
                "end_seconds": round(float(end), 3),
                "speaker_id": str(item.get("speaker_id") or speaker_id),
                "type": str(item.get("type") or "word"),
            }
            if item.get("confidence") is not None:
                word["confidence"] = float(item["confidence"])
            words.append(word)
        if not words:
            raise ValueError("Local JSON contains no usable word timings")
        words.sort(key=lambda item: (item["start_seconds"], item["end_seconds"]))
        return words

    def _pack(self, inputs: dict[str, Any]) -> ToolResult:
        paths = [Path(value).expanduser().resolve() for value in inputs.get("transcript_paths", [])]
        if not paths and inputs.get("transcript_path"):
            paths = [Path(inputs["transcript_path"]).expanduser().resolve()]
        if not paths:
            raise ValueError("transcript_paths must contain at least one local artifact")
        output_path = Path(inputs.get("output_path") or paths[0].parent / "takes_packed.md")
        silence_threshold = float(inputs.get("silence_threshold") or 0.5)
        lines = ["# Packed Takes", "", "Local timing source for editorial review. No media was uploaded.", ""]
        for path in paths:
            transcript = load_transcript(path)
            lines.extend(
                [
                    f"## {transcript['source_id']}",
                    "",
                    f"- Source: `{transcript['source_path']}`",
                    f"- Timing: `{transcript['timing_quality']}`",
                    f"- Duration: `{transcript['duration_seconds']:.3f}s`",
                    "",
                ]
            )
            phrases = group_into_phrases(transcript["words"], silence_threshold)
            for phrase in phrases:
                lines.append(
                    f"`{phrase['start_seconds']:.3f}-{phrase['end_seconds']:.3f}` "
                    f"**{phrase['speaker_id'] or transcript['source_id']}**: {phrase['text']}"
                )
                lines.append("")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return ToolResult(
            success=True,
            data={"packed_transcript_path": str(output_path), "source_count": len(paths)},
            artifacts=[str(output_path)],
        )
