"""Bind a review to exact local media and production inputs, never to a filename alone."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def verify_playable_video(video: Path) -> str:
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video),
    ], capture_output=True, text=True, check=True, timeout=30)
    media = json.loads(probe.stdout)
    video_streams = [s for s in media.get("streams", []) if s.get("codec_type") == "video"]
    if not video_streams or float(media.get("format", {}).get("duration", 0)) <= 0:
        raise ValueError("Render has no playable video stream")
    decoded = subprocess.run([
        "ffmpeg", "-v", "error", "-xerror", "-threads", "1", "-i", str(video),
        "-map", "0:v:0", "-map", "0:a:0?", "-threads", "1", "-f", "null", "-",
    ], capture_output=True, text=True, timeout=120)
    if decoded.returncode or decoded.stderr.strip():
        raise ValueError(f"Render decode failed: {decoded.stderr[-500:]}")
    return f"FFprobe verified video; FFmpeg decoded all frames and audio: {video.name}"


def file_fingerprint(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}


def bind_render(video: Path, project: Path) -> dict[str, Any]:
    project = project.resolve()
    dependencies = []
    names = (
        "consumer_request", "product_truth", "script", "dialogue_script", "scene_plan",
        "proof_plan", "asset_manifest", "audio_timeline", "edit_decisions", "cast_bible",
        "visual_continuity_bible", "shot_language_plan",
    )
    paths = {project / "artifacts" / f"{name}.json" for name in names}
    asset_manifest = project / "artifacts/asset_manifest.json"
    if asset_manifest.is_file():
        for asset in json.loads(asset_manifest.read_text(encoding="utf-8")).get("assets", []):
            value = asset.get("path")
            if value and not value.startswith(("http://", "https://")):
                path = Path(value).expanduser()
                path = path if path.is_absolute() else project / path
                dependencies.append(file_fingerprint(path))
    dependencies.extend(file_fingerprint(path) for path in sorted(paths) if path.is_file())
    return {"video": file_fingerprint(video), "dependencies": dependencies}


def validate_render_binding(binding: dict[str, Any] | None, video: Path | None = None) -> None:
    if not binding or not isinstance(binding.get("video"), dict):
        raise ValueError("Review is unbound; prepare a review for the final rendered video first")
    reviewed = binding["video"]
    if video is not None and file_fingerprint(video)["sha256"] != reviewed.get("sha256"):
        raise ValueError("Reviewed render does not match the video being delivered")
    for record in [reviewed, *binding.get("dependencies", [])]:
        current = file_fingerprint(Path(record["path"]))
        if current["sha256"] != record.get("sha256") or current["size_bytes"] != record.get("size_bytes"):
            raise ValueError(f"Review is stale; changed input: {record['path']}")
