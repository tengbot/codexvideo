"""Shared data and FFmpeg helpers for native raw-footage editing."""

from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from schemas.artifacts import validate_artifact


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-3000:]
        raise RuntimeError(f"Command failed ({result.returncode}): {detail}")
    return result


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def resolve_safe_path(value: str, *, base: Path, allowed_roots: Iterable[Path]) -> Path:
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    candidate = candidate.resolve()
    roots = [root.expanduser().resolve() for root in allowed_roots]
    if not roots:
        raise ValueError("allowed_roots must contain at least one directory")
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise ValueError(f"Path is outside allowed roots: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(candidate)
    return candidate


def parse_frame_rate(value: str | int | float) -> str:
    """Return an exact, FFmpeg-safe positive rational frame rate."""
    text = str(value).strip()
    if len(text) > 32 or not re.fullmatch(
        r"(?:[0-9]+(?:\.[0-9]+)?|[0-9]+/[0-9]+)", text
    ):
        raise ValueError("fps must be a positive number or rational such as 30 or 30000/1001")
    try:
        rate = Fraction(text)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(
            "fps must be a positive number or rational such as 30 or 30000/1001"
        ) from exc
    if rate <= 0:
        raise ValueError("fps must be greater than zero")
    max_component = 2_147_483_647
    if rate.numerator > max_component or rate.denominator > max_component:
        raise ValueError("fps precision or magnitude is too large")
    return f"{rate.numerator}/{rate.denominator}"


def file_sha256(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Hash a local source without loading the complete file into memory."""
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def probe_audio_streams(path: Path) -> list[dict[str, Any]]:
    """Return audio streams using zero-based audio ordinals for FFmpeg mapping."""
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index,codec_name,channels,sample_rate:stream_tags=language,title",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    streams: list[dict[str, Any]] = []
    for track, stream in enumerate(payload.get("streams") or []):
        tags = stream.get("tags") or {}
        streams.append(
            {
                "track": track,
                "stream_index": int(stream.get("index") or 0),
                "codec": str(stream.get("codec_name") or ""),
                "channels": int(stream.get("channels") or 0),
                "sample_rate": int(stream.get("sample_rate") or 0),
                "language": tags.get("language"),
                "title": tags.get("title"),
            }
        )
    return streams


def probe_media(path: Path) -> dict[str, Any]:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,pix_fmt,avg_frame_rate,r_frame_rate,color_transfer,color_primaries,color_space:stream_side_data=rotation",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    fps_rate = ""
    for field in ("avg_frame_rate", "r_frame_rate"):
        candidate = str(video.get(field) or "")
        if not candidate or candidate == "0/0":
            continue
        try:
            fps_rate = parse_frame_rate(candidate)
            break
        except ValueError:
            continue
    fps = float(Fraction(fps_rate)) if fps_rate else 0.0
    coded_width = int(video.get("width") or 0)
    coded_height = int(video.get("height") or 0)
    rotation = 0
    for side_data in video.get("side_data_list") or []:
        if side_data.get("rotation") is None:
            continue
        try:
            rotation = int(round(float(side_data["rotation"]))) % 360
        except (TypeError, ValueError, OverflowError):
            rotation = 0
        break
    width, height = coded_width, coded_height
    if rotation in {90, 270}:
        width, height = height, width
    format_data = payload.get("format") or {}
    return {
        "duration_seconds": float(format_data.get("duration") or 0),
        "size_bytes": int(format_data.get("size") or path.stat().st_size),
        "width": width,
        "height": height,
        "coded_width": coded_width,
        "coded_height": coded_height,
        "rotation": rotation,
        "fps": fps,
        "fps_rate": fps_rate,
        "codec": str(video.get("codec_name") or ""),
        "pixel_format": str(video.get("pix_fmt") or ""),
        "has_audio": audio is not None,
        "color_transfer": str(video.get("color_transfer") or ""),
        "color_primaries": str(video.get("color_primaries") or ""),
        "color_space": str(video.get("color_space") or ""),
    }


_SRT_BLOCK = re.compile(
    r"(?:^|\n)\s*(?:\d+\s*\n)?"
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})[^\n]*\n"
    r"(?P<text>.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def parse_timestamp(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_srt(path: Path) -> list[dict[str, Any]]:
    content = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    cues: list[dict[str, Any]] = []
    for match in _SRT_BLOCK.finditer(content.strip()):
        text = re.sub(r"<[^>]+>", "", match.group("text"))
        text = " ".join(line.strip() for line in text.splitlines() if line.strip())
        if text:
            cues.append(
                {
                    "start_seconds": parse_timestamp(match.group("start")),
                    "end_seconds": parse_timestamp(match.group("end")),
                    "text": text,
                }
            )
    if not cues:
        raise ValueError(f"No subtitle cues found in {path}")
    return cues


def cues_to_words(cues: list[dict[str, Any]], speaker_id: str) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    word_index = 1
    for cue in cues:
        tokens = re.findall(r"\S+", cue["text"])
        if not tokens:
            continue
        start = float(cue["start_seconds"])
        end = max(start, float(cue["end_seconds"]))
        weights = [max(1, len(re.sub(r"\W", "", token))) for token in tokens]
        total_weight = sum(weights)
        cursor = start
        for token, weight in zip(tokens, weights):
            token_end = end if token == tokens[-1] else cursor + (end - start) * weight / total_weight
            words.append(
                {
                    "id": f"w{word_index:06d}",
                    "text": token,
                    "start_seconds": round(cursor, 3),
                    "end_seconds": round(max(cursor, token_end), 3),
                    "speaker_id": speaker_id,
                    "type": "word",
                }
            )
            cursor = token_end
            word_index += 1
    return words


def load_transcript(path: Path) -> dict[str, Any]:
    transcript = read_json(path)
    validate_artifact("source_transcript", transcript)
    previous = -1.0
    for word in transcript["words"]:
        if word["end_seconds"] < word["start_seconds"]:
            raise ValueError(f"Word ends before it starts: {word['id']}")
        if word["start_seconds"] < previous - 0.001:
            raise ValueError(f"Word timeline is not monotonic: {word['id']}")
        previous = word["start_seconds"]
    return transcript


def trim_words_to_cut(
    transcript: dict[str, Any],
    *,
    source_in: float,
    source_out: float,
    timeline_start: float,
    speed: float = 1.0,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for word in transcript["words"]:
        start = float(word["start_seconds"])
        end = float(word["end_seconds"])
        if end <= source_in or start >= source_out:
            continue
        selected.append(
            {
                **word,
                "start_seconds": round(timeline_start + (max(start, source_in) - source_in) / speed, 3),
                "end_seconds": round(timeline_start + (min(end, source_out) - source_in) / speed, 3),
            }
        )
    return selected


def group_subtitle_cues(
    words: list[dict[str, Any]],
    *,
    max_words: int = 7,
    max_duration: float = 2.8,
    max_gap: float = 0.5,
) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for word in words:
        should_break = bool(
            current
            and (
                len(current) >= max_words
                or word["start_seconds"] - current[-1]["end_seconds"] > max_gap
                or word["end_seconds"] - current[0]["start_seconds"] > max_duration
                or re.search(r"[.!?]$", current[-1]["text"])
            )
        )
        if should_break:
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)
    return [
        {
            "start_seconds": max(0.0, float(group[0]["start_seconds"])),
            "end_seconds": max(float(group[0]["start_seconds"]) + 0.08, float(group[-1]["end_seconds"])),
            "text": " ".join(item["text"] for item in group),
        }
        for group in groups
    ]


def format_srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(path: Path, cues: list[dict[str, Any]]) -> None:
    blocks = []
    for index, cue in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{format_srt_timestamp(cue['start_seconds'])} --> "
            f"{format_srt_timestamp(cue['end_seconds'])}\n{cue['text']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def timeline_boundaries(cuts: list[dict[str, Any]]) -> list[float]:
    cursor = 0.0
    boundaries: list[float] = []
    for index, cut in enumerate(cuts):
        speed = float(cut.get("speed") or 1.0)
        cursor += (float(cut["out_seconds"]) - float(cut["in_seconds"])) / speed
        if index < len(cuts) - 1:
            boundaries.append(round(cursor, 3))
    return boundaries
