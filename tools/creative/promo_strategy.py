"""Pain-first creative strategy gates for product promotion videos."""

from __future__ import annotations

import json
import re
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


class PromoStrategy(BaseTool):
    """Rank pains, enforce the three-second hook gate, and close the learning loop."""

    name = "promo_strategy"
    version = "1.1.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT
    capability = "promotion_strategy"
    provider = "openmontage"
    capabilities = [
        "pain_ranking",
        "three_second_hook_gate",
        "audience_job_validation",
        "script_quality_gate",
        "promotion_contract_validation",
        "creative_metric_diagnosis",
    ]
    best_for = [
        "Ranking an evidence-linked library of consumer pains",
        "Rejecting hooks that hide the pain, lack support, break their body promise, or exceed three seconds",
        "Checking audience job, pain, claim, proof, script quality, and CTA references before rendering",
        "Turning hold, click, and conversion metrics into the next creative action",
    ]
    not_good_for = ["Inventing product claims", "Writing copy without evidence"]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["rank_pains", "evaluate_hooks", "validate_campaign", "diagnose"]},
            "pain_library_path": {"type": "string"},
            "hook_candidates_path": {"type": "string"},
            "product_truth_path": {"type": "string"},
            "audience_job_path": {"type": "string"},
            "value_map_path": {"type": "string"},
            "creative_brief_path": {"type": "string"},
            "script_path": {"type": "string"},
            "script_qa_report_path": {"type": "string"},
            "proof_plan_path": {"type": "string"},
            "output_path": {"type": "string"},
            "top_n": {"type": "integer", "minimum": 1, "maximum": 5},
            "brand_names": {"type": "array", "items": {"type": "string"}},
            "words_per_second": {"type": "number", "exclusiveMinimum": 0},
            "max_hook_seconds": {"type": "number", "exclusiveMinimum": 0},
            "metrics": {"type": "object"},
            "thresholds": {"type": "object"},
            "experiment_id": {"type": "string"},
            "creative_id": {"type": "string"},
            "platform": {"type": "string"}
        }
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=16, network_required=False)
    user_visible_verification = [
        "Confirm selected pains are the highest ranked evidence-linked entries",
        "Confirm every selected hook passes credibility, payoff, speakability, and three-second gates",
        "Confirm the selected audience job and script quality report pass before proof planning",
        "Confirm every persuasive claim has a concrete proof scene",
    ]

    _PAIN_MARKERS = (
        "tired", "wast", "stuck", "frustrat", "can't", "cannot", "hard",
        "slow", "wrong", "too many", "every time", "before you", "still",
        "stop", "paying", "guess", "expensive", "cost", "confus", "redo", "rebuild",
    )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            operation = inputs["operation"]
            if operation == "rank_pains":
                return self._rank_pains(inputs)
            if operation == "evaluate_hooks":
                return self._evaluate_hooks(inputs)
            if operation == "validate_campaign":
                return self._validate_campaign(inputs)
            if operation == "diagnose":
                return self._diagnose(inputs)
            return ToolResult(success=False, error=f"Unsupported operation: {operation}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"promotion strategy failed: {exc}")

    def _rank_pains(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._required_path(inputs, "pain_library_path")
        ranked = deepcopy(self._read_json(path))
        seen: set[str] = set()
        for pain in ranked.get("pains", []):
            pain_id = pain["id"]
            if pain_id in seen:
                raise ValueError(f"Duplicate pain id: {pain_id}")
            seen.add(pain_id)
            scores = pain["scores"]
            scores["total"] = round(sum(float(scores[key]) for key in (
                "frequency", "urgency", "severity", "commercial_intent", "confidence"
            )), 3)
        ranked["pains"].sort(key=lambda pain: (
            -pain["scores"]["total"], -pain["scores"]["commercial_intent"], pain["id"]
        ))
        for index, pain in enumerate(ranked["pains"], start=1):
            pain["rank"] = index
        top_n = int(inputs.get("top_n", 5))
        ranked["selected_pain_ids"] = [pain["id"] for pain in ranked["pains"][:top_n]]
        validate_artifact("pain_library", ranked)
        output = Path(inputs.get("output_path") or path)
        self._write_json(output, ranked)
        return ToolResult(success=True, data={
            "pain_library": ranked,
            "selected_pain_ids": ranked["selected_pain_ids"],
            "output_path": str(output),
        }, artifacts=[str(output)])

    def _evaluate_hooks(self, inputs: dict[str, Any]) -> ToolResult:
        path = self._required_path(inputs, "hook_candidates_path")
        evaluated = deepcopy(self._read_json(path))
        validate_artifact("hook_candidates", evaluated)
        words_per_second = float(inputs.get("words_per_second", 2.5))
        max_seconds = float(inputs.get("max_hook_seconds", 3.0))
        brands = [name.lower().strip() for name in inputs.get("brand_names", []) if name.strip()]
        failures: list[dict[str, Any]] = []
        strict_quality = evaluated.get("version") == "1.1"
        for candidate in evaluated["candidates"]:
            text = candidate["text"].strip()
            word_count = len(re.findall(r"\b[\w']+\b", text))
            speakability = candidate.get("speakability") or {}
            if strict_quality and speakability.get("duration_source") != "estimated":
                duration = float(speakability["duration_seconds"])
            else:
                duration = float(candidate.get("spoken_duration_seconds") or word_count / words_per_second)
                if strict_quality:
                    speakability["duration_seconds"] = round(duration, 3)
            candidate["spoken_duration_seconds"] = round(duration, 3)
            if strict_quality:
                speakability["word_count"] = word_count
            lower = text.lower()
            brand_first = any(lower.startswith(name) for name in brands)
            pain_is_explicit = bool(candidate.get("pain_id")) and any(marker in lower for marker in self._PAIN_MARKERS)
            visual_sync = bool(candidate.get("first_frame", "").strip())
            evidence_refs = set(candidate.get("evidence_refs") or [])
            credibility_refs = set((candidate.get("credibility") or {}).get("source_refs") or [])
            credibility_supported = not strict_quality or bool(credibility_refs) and credibility_refs.issubset(evidence_refs)
            body_payoff_matches = not strict_quality or bool((candidate.get("body_payoff") or {}).get("matches"))
            speakability_passes = not strict_quality or (
                bool(speakability.get("passes")) and duration <= max_seconds
            )
            passes = all((
                duration <= max_seconds,
                pain_is_explicit,
                not brand_first,
                visual_sync,
                credibility_supported,
                body_payoff_matches,
                speakability_passes,
            ))
            notes = self._hook_notes(
                duration,
                max_seconds,
                pain_is_explicit,
                brand_first,
                visual_sync,
                credibility_supported,
                body_payoff_matches,
                speakability_passes,
            )
            candidate["three_second_gate"] = {
                "passes": passes,
                "pain_is_explicit": pain_is_explicit,
                "brand_first": brand_first,
                "visual_sync": visual_sync,
                "credibility_supported": credibility_supported,
                "body_payoff_matches": body_payoff_matches,
                "speakability_passes": speakability_passes,
                "notes": notes,
            }
            if not passes:
                failures.append({"id": candidate["id"], "notes": notes})
        selected = set(evaluated.get("selected_ids") or [])
        if evaluated.get("selected_id"):
            selected.add(evaluated["selected_id"])
        selected_failures = [failure for failure in failures if failure["id"] in selected]
        validate_artifact("hook_candidates", evaluated)
        output = Path(inputs.get("output_path") or path)
        self._write_json(output, evaluated)
        return ToolResult(
            success=not selected_failures,
            data={
                "hook_candidates": evaluated,
                "passed_count": len(evaluated["candidates"]) - len(failures),
                "failed_count": len(failures),
                "failures": failures,
                "selected_failures": selected_failures,
                "output_path": str(output),
            },
            artifacts=[str(output)],
            error=f"Selected hooks failed the three-second gate: {selected_failures}" if selected_failures else None,
        )

    def _validate_campaign(self, inputs: dict[str, Any]) -> ToolResult:
        names = ("product_truth", "pain_library", "value_map", "hook_candidates", "creative_brief", "proof_plan")
        artifacts: dict[str, dict[str, Any]] = {}
        for name in names:
            path = self._required_path(inputs, f"{name}_path")
            artifact = self._read_json(path)
            validate_artifact(name, artifact)
            artifacts[name] = artifact
        hook_version = artifacts["hook_candidates"].get("version")
        brief_version = artifacts["creative_brief"].get("version")
        strict_contract = hook_version == "1.1" or brief_version == "1.1"
        if strict_contract and hook_version != brief_version:
            raise ValueError("Hook candidates and creative brief must use the same contract version")
        if strict_contract:
            for name in ("audience_job", "script", "script_qa_report"):
                path = self._required_path(inputs, f"{name}_path")
                artifact = self._read_json(path)
                validate_artifact(name, artifact)
                artifacts[name] = artifact
        truth = artifacts["product_truth"]
        pains = {pain["id"]: pain for pain in artifacts["pain_library"]["pains"]}
        claims = {claim["id"]: claim for claim in truth["claims"]}
        mappings = {item["id"]: item for item in artifacts["value_map"]["mappings"]}
        hooks = {item["id"]: item for item in artifacts["hook_candidates"]["candidates"]}
        brief = artifacts["creative_brief"]
        if brief["product_id"] != truth["product_id"]:
            raise ValueError("Creative brief product_id does not match product truth")
        if brief["pain_id"] not in pains:
            raise ValueError(f"Unknown creative pain_id: {brief['pain_id']}")
        if "audience_job" in artifacts:
            if artifacts["audience_job"]["product_id"] != truth["product_id"]:
                raise ValueError("Audience job product_id does not match product truth")
            profiles = {profile["id"]: profile for profile in artifacts["audience_job"]["profiles"]}
            profile = profiles.get(brief.get("audience_job_id"))
            if profile is None:
                raise ValueError("Creative brief audience_job_id does not exist")
            if brief["pain_id"] not in profile["pain_ids"]:
                raise ValueError("Creative audience job does not match the selected pain")
            if profile["id"] not in artifacts["audience_job"]["selected_profile_ids"]:
                raise ValueError("Creative audience job has not been selected")
        mapping = mappings.get(brief["value_mapping_id"])
        if mapping is None or mapping["pain_id"] != brief["pain_id"]:
            raise ValueError("Creative value mapping does not match the selected pain")
        for claim_id in mapping["claim_ids"]:
            claim = claims.get(claim_id)
            if claim is None:
                raise ValueError(f"Unknown product claim: {claim_id}")
            if claim["status"] == "unverified":
                raise ValueError(f"Selected mapping uses unverified claim: {claim_id}")
        hook = hooks.get(brief["hook_id"])
        if hook is None or hook.get("pain_id") != brief["pain_id"]:
            raise ValueError("Creative hook does not match the selected pain")
        if not (hook.get("three_second_gate") or {}).get("passes"):
            raise ValueError("Selected hook has not passed the three-second gate")
        if "script" in artifacts:
            script = artifacts["script"]
            if script["sections"][0]["text"].strip() != hook["text"].strip():
                raise ValueError("Production script does not use the approved hook verbatim")
            qa_report = artifacts["script_qa_report"]
            if qa_report["language"] != brief["language"]:
                raise ValueError("Script QA language does not match the creative brief")
            if qa_report["desired_viewer_response"] != brief["desired_viewer_response"]:
                raise ValueError("Script QA viewer response does not match the creative brief")
            failed_checks = [name for name, check in qa_report["checks"].items() if not check["passes"]]
            if qa_report["overall_status"] != "pass" or failed_checks:
                raise ValueError(f"Script quality gate has not passed: {failed_checks}")
            if qa_report["approval"]["status"] not in {"approved", "approved_with_changes"}:
                raise ValueError("Script quality report has not been approved")
        structure = brief["structure"]
        if structure[0]["beat"] != "hook" or structure[0]["start_seconds"] != 0:
            raise ValueError("Creative structure must start with a hook at 0 seconds")
        if structure[0]["end_seconds"] > 3:
            raise ValueError("Creative hook must end by 3 seconds")
        if structure[-1]["beat"] != "cta":
            raise ValueError("Creative structure must end with a CTA")
        previous_end = 0.0
        for beat in structure:
            if beat["start_seconds"] < previous_end or beat["end_seconds"] <= beat["start_seconds"]:
                raise ValueError("Creative structure contains an invalid or overlapping time range")
            previous_end = beat["end_seconds"]
        if previous_end > brief["duration_seconds"] + 0.05:
            raise ValueError("Creative structure exceeds the approved duration")
        proof_claims = {claim for scene in artifacts["proof_plan"]["scenes"] for claim in scene["claim_refs"]}
        missing = sorted(set(mapping["claim_ids"]) - proof_claims)
        if missing:
            raise ValueError(f"Claims without proof scenes: {missing}")
        return ToolResult(success=True, data={
            "creative_id": brief["creative_id"],
            "pain_id": brief["pain_id"],
            "claim_ids": mapping["claim_ids"],
            "hook_id": brief["hook_id"],
            "audience_job_id": brief.get("audience_job_id"),
            "script_qa_status": (artifacts.get("script_qa_report") or {}).get("overall_status"),
            "proof_scene_count": len(artifacts["proof_plan"]["scenes"]),
            "status": "ready_for_production",
        })

    def _diagnose(self, inputs: dict[str, Any]) -> ToolResult:
        metrics = deepcopy(inputs.get("metrics") or {})
        required = ("impressions", "three_second_views", "outbound_clicks", "conversions", "spend")
        missing = [key for key in required if key not in metrics]
        if missing:
            raise ValueError(f"Missing metrics: {', '.join(missing)}")
        impressions = int(metrics["impressions"])
        views = int(metrics["three_second_views"])
        clicks = int(metrics["outbound_clicks"])
        conversions = int(metrics["conversions"])
        thresholds = {
            "minimum_impressions": 500,
            "minimum_hold_rate": 0.25,
            "minimum_outbound_ctr": 0.01,
            "minimum_conversion_rate": 0.02,
            **(inputs.get("thresholds") or {}),
        }
        hold_rate = views / impressions if impressions else None
        outbound_ctr = clicks / impressions if impressions else None
        conversion_rate = conversions / clicks if clicks else None
        metrics.update({
            "hold_rate": hold_rate,
            "outbound_ctr": outbound_ctr,
            "conversion_rate": conversion_rate,
            "currency": metrics.get("currency", "USD"),
        })
        if impressions < int(thresholds["minimum_impressions"]):
            diagnosis, action = "insufficient_data", "Collect more impressions before changing the creative."
        elif hold_rate is None or hold_rate < float(thresholds["minimum_hold_rate"]):
            diagnosis, action = "hook_problem", "Keep the body and offer fixed; test a new pain-led hook and first frame."
        elif outbound_ctr is None or outbound_ctr < float(thresholds["minimum_outbound_ctr"]):
            diagnosis, action = "message_or_proof_problem", "Keep the hook fixed; strengthen the solution explanation and product proof."
        elif conversion_rate is None or conversion_rate < float(thresholds["minimum_conversion_rate"]):
            diagnosis, action = "offer_or_landing_problem", "Keep the creative fixed; audit CTA, offer, trust, and landing-page continuity."
        else:
            diagnosis, action = "creative_candidate", "Promote this creative to control and test one new variable against it."
        result = {
            "version": "1.0",
            "experiment_id": inputs.get("experiment_id", "experiment-local"),
            "creative_id": inputs.get("creative_id", "creative-local"),
            "platform": inputs.get("platform", "unknown"),
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "diagnosis": diagnosis,
            "next_action": action,
            "metadata": {"thresholds": thresholds},
        }
        validate_artifact("experiment_result", result)
        artifacts: list[str] = []
        if inputs.get("output_path"):
            output = Path(inputs["output_path"])
            self._write_json(output, result)
            artifacts.append(str(output))
        return ToolResult(success=True, data={"experiment_result": result}, artifacts=artifacts)

    @staticmethod
    def _hook_notes(
        duration: float,
        max_seconds: float,
        pain: bool,
        brand: bool,
        visual: bool,
        credibility: bool,
        payoff: bool,
        speakability: bool,
    ) -> str:
        issues = []
        if duration > max_seconds:
            issues.append(f"spoken duration is {duration:.2f}s")
        if not pain:
            issues.append("pain is not explicit in consumer language")
        if brand:
            issues.append("hook starts with the brand")
        if not visual:
            issues.append("first frame is missing")
        if not credibility:
            issues.append("credibility references are missing or outside the evidence set")
        if not payoff:
            issues.append("body payoff does not match the opening promise")
        if not speakability:
            issues.append("spoken delivery gate failed")
        return "; ".join(issues) if issues else "passes duration, pain, brand, visual, credibility, payoff, and speakability gates"

    @staticmethod
    def _required_path(inputs: dict[str, Any], key: str) -> Path:
        value = inputs.get(key)
        if not value:
            raise ValueError(f"{key} is required")
        path = Path(value)
        if not path.is_file():
            raise ValueError(f"File not found: {path}")
        return path

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
