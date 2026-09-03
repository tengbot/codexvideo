"""Algorithms adapted from browser-use/video-use under the MIT License.

Source files:
  helpers/grade.py
  helpers/pack_transcripts.py
  helpers/timeline_view.py
  helpers/render.py

Source commit: 9575612f066aa517354790a645fd90f9f95a743b
Copyright (c) 2026 Browser Use

OpenMontage adaptations are limited to canonical ``*_seconds`` timing fields,
provider-neutral transcripts, and library-style error handling. See
THIRD_PARTY_LICENSES/video-use-MIT.txt for the full license.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np


PRESETS: dict[str, str] = {
    "subtle": "eq=contrast=1.03:saturation=0.98",
    "neutral_punch": (
        "eq=contrast=1.06:brightness=0.0:saturation=1.0,"
        "curves=master='0/0 0.25/0.23 0.75/0.77 1/1'"
    ),
    "warm_cinematic": (
        "eq=contrast=1.12:brightness=-0.02:saturation=0.88,"
        "colorbalance="
        "rs=0.02:gs=0.0:bs=-0.03:"
        "rm=0.04:gm=0.01:bm=-0.02:"
        "rh=0.08:gh=0.02:bh=-0.05,"
        "curves=master='0/0 0.25/0.22 0.75/0.78 1/1'"
    ),
    "none": "",
}


def get_preset(name: str) -> str:
    """Return an upstream grade preset by name."""
    if name not in PRESETS:
        raise KeyError(f"unknown preset '{name}'. Available: {', '.join(sorted(PRESETS))}")
    return PRESETS[name]


def _sample_frame_stats(
    video: Path,
    start: float,
    duration: float,
    n_samples: int = 10,
) -> dict[str, float]:
    """Sample luma and saturation with FFmpeg signalstats."""
    fps = max(0.5, min(n_samples / max(duration, 0.1), 10.0))
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as handle:
        metadata_path = Path(handle.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-nostats",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(video),
                "-t",
                f"{duration:.3f}",
                "-vf",
                f"fps={fps:.2f},signalstats,metadata=print:file={metadata_path}",
                "-f",
                "null",
                "-",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        y_avgs: list[float] = []
        y_mins: list[float] = []
        y_maxs: list[float] = []
        sat_avgs: list[float] = []
        bit_depth = 8

        def parse_value(line: str) -> float | None:
            try:
                return float(line.rsplit("=", 1)[1])
            except (ValueError, IndexError):
                return None

        with metadata_path.open(encoding="utf-8") as handle:
            for line in handle:
                if "lavfi.signalstats.YBITDEPTH" in line:
                    value = parse_value(line)
                    if value is not None:
                        bit_depth = int(value)
                elif "lavfi.signalstats.YAVG" in line:
                    value = parse_value(line)
                    if value is not None:
                        y_avgs.append(value)
                elif "lavfi.signalstats.YMIN" in line:
                    value = parse_value(line)
                    if value is not None:
                        y_mins.append(value)
                elif "lavfi.signalstats.YMAX" in line:
                    value = parse_value(line)
                    if value is not None:
                        y_maxs.append(value)
                elif "lavfi.signalstats.SATAVG" in line:
                    value = parse_value(line)
                    if value is not None:
                        sat_avgs.append(value)

        if not y_avgs:
            return {"y_mean": 0.5, "y_std": 0.18, "sat_mean": 0.25}
        max_value = (2**bit_depth) - 1
        y_mean = (sum(y_avgs) / len(y_avgs)) / max_value
        y_range = (
            ((sum(y_maxs) / len(y_maxs)) - (sum(y_mins) / len(y_mins))) / max_value
            if y_maxs and y_mins
            else 0.7
        )
        sat_mean = ((sum(sat_avgs) / len(sat_avgs)) / max_value) if sat_avgs else 0.25
        return {"y_mean": y_mean, "y_std": y_range / 4.0, "sat_mean": sat_mean}
    finally:
        metadata_path.unlink(missing_ok=True)


def auto_grade_for_clip(
    video: Path,
    start: float = 0.0,
    duration: float | None = None,
) -> tuple[str, dict[str, float]]:
    """Emit the upstream bounded, neutral per-clip correction filter."""
    if duration is None:
        try:
            duration = float(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        str(video),
                    ]
                )
                .decode()
                .strip()
            )
        except Exception:
            duration = 10.0
    stats = _sample_frame_stats(video, start, duration)
    y_mean = stats["y_mean"]
    y_range = stats["y_std"] * 4.0
    sat_mean = stats["sat_mean"]

    if y_range < 0.65:
        amount = max(0.0, min(1.0, (y_range - 0.50) / 0.15))
        contrast = 1.08 - 0.05 * amount
    else:
        contrast = 1.03
    gamma = 1.0
    if y_mean < 0.42:
        amount = max(0.0, min(1.0, (y_mean - 0.30) / 0.12))
        gamma = 1.10 - 0.08 * amount
    elif y_mean > 0.60:
        gamma = 0.97
    saturation = 0.98
    if sat_mean < 0.18:
        saturation = 1.04
    elif sat_mean > 0.38:
        saturation = 0.96

    contrast = max(0.94, min(1.08, contrast))
    gamma = max(0.94, min(1.10, gamma))
    saturation = max(0.94, min(1.06, saturation))
    parts = []
    if abs(contrast - 1.0) > 0.005:
        parts.append(f"contrast={contrast:.3f}")
    if abs(gamma - 1.0) > 0.005:
        parts.append(f"gamma={gamma:.3f}")
    if abs(saturation - 1.0) > 0.005:
        parts.append(f"saturation={saturation:.3f}")
    return ("eq=" + ":".join(parts) if parts else ""), stats


def _start(word: dict[str, Any]) -> float | None:
    value = word.get("start_seconds", word.get("start"))
    return float(value) if value is not None else None


def _end(word: dict[str, Any]) -> float | None:
    value = word.get("end_seconds", word.get("end"))
    return float(value) if value is not None else None


def group_into_phrases(
    words: list[dict[str, Any]],
    silence_threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """Group transcript tokens on silence or speaker changes."""
    phrases: list[dict[str, Any]] = []
    current_words: list[dict[str, Any]] = []
    current_start: float | None = None
    current_speaker: str | None = None

    def flush() -> None:
        nonlocal current_words, current_start, current_speaker
        if not current_words:
            return
        text_parts = []
        for word in current_words:
            raw = str(word.get("text") or "").strip()
            if not raw:
                continue
            if word.get("type", "word") == "audio_event" and not raw.startswith("("):
                raw = f"({raw})"
            text_parts.append(raw)
        if text_parts:
            text = " ".join(text_parts)
            for punctuation in (",", ".", "?", "!"):
                text = text.replace(f" {punctuation}", punctuation)
            phrases.append(
                {
                    "start_seconds": current_start,
                    "end_seconds": _end(current_words[-1]) or current_start or 0.0,
                    "text": text,
                    "speaker_id": current_speaker,
                }
            )
        current_words = []
        current_start = None
        current_speaker = None

    previous_end: float | None = None
    for word in words:
        word_type = word.get("type", "word")
        if word_type == "spacing":
            start = _start(word)
            end = _end(word)
            if start is not None and end is not None and end - start >= silence_threshold:
                flush()
            continue
        start = _start(word)
        if start is None:
            continue
        speaker = word.get("speaker_id")
        if current_speaker is not None and speaker is not None and speaker != current_speaker:
            flush()
        if previous_end is not None and start - previous_end >= silence_threshold:
            flush()
        if current_start is None:
            current_start = start
            current_speaker = str(speaker) if speaker is not None else None
        current_words.append(word)
        previous_end = _end(word) or start
    flush()
    return phrases


def compute_envelope(video: Path, start: float, end: float, samples: int = 2000) -> np.ndarray:
    """Extract mono PCM and return the upstream normalized RMS envelope."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        wav_path = Path(handle.name)
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                f"{start:.3f}",
                "-i",
                str(video),
                "-t",
                f"{end - start:.3f}",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(wav_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size == 0:
            return np.zeros(samples)
        with wave.open(str(wav_path), "rb") as wav:
            frames = wav.readframes(wav.getnframes())
        pcm = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if pcm.size == 0:
            return np.zeros(samples)
        window = max(1, pcm.size // samples)
        usable = (pcm.size // window) * window
        envelope = np.sqrt(np.mean(pcm[:usable].reshape(-1, window) ** 2, axis=1))
        if envelope.size < samples:
            envelope = np.pad(envelope, (0, samples - envelope.size))
        elif envelope.size > samples:
            envelope = envelope[:samples]
        if envelope.max() > 0:
            envelope = envelope / envelope.max()
        return envelope
    finally:
        wav_path.unlink(missing_ok=True)


def words_in_range(
    transcript: dict[str, Any] | None,
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    if not transcript:
        return []
    output = []
    for word in transcript.get("words", []):
        word_start = _start(word)
        word_end = _end(word)
        if word_start is None or word_end is None or word_end <= start or word_start >= end:
            continue
        output.append(word)
    return output


def find_silences(
    words: list[dict[str, Any]],
    start: float,
    end: float,
    threshold: float = 0.4,
) -> list[tuple[float, float]]:
    """Find transcript gaps at or above the requested threshold."""
    gaps: list[tuple[float, float]] = []
    previous_end = start
    for word in words:
        if word.get("type") == "spacing":
            continue
        word_start = max(start, _start(word) or start)
        if word_start - previous_end >= threshold:
            gaps.append((previous_end, word_start))
        previous_end = max(previous_end, _end(word) or word_start)
    if end - previous_end >= threshold:
        gaps.append((previous_end, end))
    return gaps


def measure_loudness(
    video_path: Path,
    *,
    integrated: float = -14.0,
    true_peak: float = -1.0,
    range_lu: float = 11.0,
) -> dict[str, str] | None:
    """Run the upstream first-pass loudnorm measurement and parse its JSON."""
    filter_value = (
        f"loudnorm=I={integrated}:TP={true_peak}:LRA={range_lu}:print_format=json"
    )
    process = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video_path),
            "-af",
            filter_value,
            "-vn",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    start = process.stderr.rfind("{")
    end = process.stderr.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(process.stderr[start : end + 1])
    except json.JSONDecodeError:
        return None
    needed = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    return data if needed.issubset(data) else None
