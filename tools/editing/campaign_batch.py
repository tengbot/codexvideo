"""Deterministic modular campaign planning, assembly, resume, and media QA."""

from __future__ import annotations

import hashlib
import itertools
import json
import re
import time
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


class CampaignBatch(BaseTool):
    """Execute an approved module matrix without making creative decisions."""

    name = "campaign_batch"
    version = "0.1.0"
    tier = ToolTier.CORE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT

    capability = "campaign_post"
    provider = "openmontage"
    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg with ffprobe support."
    agent_skills = ["ffmpeg"]
    capabilities = [
        "campaign_plan",
        "modular_variant_assembly",
        "aspect_profile_delivery",
        "subtitle_timeline_merge",
        "batch_resume",
        "media_qa",
    ]
    supports = {
        "local_offline": True,
        "free": True,
        "creative_decisions": False,
        "single_final_encode_per_deliverable": True,
    }
    best_for = [
        "Assembling approved hook, body, and CTA modules into many deliverables",
        "Rendering explicit or full-factorial variant matrices",
        "Producing landscape, portrait, and square delivery profiles",
        "Resuming a local batch without rebuilding QA-passed outputs",
    ]
    not_good_for = [
        "Writing hooks or scripts",
        "Choosing experiment winners",
        "Reflowing a motion-graphics composition without profile-specific module renders",
        "Publishing performance metrics back from social platforms",
    ]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["plan", "run", "resume", "validate", "report"],
            },
            "campaign_path": {"type": "string"},
            "run_path": {"type": "string"},
            "project_dir": {"type": "string"},
            "continue_on_error": {"type": "boolean", "default": True},
            "limit": {"type": "integer", "minimum": 1},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "campaign_plan": {"type": "object"},
            "batch_run": {"type": "object"},
            "campaign_plan_path": {"type": "string"},
            "run_path": {"type": "string"},
            "variants_path": {"type": "string"},
            "report_path": {"type": "string"},
            "files_written": {"type": "array", "items": {"type": "string"}},
            "rendered_jobs": {"type": "integer"},
            "cached_jobs": {"type": "integer"},
            "failed_jobs": {"type": "integer"},
        },
    }
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(
        cpu_cores=4,
        ram_mb=1024,
        vram_mb=0,
        disk_mb=10000,
        network_required=False,
    )
    side_effects = [
        "writes campaign artifacts, outputs, work files, and reports",
        "runs one FFmpeg encode and media QA pass per pending deliverable",
    ]
    user_visible_verification = [
        "Open outputs for every requested profile and verify composition framing",
        "Confirm batch-report.json has zero failed jobs",
        "Run resume and confirm QA-passed jobs are reported as cached",
    ]

    _SRT_TIMING = re.compile(
        r"(?P<sh>\d{2}):(?P<sm>\d{2}):(?P<ss>\d{2}),(?P<sms>\d{3})"
        r"\s*-->\s*"
        r"(?P<eh>\d{2}):(?P<em>\d{2}):(?P<es>\d{2}),(?P<ems>\d{3})"
    )

    def __init__(self) -> None:
        self._media_cache: dict[str, dict[str, Any]] = {}
        self._file_hash_cache: dict[str, str] = {}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            operation = inputs["operation"]
            if operation == "plan":
                result = self._plan(inputs)
            elif operation in {"run", "resume"}:
                result = self._run(inputs)
            elif operation == "validate":
                result = self._validate(inputs)
            elif operation == "report":
                result = self._report(inputs)
            else:
                return ToolResult(success=False, error=f"Unsupported operation: {operation}")
            result.duration_seconds = round(time.monotonic() - started, 2)
            return result
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                duration_seconds=round(time.monotonic() - started, 2),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"campaign batch failed: {exc}",
                duration_seconds=round(time.monotonic() - started, 2),
            )

    def _plan(self, inputs: dict[str, Any]) -> ToolResult:
        source_path = self._required_path(inputs, "campaign_path")
        campaign = self._read_json(source_path)
        validate_artifact("campaign_plan", campaign)
        project_dir = self._project_dir(inputs, source_path)
        variants = self._materialize_variants(campaign)
        self._validate_semantics(campaign, variants, project_dir)

        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        canonical_campaign_path = artifacts_dir / "campaign_plan.json"
        variants_path = artifacts_dir / "variants.json"
        run_path = Path(inputs.get("run_path") or artifacts_dir / "batch_run.json")
        if not run_path.is_absolute():
            run_path = project_dir / run_path

        self._write_json(canonical_campaign_path, campaign)
        self._write_json(
            variants_path,
            {
                "version": "1.0",
                "campaign_id": campaign["campaign_id"],
                "experiment": campaign["experiment"],
                "variants": variants,
            },
        )

        old_run = self._read_json(run_path) if run_path.is_file() else None
        run = self._build_run(
            campaign=campaign,
            variants=variants,
            project_dir=project_dir,
            campaign_plan_path=canonical_campaign_path,
            old_run=old_run,
        )
        validate_artifact("batch_run", run)
        self._write_json(run_path, run)
        return ToolResult(
            success=True,
            data={
                "campaign_plan": campaign,
                "batch_run": run,
                "campaign_plan_path": str(canonical_campaign_path),
                "variants_path": str(variants_path),
                "run_path": str(run_path),
                "files_written": [
                    str(canonical_campaign_path),
                    str(variants_path),
                    str(run_path),
                ],
            },
            artifacts=[str(canonical_campaign_path), str(run_path)],
        )

    def _run(self, inputs: dict[str, Any]) -> ToolResult:
        run_path = self._resolve_run_path(inputs)
        run = self._read_json(run_path)
        validate_artifact("batch_run", run)
        campaign_path = Path(run["campaign_plan_path"])
        campaign = self._read_json(campaign_path)
        validate_artifact("campaign_plan", campaign)
        project_dir = self._project_dir(inputs, campaign_path)
        variants = self._materialize_variants(campaign)
        self._validate_semantics(campaign, variants, project_dir)

        expected_plan_hash = self._json_hash(campaign)
        if run["plan_hash"] != expected_plan_hash:
            raise ValueError("Campaign plan changed after planning; run operation=plan again")

        module_lookup = {module["id"]: module for module in campaign["modules"]}
        profile_lookup = {profile["id"]: profile for profile in campaign["profiles"]}
        variant_lookup = {variant["id"]: variant for variant in variants}
        self._validate_run_inputs(
            run=run,
            campaign=campaign,
            variant_lookup=variant_lookup,
            module_lookup=module_lookup,
            profile_lookup=profile_lookup,
            project_dir=project_dir,
        )
        continue_on_error = inputs.get("continue_on_error", True)
        limit = inputs.get("limit")
        processed = 0
        rendered = 0
        cached = 0
        failures = 0

        for job in run["jobs"]:
            if limit is not None and processed >= limit:
                break
            if self._job_is_cached(job):
                cached += 1
                continue
            processed += 1
            job["status"] = "running"
            job["attempts"] += 1
            job["started_at"] = self._now()
            job.pop("completed_at", None)
            job["error"] = None
            job.pop("qa", None)
            self._refresh_run(run)
            self._write_run(run_path, run)

            try:
                modules = [module_lookup[module_id] for module_id in job["module_ids"]]
                profile = profile_lookup[job["profile_id"]]
                output_path = Path(job["output_path"])
                output_path.parent.mkdir(parents=True, exist_ok=True)
                self._render_job(
                    modules=modules,
                    profile=profile,
                    project_dir=project_dir,
                    output_path=output_path,
                    job=job,
                )
                qa = self._qa_output(
                    output_path=output_path,
                    profile=profile,
                    expected_duration=self._modules_duration(modules, profile, project_dir),
                )
                job["qa"] = qa
                if not qa["passed"]:
                    raise ValueError("; ".join(qa["issues"]))
                job["status"] = "qa_passed"
                job["completed_at"] = self._now()
                rendered += 1
            except Exception as exc:
                job["status"] = "failed"
                job["error"] = str(exc)[:2000]
                job["completed_at"] = self._now()
                failures += 1
                if not continue_on_error:
                    self._refresh_run(run)
                    self._write_run(run_path, run)
                    break

            self._refresh_run(run)
            self._write_run(run_path, run)

        report_path = self._write_report(run, project_dir)
        data = {
            "batch_run": run,
            "run_path": str(run_path),
            "report_path": str(report_path),
            "files_written": [
                str(run_path),
                str(report_path),
                *[
                    job["output_path"]
                    for job in run["jobs"]
                    if job["status"] == "qa_passed"
                ],
            ],
            "rendered_jobs": rendered,
            "cached_jobs": cached,
            "failed_jobs": failures,
        }
        if failures:
            return ToolResult(
                success=False,
                data=data,
                artifacts=[str(run_path), str(report_path)],
                error=f"{failures} campaign jobs failed",
            )
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(run_path), str(report_path)],
        )

    def _validate(self, inputs: dict[str, Any]) -> ToolResult:
        campaign_path = self._required_path(inputs, "campaign_path")
        campaign = self._read_json(campaign_path)
        validate_artifact("campaign_plan", campaign)
        project_dir = self._project_dir(inputs, campaign_path)
        variants = self._materialize_variants(campaign)
        self._validate_semantics(campaign, variants, project_dir)
        data: dict[str, Any] = {
            "campaign_plan": campaign,
            "campaign_plan_path": str(campaign_path),
            "variant_count": len(variants),
            "delivery_count": sum(
                len(variant.get("profile_ids") or campaign["profiles"])
                for variant in variants
            ),
        }
        if inputs.get("run_path"):
            run_path = self._resolve_run_path(inputs)
            run = self._read_json(run_path)
            validate_artifact("batch_run", run)
            data["batch_run"] = run
            data["run_path"] = str(run_path)
        return ToolResult(success=True, data=data)

    def _report(self, inputs: dict[str, Any]) -> ToolResult:
        run_path = self._resolve_run_path(inputs)
        run = self._read_json(run_path)
        validate_artifact("batch_run", run)
        campaign_path = Path(run["campaign_plan_path"])
        project_dir = self._project_dir(inputs, campaign_path)
        report_path = self._write_report(run, project_dir)
        return ToolResult(
            success=True,
            data={
                "batch_run": run,
                "run_path": str(run_path),
                "report_path": str(report_path),
                "files_written": [str(report_path)],
            },
            artifacts=[str(report_path)],
        )

    def _materialize_variants(self, campaign: dict[str, Any]) -> list[dict[str, Any]]:
        mode = campaign["experiment"]["mode"]
        if mode == "explicit":
            variants = deepcopy(campaign["variants"])
            if not variants:
                raise ValueError("Explicit experiment requires at least one variant")
            return variants

        if campaign["variants"]:
            raise ValueError("full_factorial mode must leave variants empty")
        by_role = {
            role: [module for module in campaign["modules"] if module["role"] == role]
            for role in ("hook", "body", "cta")
        }
        variants = []
        for hook, body, cta in itertools.product(
            by_role["hook"], by_role["body"], by_role["cta"]
        ):
            variant_id = f"{hook['id']}-{body['id']}-{cta['id']}"
            variants.append(
                {
                    "id": variant_id,
                    "selection": {
                        "hook": hook["id"],
                        "body": body["id"],
                        "cta": cta["id"],
                    },
                }
            )
        return variants

    def _validate_run_inputs(
        self,
        *,
        run: dict[str, Any],
        campaign: dict[str, Any],
        variant_lookup: dict[str, dict[str, Any]],
        module_lookup: dict[str, dict[str, Any]],
        profile_lookup: dict[str, dict[str, Any]],
        project_dir: Path,
    ) -> None:
        for job in run["jobs"]:
            variant = variant_lookup.get(job["variant_id"])
            profile = profile_lookup.get(job["profile_id"])
            if variant is None or profile is None:
                raise ValueError(
                    f"Batch job {job['id']} no longer matches the campaign plan; "
                    "run operation=plan again"
                )
            modules = [module_lookup[module_id] for module_id in job["module_ids"]]
            current_hash = self._job_input_hash(
                campaign=campaign,
                variant=variant,
                modules=modules,
                profile=profile,
                project_dir=project_dir,
            )
            if current_hash != job["input_hash"]:
                raise ValueError(
                    f"Inputs changed for job {job['id']}; run operation=plan again"
                )

    def _validate_semantics(
        self,
        campaign: dict[str, Any],
        variants: list[dict[str, Any]],
        project_dir: Path,
    ) -> None:
        modules = campaign["modules"]
        module_ids = [module["id"] for module in modules]
        if len(module_ids) != len(set(module_ids)):
            raise ValueError("Campaign module IDs must be unique")
        module_lookup = {module["id"]: module for module in modules}
        for role in ("hook", "body", "cta"):
            if not any(module["role"] == role for module in modules):
                raise ValueError(f"Campaign must define at least one {role} module")

        profile_ids = [profile["id"] for profile in campaign["profiles"]]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("Campaign profile IDs must be unique")
        profile_lookup = {profile["id"]: profile for profile in campaign["profiles"]}
        for profile in campaign["profiles"]:
            if profile["width"] % 2 or profile["height"] % 2:
                raise ValueError(f"Profile {profile['id']} dimensions must be even")

        variant_ids = [variant["id"] for variant in variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("Campaign variant IDs must be unique")
        for variant in variants:
            selection = variant["selection"]
            for role in ("hook", "body", "cta"):
                module_id = selection[role]
                if module_id not in module_lookup:
                    raise ValueError(
                        f"Variant {variant['id']} references unknown module {module_id}"
                    )
                actual_role = module_lookup[module_id]["role"]
                if actual_role != role:
                    raise ValueError(
                        f"Variant {variant['id']} uses {module_id} as {role}, "
                        f"but the module role is {actual_role}"
                    )
            for profile_id in variant.get("profile_ids") or profile_ids:
                if profile_id not in profile_lookup:
                    raise ValueError(
                        f"Variant {variant['id']} references unknown profile {profile_id}"
                    )

        experiment = campaign["experiment"]
        control_id = experiment.get("control_variant_id")
        max_changes = experiment.get("max_changed_dimensions")
        if control_id:
            variant_lookup = {variant["id"]: variant for variant in variants}
            if control_id not in variant_lookup:
                raise ValueError(f"Unknown control variant: {control_id}")
            if max_changes is not None:
                control = variant_lookup[control_id]["selection"]
                for variant in variants:
                    changes = sum(
                        variant["selection"][role] != control[role]
                        for role in ("hook", "body", "cta")
                    )
                    if changes > max_changes:
                        raise ValueError(
                            f"Variant {variant['id']} changes {changes} dimensions "
                            f"from control {control_id}; maximum is {max_changes}"
                        )

        for module in modules:
            default_source = self._resolve_project_path(project_dir, module["source_path"])
            if not default_source.is_file():
                raise ValueError(
                    f"Module {module['id']} source not found: {default_source}"
                )
            trim = module.get("trim")
            if trim and trim["end_seconds"] <= trim["start_seconds"]:
                raise ValueError(
                    f"Module {module['id']} trim end must be after trim start"
                )
            captions_path = module.get("captions_path")
            if captions_path:
                resolved_captions = self._resolve_project_path(project_dir, captions_path)
                if not resolved_captions.is_file():
                    raise ValueError(
                        f"Module {module['id']} captions not found: {resolved_captions}"
                    )
            for profile_id, profile_source in (module.get("profile_sources") or {}).items():
                if profile_id not in profile_lookup:
                    raise ValueError(
                        f"Module {module['id']} has source for unknown profile {profile_id}"
                    )
                resolved_source = self._resolve_project_path(project_dir, profile_source)
                if not resolved_source.is_file():
                    raise ValueError(
                        f"Module {module['id']} profile source not found: {resolved_source}"
                    )

        for profile in campaign["profiles"]:
            if profile["fit"] != "reflow":
                continue
            for module in modules:
                if profile["id"] not in (module.get("profile_sources") or {}):
                    raise ValueError(
                        f"Profile {profile['id']} requires reflow source for module "
                        f"{module['id']}"
                    )

    def _build_run(
        self,
        *,
        campaign: dict[str, Any],
        variants: list[dict[str, Any]],
        project_dir: Path,
        campaign_plan_path: Path,
        old_run: dict[str, Any] | None,
    ) -> dict[str, Any]:
        profile_lookup = {profile["id"]: profile for profile in campaign["profiles"]}
        module_lookup = {module["id"]: module for module in campaign["modules"]}
        output_root = self._resolve_project_path(project_dir, campaign["output_dir"])
        old_jobs = {
            job["id"]: job
            for job in (old_run or {}).get("jobs", [])
        }
        jobs = []
        for variant in variants:
            selection = variant["selection"]
            module_ids = [
                selection["hook"],
                selection["body"],
                selection["cta"],
            ]
            requested_profiles = variant.get("profile_ids") or list(profile_lookup)
            for profile_id in requested_profiles:
                profile = profile_lookup[profile_id]
                modules = [module_lookup[module_id] for module_id in module_ids]
                input_hash = self._job_input_hash(
                    campaign=campaign,
                    variant=variant,
                    modules=modules,
                    profile=profile,
                    project_dir=project_dir,
                )
                job_id = f"{variant['id']}--{profile_id}"
                output_path = output_root / profile_id / f"{variant['id']}.mp4"
                previous = old_jobs.get(job_id)
                keep_passed = (
                    previous is not None
                    and previous.get("input_hash") == input_hash
                    and previous.get("status") == "qa_passed"
                    and previous.get("output_path") == str(output_path)
                    and self._job_is_cached(previous)
                )
                if keep_passed:
                    job = deepcopy(previous)
                else:
                    job = {
                        "id": job_id,
                        "variant_id": variant["id"],
                        "profile_id": profile_id,
                        "module_ids": module_ids,
                        "input_hash": input_hash,
                        "output_path": str(output_path),
                        "status": "planned",
                        "attempts": 0,
                    }
                jobs.append(job)

        run = {
            "version": "1.0",
            "campaign_id": campaign["campaign_id"],
            "campaign_plan_path": str(campaign_plan_path),
            "plan_hash": self._json_hash(campaign),
            "jobs": jobs,
            "summary": self._summary(jobs),
            "updated_at": self._now(),
            "metadata": {
                "variant_count": len(variants),
                "profile_count": len(campaign["profiles"]),
                "execution": "sequential-local",
                "creative_decisions_locked": True,
            },
        }
        return run

    def _job_input_hash(
        self,
        *,
        campaign: dict[str, Any],
        variant: dict[str, Any],
        modules: list[dict[str, Any]],
        profile: dict[str, Any],
        project_dir: Path,
    ) -> str:
        source_fingerprints = []
        for module in modules:
            source = self._module_source(module, profile, project_dir)
            fingerprint = {
                "module_id": module["id"],
                "source": str(source),
                "source_sha256": self._file_hash(source),
                "trim": module.get("trim"),
            }
            if module.get("captions_path"):
                captions = self._resolve_project_path(
                    project_dir, module["captions_path"]
                )
                fingerprint["captions_sha256"] = self._file_hash(captions)
                fingerprint["captions_timebase"] = module.get(
                    "captions_timebase", "module"
                )
            source_fingerprints.append(fingerprint)
        payload = {
            "campaign_id": campaign["campaign_id"],
            "variant": variant,
            "profile": profile,
            "sources": source_fingerprints,
            "tool_version": self.version,
        }
        return self._json_hash(payload)

    def _render_job(
        self,
        *,
        modules: list[dict[str, Any]],
        profile: dict[str, Any],
        project_dir: Path,
        output_path: Path,
        job: dict[str, Any],
    ) -> None:
        input_args: list[str] = []
        filter_parts: list[str] = []
        concat_inputs: list[str] = []
        module_durations: list[float] = []
        input_index = 0

        for index, module in enumerate(modules):
            source = self._module_source(module, profile, project_dir)
            media = self._probe_media(source)
            start_seconds, duration_seconds = self._module_window(module, media)
            module_durations.append(duration_seconds)

            if start_seconds > 0:
                input_args.extend(["-ss", self._number(start_seconds)])
            input_args.extend(["-t", self._number(duration_seconds), "-i", str(source)])
            video_index = input_index
            input_index += 1
            if media["has_audio"]:
                audio_index = video_index
            else:
                input_args.extend(
                    [
                        "-f",
                        "lavfi",
                        "-t",
                        self._number(duration_seconds),
                        "-i",
                        "anullsrc=r=48000:cl=stereo",
                    ]
                )
                audio_index = input_index
                input_index += 1

            geometry = self._geometry_filter(profile)
            filter_parts.append(
                f"[{video_index}:v]{geometry},"
                f"trim=duration={self._number(duration_seconds)},"
                f"setpts=PTS-STARTPTS,setsar=1,"
                f"fps={self._number(profile['fps'])},format=yuv420p[v{index}]"
            )
            filter_parts.append(
                f"[{audio_index}:a]aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:"
                "channel_layouts=stereo,"
                f"atrim=duration={self._number(duration_seconds)},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[v{index}][a{index}]")

        filter_parts.append(
            "".join(concat_inputs)
            + f"concat=n={len(modules)}:v=1:a=1[vcat][acat]"
        )
        combined_srt = self._combined_subtitles(
            modules=modules,
            profile=profile,
            project_dir=project_dir,
            module_durations=module_durations,
            output_path=output_path,
            job_id=job["id"],
        )
        video_label = "vcat"
        if combined_srt:
            escaped_srt = self._ffmpeg_filter_path(combined_srt)
            force_style = self._subtitle_style(profile)
            filter_parts.append(
                f"[vcat]subtitles='{escaped_srt}':"
                f"force_style='{force_style}'[vout]"
            )
            video_label = "vout"

        command = [
            "ffmpeg",
            "-y",
            *input_args,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            f"[{video_label}]",
            "-map",
            "[acat]",
            "-c:v",
            profile.get("codec", "libx264"),
            "-crf",
            str(profile.get("crf", 20)),
            "-preset",
            profile.get("preset", "medium"),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            profile.get("audio_bitrate", "192k"),
            "-ar",
            "48000",
            "-movflags",
            "+faststart",
            "-metadata",
            f"campaign_job={job['id']}",
            str(output_path),
        ]
        timeout = max(120, int(sum(module_durations) * 15))
        self.run_command(command, timeout=timeout)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise ValueError(f"FFmpeg produced no output: {output_path}")

    def _combined_subtitles(
        self,
        *,
        modules: list[dict[str, Any]],
        profile: dict[str, Any],
        project_dir: Path,
        module_durations: list[float],
        output_path: Path,
        job_id: str,
    ) -> Path | None:
        cues: list[dict[str, Any]] = []
        offset = 0.0
        for module, duration in zip(modules, module_durations):
            captions_value = module.get("captions_path")
            if captions_value:
                captions_path = self._resolve_project_path(project_dir, captions_value)
                module_cues = self._parse_srt(captions_path)
                if module.get("captions_timebase", "module") == "source":
                    trim = module.get("trim") or {}
                    trim_start = float(trim.get("start_seconds", 0))
                    trim_end = trim_start + duration
                    module_cues = self._trim_cues(
                        module_cues, trim_start, trim_end
                    )
                else:
                    module_cues = self._trim_cues(module_cues, 0, duration)
                for cue in module_cues:
                    cues.append(
                        {
                            "start": cue["start"] + offset,
                            "end": cue["end"] + offset,
                            "text": cue["text"],
                        }
                    )
            offset += duration
        if not cues:
            return None

        work_dir = output_path.parents[1] / ".work"
        work_dir.mkdir(parents=True, exist_ok=True)
        subtitle_path = work_dir / f"{job_id}.srt"
        subtitle_path.write_text(self._render_srt(cues), encoding="utf-8")
        return subtitle_path

    def _parse_srt(self, path: Path) -> list[dict[str, Any]]:
        content = path.read_text(encoding="utf-8-sig")
        blocks = re.split(r"\r?\n\r?\n+", content.strip())
        cues: list[dict[str, Any]] = []
        for block in blocks:
            lines = block.splitlines()
            timing_index = next(
                (index for index, line in enumerate(lines) if "-->" in line),
                None,
            )
            if timing_index is None:
                continue
            match = self._SRT_TIMING.search(lines[timing_index])
            if not match:
                continue
            text = "\n".join(lines[timing_index + 1 :]).strip()
            if not text:
                continue
            cues.append(
                {
                    "start": self._srt_match_seconds(match, "s"),
                    "end": self._srt_match_seconds(match, "e"),
                    "text": text,
                }
            )
        return cues

    @staticmethod
    def _srt_match_seconds(match: re.Match[str], prefix: str) -> float:
        return (
            int(match.group(f"{prefix}h")) * 3600
            + int(match.group(f"{prefix}m")) * 60
            + int(match.group(f"{prefix}s"))
            + int(match.group(f"{prefix}ms")) / 1000
        )

    @staticmethod
    def _trim_cues(
        cues: list[dict[str, Any]],
        start_seconds: float,
        end_seconds: float,
    ) -> list[dict[str, Any]]:
        trimmed = []
        for cue in cues:
            if cue["end"] <= start_seconds or cue["start"] >= end_seconds:
                continue
            trimmed.append(
                {
                    "start": max(cue["start"], start_seconds) - start_seconds,
                    "end": min(cue["end"], end_seconds) - start_seconds,
                    "text": cue["text"],
                }
            )
        return trimmed

    def _render_srt(self, cues: list[dict[str, Any]]) -> str:
        lines = []
        for index, cue in enumerate(cues, start=1):
            lines.extend(
                [
                    str(index),
                    f"{self._srt_time(cue['start'])} --> {self._srt_time(cue['end'])}",
                    cue["text"],
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _srt_time(seconds: float) -> str:
        total_ms = int(round(max(0, seconds) * 1000))
        hours, remainder = divmod(total_ms, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"

    def _qa_output(
        self,
        *,
        output_path: Path,
        profile: dict[str, Any],
        expected_duration: float,
    ) -> dict[str, Any]:
        media = self._probe_media(output_path, refresh=True)
        issues = []
        if media["width"] != profile["width"] or media["height"] != profile["height"]:
            issues.append(
                f"resolution {media['width']}x{media['height']} does not match "
                f"{profile['width']}x{profile['height']}"
            )
        if media["video_codec"] != "h264":
            issues.append(f"unexpected video codec: {media['video_codec']}")
        if media["audio_codec"] != "aac":
            issues.append(f"unexpected audio codec: {media['audio_codec']}")
        if media["pixel_format"] != "yuv420p":
            issues.append(f"unexpected pixel format: {media['pixel_format']}")
        duration_delta = abs(media["duration_seconds"] - expected_duration)
        if duration_delta > 0.2:
            issues.append(
                f"duration differs by {duration_delta:.3f}s from expected"
            )

        decode_clean = True
        try:
            self.run_command(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-i",
                    str(output_path),
                    "-f",
                    "null",
                    "-",
                ],
                timeout=max(120, int(expected_duration * 10)),
            )
        except Exception as exc:
            decode_clean = False
            issues.append(f"decode failed: {exc}")

        faststart = self._has_faststart(output_path)
        if not faststart:
            issues.append("MP4 moov atom is not before mdat")
        checksum = self._file_hash(output_path, refresh=True)
        return {
            "passed": not issues,
            "issues": issues,
            "resolution": f"{media['width']}x{media['height']}",
            "video_codec": media["video_codec"],
            "audio_codec": media["audio_codec"],
            "pixel_format": media["pixel_format"],
            "duration_seconds": media["duration_seconds"],
            "expected_duration_seconds": round(expected_duration, 3),
            "file_size_bytes": output_path.stat().st_size,
            "sha256": checksum,
            "decode_clean": decode_clean,
            "faststart": faststart,
        }

    def _probe_media(self, path: Path, *, refresh: bool = False) -> dict[str, Any]:
        cache_key = str(path.resolve())
        if not refresh and cache_key in self._media_cache:
            return self._media_cache[cache_key]
        result = self.run_command(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,pix_fmt",
                "-of",
                "json",
                str(path),
            ],
            timeout=30,
        )
        payload = json.loads(result.stdout)
        streams = payload.get("streams") or []
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            {},
        )
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            {},
        )
        media = {
            "duration_seconds": float(payload.get("format", {}).get("duration", 0)),
            "has_audio": bool(audio),
            "width": int(video.get("width", 0)),
            "height": int(video.get("height", 0)),
            "video_codec": video.get("codec_name"),
            "audio_codec": audio.get("codec_name"),
            "pixel_format": video.get("pix_fmt"),
        }
        if not video or media["duration_seconds"] <= 0:
            raise ValueError(f"Invalid video module: {path}")
        self._media_cache[cache_key] = media
        return media

    def _modules_duration(
        self,
        modules: list[dict[str, Any]],
        profile: dict[str, Any],
        project_dir: Path,
    ) -> float:
        return sum(
            self._module_window(
                module,
                self._probe_media(self._module_source(module, profile, project_dir)),
            )[1]
            for module in modules
        )

    @staticmethod
    def _module_window(
        module: dict[str, Any],
        media: dict[str, Any],
    ) -> tuple[float, float]:
        trim = module.get("trim") or {}
        start = float(trim.get("start_seconds", 0))
        end = float(trim.get("end_seconds", media["duration_seconds"]))
        if end <= start:
            raise ValueError(f"Module {module['id']} has an invalid trim window")
        if end > media["duration_seconds"] + 0.25:
            raise ValueError(
                f"Module {module['id']} trim ends at {end:.3f}s, "
                f"source duration is {media['duration_seconds']:.3f}s"
            )
        return start, end - start

    def _module_source(
        self,
        module: dict[str, Any],
        profile: dict[str, Any],
        project_dir: Path,
    ) -> Path:
        profile_sources = module.get("profile_sources") or {}
        source_value = profile_sources.get(profile["id"], module["source_path"])
        if profile["fit"] == "reflow" and profile["id"] not in profile_sources:
            raise ValueError(
                f"Profile {profile['id']} requires a reflow source for module "
                f"{module['id']}"
            )
        source = self._resolve_project_path(project_dir, source_value)
        if not source.is_file():
            raise ValueError(f"Module source not found: {source}")
        return source

    @staticmethod
    def _geometry_filter(profile: dict[str, Any]) -> str:
        width = profile["width"]
        height = profile["height"]
        fit = profile["fit"]
        if fit in {"contain", "reflow"}:
            color = CampaignBatch._ffmpeg_color(
                profile.get("background_color", "#000000")
            )
            return (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={color}"
            )
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

    @staticmethod
    def _subtitle_style(profile: dict[str, Any]) -> str:
        style = {
            "font": "Arial",
            "font_size": 38 if profile["height"] >= profile["width"] else 30,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "outline_width": 3,
            "margin_v": 120 if profile["height"] > profile["width"] else 60,
            "alignment": 2,
            **(profile.get("subtitle_style") or {}),
        }
        return ",".join(
            [
                f"FontName={style['font']}",
                f"FontSize={style['font_size']}",
                f"PrimaryColour={style['primary_color']}",
                f"OutlineColour={style['outline_color']}",
                f"Outline={style['outline_width']}",
                f"MarginV={style['margin_v']}",
                f"Alignment={style['alignment']}",
            ]
        )

    def _job_is_cached(self, job: dict[str, Any]) -> bool:
        if job.get("status") != "qa_passed":
            return False
        output_path = Path(job["output_path"])
        qa = job.get("qa") or {}
        expected_hash = qa.get("sha256")
        if not output_path.is_file() or not expected_hash:
            return False
        return self._file_hash(output_path) == expected_hash

    def _write_report(self, run: dict[str, Any], project_dir: Path) -> Path:
        report_path = project_dir / "reports" / "batch-report.json"
        report = {
            "version": "1.0",
            "campaign_id": run["campaign_id"],
            "summary": run["summary"],
            "updated_at": run["updated_at"],
            "jobs": [
                {
                    "id": job["id"],
                    "variant_id": job["variant_id"],
                    "profile_id": job["profile_id"],
                    "module_ids": job["module_ids"],
                    "status": job["status"],
                    "attempts": job["attempts"],
                    "output_path": job["output_path"],
                    "error": job.get("error"),
                    "qa": job.get("qa"),
                }
                for job in run["jobs"]
            ],
        }
        self._write_json(report_path, report)
        return report_path

    @staticmethod
    def _summary(jobs: list[dict[str, Any]]) -> dict[str, int]:
        summary = {
            "total": len(jobs),
            "planned": 0,
            "running": 0,
            "qa_passed": 0,
            "failed": 0,
        }
        for job in jobs:
            summary[job["status"]] += 1
        return summary

    def _refresh_run(self, run: dict[str, Any]) -> None:
        run["summary"] = self._summary(run["jobs"])
        run["updated_at"] = self._now()
        validate_artifact("batch_run", run)

    def _write_run(self, path: Path, run: dict[str, Any]) -> None:
        validate_artifact("batch_run", run)
        self._write_json(path, run)

    @staticmethod
    def _project_dir(inputs: dict[str, Any], campaign_path: Path) -> Path:
        if inputs.get("project_dir"):
            return Path(inputs["project_dir"]).expanduser().resolve()
        if campaign_path.parent.name == "artifacts":
            return campaign_path.parent.parent.resolve()
        return campaign_path.parent.resolve()

    def _resolve_run_path(self, inputs: dict[str, Any]) -> Path:
        if inputs.get("run_path"):
            path = Path(inputs["run_path"]).expanduser()
            if not path.is_absolute() and inputs.get("project_dir"):
                path = Path(inputs["project_dir"]) / path
            if not path.is_file():
                raise ValueError(f"run_path not found: {path}")
            return path.resolve()
        campaign_path = self._required_path(inputs, "campaign_path")
        project_dir = self._project_dir(inputs, campaign_path)
        path = project_dir / "artifacts" / "batch_run.json"
        if not path.is_file():
            raise ValueError(f"run_path not found: {path}")
        return path

    @staticmethod
    def _required_path(inputs: dict[str, Any], key: str) -> Path:
        value = inputs.get(key)
        if not value:
            raise ValueError(f"{key} is required")
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(f"{key} not found: {path}")
        return path.resolve()

    @staticmethod
    def _resolve_project_path(project_dir: Path, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path.resolve() if path.is_absolute() else (project_dir / path).resolve()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _json_hash(value: Any) -> str:
        raw = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _file_hash(self, path: Path, *, refresh: bool = False) -> str:
        key = str(path.resolve())
        if not refresh and key in self._file_hash_cache:
            return self._file_hash_cache[key]
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        value = digest.hexdigest()
        self._file_hash_cache[key] = value
        return value

    @staticmethod
    def _has_faststart(path: Path) -> bool:
        with path.open("rb") as handle:
            prefix = handle.read(2 * 1024 * 1024)
        moov = prefix.find(b"moov")
        mdat = prefix.find(b"mdat")
        return moov >= 0 and mdat >= 0 and moov < mdat

    @staticmethod
    def _ffmpeg_filter_path(path: Path) -> str:
        return (
            str(path.resolve())
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "\\'")
        )

    @staticmethod
    def _ffmpeg_color(value: str) -> str:
        return f"0x{value[1:]}" if value.startswith("#") else value

    @staticmethod
    def _number(value: float | int) -> str:
        return f"{float(value):.6f}".rstrip("0").rstrip(".")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
