"""Command-line front door for consumer CodexVideo projects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from codexvideo.catalog import load_catalog
from codexvideo.project import build_capability_manifest, create_project, resume_project
from lib.paths import PROJECTS_DIR
from tools.analysis.creative_qa import CreativeQA
from tools.cost_tracker import ApprovalRequiredError, BudgetExceededError
from jsonschema import ValidationError


def _audio_track(value: str) -> str | int:
    if value == "auto":
        return value
    try:
        track = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("audio track must be 'auto' or a zero-based integer") from exc
    if track < 0:
        raise argparse.ArgumentTypeError("audio track must be zero or greater")
    return track


def _print(value: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                print(f"{key}: {json.dumps(item, ensure_ascii=False)}")
            else:
                print(f"{key}: {item}")
        return
    print(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexvideo",
        description="Create resumable, consumer-led video projects for Codex.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("routes", help="List consumer video formats")
    sub.add_parser("styles", help="List consumer-facing visual styles")

    doctor = sub.add_parser("doctor", help="Inspect local runtimes and provider unlocks")
    doctor.add_argument("--provider-pack", default="auto")

    create = sub.add_parser("create", help="Scaffold a routed, resumable production project")
    create.add_argument("prompt", nargs="?", default="")
    create.add_argument("--url")
    create.add_argument(
        "--media",
        action="append",
        type=Path,
        default=[],
        help="Local source media path; repeat for multiple files",
    )
    create.add_argument("--transcript", type=Path, help="Local SRT or word-timing JSON")
    create.add_argument("--audio-track", type=_audio_track, default="auto")
    create.add_argument(
        "--prepare-media",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Probe, fingerprint, and cache source audio during project creation",
    )
    create.add_argument("--title")
    create.add_argument("--project-id")
    create.add_argument("--type", default="auto")
    create.add_argument("--style", default="auto")
    create.add_argument("--destination", default="tiktok")
    create.add_argument("--aspect", choices=["9:16", "1:1", "16:9"])
    create.add_argument("--language", default="en")
    create.add_argument("--duration", type=int)
    create.add_argument("--audience", default="English-speaking consumers")
    create.add_argument("--budget", type=float, default=5.0)
    create.add_argument("--flow", choices=["automation", "companion"], default="automation")
    create.add_argument("--storyboard", action=argparse.BooleanOptionalAction, default=False)
    create.add_argument("--provider-pack", default="auto")
    create.add_argument("--variants", type=int, default=1)
    create.add_argument("--projects-dir", type=Path, default=PROJECTS_DIR)

    resume = sub.add_parser("resume", help="Report the next safe stage for a project")
    resume.add_argument("project", type=Path)

    checkpoint = sub.add_parser("checkpoint", help="Validate and persist a stage's canonical artifacts")
    checkpoint.add_argument("project", type=Path)
    checkpoint.add_argument("stage")
    checkpoint.add_argument("--status", choices=["in_progress", "awaiting_human", "completed", "failed"], required=True)
    checkpoint.add_argument("--approval-note", help="Record actual explicit user approval; never invent it")
    checkpoint.add_argument("--error")

    invoke = sub.add_parser("invoke", help="Prepare or dispatch one governed tool call")
    invoke.add_argument("project", type=Path)
    invoke.add_argument("stage")
    invoke.add_argument("tool")
    invoke.add_argument("--inputs", type=Path, required=True)
    invoke.add_argument("--request-id", required=True)
    invoke.add_argument("--execute", action="store_true")
    invoke.add_argument("--approval", type=Path)

    qa = sub.add_parser("qa", help="Enforce the creative quality gate")
    qa.add_argument("report", type=Path)
    qa.add_argument("--prepare-video", type=Path, help="Bind a fresh review to this render and reset previous scores")
    qa.add_argument("--project", type=Path)
    qa.add_argument("--write", action="store_true", help="Write evaluated status back to the report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    catalog = load_catalog()

    try:
        if args.command == "routes":
            _print(catalog["formats"], args.json)
            return 0
        if args.command == "styles":
            _print(catalog["styles"], args.json)
            return 0
        if args.command == "doctor":
            required = ["video_post", "audio_processing", "subtitle"]
            optional = sorted({
                capability
                for format_config in catalog["formats"].values()
                for capability in (
                    format_config["required_capabilities"] + format_config["optional_capabilities"]
                )
                if capability not in required
            })
            result = build_capability_manifest(required, optional, args.provider_pack)
            _print(result, args.json)
            return 0 if result["planning_ready"] else 2
        if args.command == "create":
            if not args.prompt and not args.url and not args.media:
                parser.error("create requires a prompt, --url, or --media")
            result = create_project(
                prompt=args.prompt,
                source_url=args.url,
                title=args.title,
                project_id=args.project_id,
                requested_format=args.type,
                requested_style=args.style,
                destination=args.destination,
                aspect=args.aspect,
                language=args.language,
                duration_seconds=args.duration,
                audience=args.audience,
                budget_usd=args.budget,
                flow=args.flow,
                storyboard=args.storyboard,
                provider_pack=args.provider_pack,
                variants=args.variants,
                projects_dir=args.projects_dir,
                source_media_paths=args.media,
                source_transcript_path=args.transcript,
                audio_track=args.audio_track,
                prepare_media=args.prepare_media,
            )
            _print(result, args.json)
            return 0 if result["status"] in {"ready", "planning_ready"} else 2
        if args.command == "resume":
            result = resume_project(args.project)
            _print(result, args.json)
            return 0
        if args.command == "checkpoint":
            from codexvideo.execution import persist_stage
            result = persist_stage(args.project, args.stage, args.status, args.approval_note, args.error)
            _print(result, args.json)
            return 0
        if args.command == "invoke":
            from codexvideo.execution import invoke_tool
            result = invoke_tool(args.project, args.stage, args.tool,
                                 json.loads(args.inputs.read_text(encoding="utf-8")),
                                 args.request_id, args.execute, args.approval)
            _print(result, args.json)
            return 0 if result["status"] in {"prepared", "completed"} else 3
        if args.command == "qa":
            result = CreativeQA().execute({
                "operation": "prepare" if args.prepare_video else "evaluate",
                **({"video_path": str(args.prepare_video)} if args.prepare_video else {}),
                **({"project_dir": str(args.project)} if args.project else {}),
                "report_path": str(args.report),
                "output_path": str(args.report) if args.write else None,
            })
            _print(result.data if result.data else {"error": result.error}, args.json)
            return 0 if result.success else 3
    except (OSError, ValueError, KeyError, ApprovalRequiredError, BudgetExceededError, ValidationError) as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}))
        else:
            parser.exit(2, f"codexvideo: {exc}\n")
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
