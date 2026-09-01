"""Contracts for the pain-first product promotion factory."""

from __future__ import annotations

import json
from pathlib import Path

from lib.pipeline_loader import get_stage_order, list_pipelines, load_pipeline
from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.creative.promo_strategy import PromoStrategy
from tools.tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parent.parent.parent


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _pain_library() -> dict:
    pains = []
    for index in range(1, 21):
        pains.append(
            {
                "id": f"pain-{index:02d}",
                "statement": f"The user is unsure which model fits job {index}.",
                "user_language": f"I am tired of guessing which model fits job {index}.",
                "persona": "Independent creator",
                "situation": "Starting a new visual generation task",
                "job_to_be_done": "Choose a suitable model before spending credits",
                "awareness_stage": "problem_aware",
                "evidence_refs": [f"source-{index:02d}"],
                "scores": {
                    "frequency": 5 if index == 1 else 3,
                    "urgency": 5 if index == 1 else 3,
                    "severity": 4 if index == 1 else 3,
                    "commercial_intent": 5 if index == 1 else 3,
                    "confidence": 5 if index == 1 else 3,
                    "total": 0,
                },
                "rank": index,
            }
        )
    return {
        "version": "1.0",
        "product_id": "vibeaha",
        "audience": "Independent creators comparing AI image and video models",
        "research_date": "2026-08-06",
        "ranking_method": "Five equal-weight evidence and demand dimensions",
        "pains": pains,
    }


def _audience_job() -> dict:
    return {
        "version": "1.0",
        "product_id": "vibeaha",
        "audience": "Independent creators comparing AI image and video models",
        "profiles": [
            {
                "id": "job-model-choice",
                "pain_ids": ["pain-01"],
                "situation": "Starting a visual generation task with limited credits",
                "desired_progress": "Choose a suitable model before paying for a generation",
                "job_statement": "Choose the model that fits the current creative task without trial-and-error spending.",
                "job_dimensions": {
                    "functional": ["Compare model fit before generation"],
                    "emotional": ["Feel confident before spending credits"],
                    "social": ["Deliver reliable work to a client"],
                },
                "switching_forces": {
                    "push": ["Repeated credit waste from guessing"],
                    "pull": ["Visible model choices in one workspace"],
                    "anxiety": ["A comparison may still not predict the result"],
                    "habit": ["Reusing the last familiar model"],
                },
                "choice_criteria": [
                    {
                        "criterion": "Model options are visible before generation",
                        "observable_signal": "The product screen shows multiple selectable models",
                        "evidence_refs": ["source-home"],
                    }
                ],
                "evidence_refs": ["pain-01", "source-01", "source-home"],
                "confidence": 4,
                "unknowns": ["How often users switch models after comparing"],
            }
        ],
        "selected_profile_ids": ["job-model-choice"],
        "approval": {"status": "approved", "notes": "Evidence-linked campaign job"},
    }


def _campaign_artifacts(tmp_path: Path) -> dict[str, Path]:
    truth = {
        "version": "1.0",
        "product_id": "vibeaha",
        "product_name": "VibeAha",
        "canonical_url": "https://vibeaha.com/",
        "captured_at": "2026-08-06T00:00:00Z",
        "audience": "Independent creators comparing AI image and video models",
        "claims": [
            {
                "id": "claim-model-choice",
                "kind": "feature",
                "statement": "The product exposes multiple generation models.",
                "consumer_value": "Creators can choose a model for the job.",
                "status": "verified",
                "limitations": [],
                "evidence_refs": ["source-home"],
            }
        ],
        "sources": [
            {
                "id": "source-home",
                "url": "https://vibeaha.com/",
                "title": "VibeAha",
                "kind": "product_page",
                "captured_at": "2026-08-06T00:00:00Z",
                "local_path": "capture/home.png",
            }
        ],
    }
    pains = _pain_library()
    pains["pains"][0]["scores"]["total"] = 24
    pains["selected_pain_ids"] = ["pain-01"]
    audience_job = _audience_job()
    value_map = {
        "version": "1.0",
        "product_id": "vibeaha",
        "mappings": [
            {
                "id": "map-choice",
                "pain_id": "pain-01",
                "claim_ids": ["claim-model-choice"],
                "promise": "Make model choice deliberate instead of random.",
                "solution": "Compare available models before generating.",
                "proof_refs": ["source-home"],
                "cta": "Compare before you create.",
                "format_fits": ["hybrid", "screen_demo"],
                "scores": {"pain_fit": 5, "claim_truth": 5, "proof_strength": 5, "visual_potential": 5, "total": 20},
            }
        ],
        "selected_mapping_id": "map-choice",
    }
    hook_texts = [
        ("hook-guessing", "Tired of guessing which AI model fits?", "direct_pain"),
        ("hook-wasting", "Still wasting credits on the wrong model?", "risk_loss"),
        ("hook-choice", "Too many models, still no clear choice?", "failed_alternative"),
        ("hook-paying", "Stop paying to test the wrong model.", "contrarian"),
        ("hook-confused", "Confused which model fits your next idea?", "objection_dialogue"),
    ]
    hooks = {
        "version": "1.1",
        "topic": "Choosing an AI model",
        "audience": truth["audience"],
        "candidates": [
            {
                "id": hook_id,
                "text": text,
                "pain_id": "pain-01",
                "human_need": "Avoid wasting credits on a poor model fit",
                "promise": "A faster model decision",
                "hook_type": hook_type,
                "spoken_duration_seconds": 2.8,
                "first_frame": "TOO MANY MODELS?",
                "three_second_gate": {
                    "passes": True,
                    "pain_is_explicit": True,
                    "brand_first": False,
                    "visual_sync": True,
                    "credibility_supported": True,
                    "body_payoff_matches": True,
                    "speakability_passes": True,
                },
                "credibility": {
                    "basis": "product_truth",
                    "claim_scope": "The product exposes several models before generation",
                    "source_refs": ["pain-01", "claim-model-choice"],
                },
                "body_payoff": {
                    "promise": "Show a deliberate model choice before spending credits",
                    "payoff_beat": "proof",
                    "matches": True,
                },
                "speakability": {
                    "language": "en-US",
                    "word_count": len(text.replace("?", "").replace(".", "").split()),
                    "duration_seconds": 2.8,
                    "duration_source": "estimated",
                    "passes": True,
                },
                "format_fits": ["hybrid", "screen_demo"],
                "scores": {"truth": 5, "retention": 5, "relevance": 5, "total": 15},
                "evidence_refs": ["pain-01", "claim-model-choice"],
            }
            for hook_id, text, hook_type in hook_texts
        ],
        "selected_id": "hook-guessing",
        "approval": {"status": "approved", "notes": "Pain first"},
    }
    brief = {
        "version": "1.1",
        "creative_id": "vibeaha-choice-01",
        "product_id": "vibeaha",
        "audience": truth["audience"],
        "audience_job_id": "job-model-choice",
        "pain_id": "pain-01",
        "value_mapping_id": "map-choice",
        "hook_id": "hook-guessing",
        "message": "Choose the model that fits before spending credits.",
        "desired_viewer_response": "click",
        "format": "hybrid",
        "language": "en-US",
        "destination": "tiktok",
        "aspect": "9:16",
        "duration_seconds": 15,
        "structure": [
            {"beat": "hook", "start_seconds": 0, "end_seconds": 3, "purpose": "State the pain"},
            {"beat": "solution", "start_seconds": 3, "end_seconds": 8, "purpose": "Introduce the solution"},
            {"beat": "proof", "start_seconds": 8, "end_seconds": 13, "purpose": "Show the product"},
            {"beat": "cta", "start_seconds": 13, "end_seconds": 15, "purpose": "Invite comparison"},
        ],
        "creative_hypothesis": "Model-choice pain will retain active creators.",
        "approval": {"status": "approved", "notes": "Autonomous pilot"},
    }
    script = {
        "version": "1.0",
        "title": "Compare before you create",
        "total_duration_seconds": 15,
        "sections": [
            {
                "id": "hook",
                "label": "hook",
                "text": "Tired of guessing which AI model fits?",
                "start_seconds": 0,
                "end_seconds": 2.8,
                "source_ref": "pain-01",
            },
            {
                "id": "solution",
                "label": "solution",
                "text": "Compare the available models before you generate.",
                "start_seconds": 2.8,
                "end_seconds": 7,
                "source_ref": "claim-model-choice",
            },
            {
                "id": "proof",
                "label": "proof",
                "text": "VibeAha shows the choices together, so the decision happens before the spend.",
                "start_seconds": 7,
                "end_seconds": 12.5,
                "source_ref": "source-home",
            },
            {
                "id": "cta",
                "label": "cta",
                "text": "Compare before you create.",
                "start_seconds": 12.5,
                "end_seconds": 15,
            },
        ],
    }
    script_qa = {
        "version": "1.0",
        "script_ref": "script.json",
        "language": "en-US",
        "target_duration_seconds": 15,
        "desired_viewer_response": "click",
        "core_claim": "Creators can compare visible model choices before generating.",
        "delivery_measurement": {
            "method": "estimate",
            "measured": False,
            "total_words": 39,
            "duration_seconds": 15,
            "words_per_second": 2.6,
            "notes": "Confirm against the approved TTS sample during asset production.",
        },
        "checks": {
            name: {"passes": True, "evidence": evidence}
            for name, evidence in {
                "single_core_claim": "Every section supports model choice before spending.",
                "hook_payoff": "The proof section shows the comparison promised by the hook.",
                "evidence_coverage": "All factual sections carry source references.",
                "flow_continuity": "Pain moves directly to comparison, proof, and one CTA.",
                "density_balance": "Each beat adds one new piece of information.",
                "spoken_delivery": "Estimated delivery stays within the approved duration.",
            }.items()
        },
        "section_reviews": [
            {
                "section_id": section["id"],
                "function": section["label"],
                "source_quote": section["text"],
                "word_count": len(section["text"].replace("?", "").replace(".", "").split()),
                "duration_seconds": section["end_seconds"] - section["start_seconds"],
                "words_per_second": round(
                    len(section["text"].replace("?", "").replace(".", "").split())
                    / (section["end_seconds"] - section["start_seconds"]),
                    3,
                ),
                "sentence_count": 1,
                "max_sentence_words": len(section["text"].replace("?", "").replace(".", "").split()),
                "breath_group_count": 1,
                "severity": "clear",
                "issues": [],
                "recommendation": "Keep as written.",
            }
            for section in script["sections"]
        ],
        "revision_actions": [],
        "overall_status": "pass",
        "approval": {"status": "approved", "notes": "Ready for proof planning"},
    }
    proof = {
        "version": "1.0",
        "creative_id": "vibeaha-choice-01",
        "scenes": [
            {
                "scene_id": "proof-models",
                "beat": "proof",
                "start_seconds": 8,
                "end_seconds": 13,
                "pain_ref": "pain-01",
                "claim_refs": ["claim-model-choice"],
                "visual_intent": "Show real model choices in the product.",
                "proof_type": "product_capture",
                "asset_requirement": "Readable current product capture",
                "selected_asset_ref": "source-home",
                "acceptance_criteria": ["At least two model choices are visible"],
            }
        ],
    }
    payloads = {
        "product_truth": truth,
        "pain_library": pains,
        "audience_job": audience_job,
        "value_map": value_map,
        "hook_candidates": hooks,
        "creative_brief": brief,
        "script": script,
        "script_qa_report": script_qa,
        "proof_plan": proof,
    }
    return {name: _write(tmp_path / f"{name}.json", payload) for name, payload in payloads.items()}


def test_product_promo_pipeline_and_artifacts_are_registered():
    assert "product-promo-factory" in list_pipelines()
    manifest = load_pipeline("product-promo-factory")
    assert get_stage_order(manifest) == [
        "product_truth", "pain_research", "audience_job", "value_mapping", "hook_lab",
        "creative_brief", "proposal", "production_contract", "script", "script_quality",
        "proof_plan", "continuity_design", "shotcraft_plan", "assets", "edit", "compose", "publish",
    ]
    for skill_ref in manifest["required_skills"]:
        assert (ROOT / "skills" / f"{skill_ref}.md").is_file(), skill_ref
    assert {
        "product_truth", "pain_library", "audience_job", "value_map", "creative_brief",
        "script_qa_report", "production_preset", "proof_plan", "visual_continuity_bible",
        "shot_language_plan", "experiment_result",
    }.issubset(ARTIFACT_NAMES)

    stages = {stage["name"]: stage for stage in manifest["stages"]}
    assert "audience_job" in stages["value_mapping"]["required_artifacts_in"]
    assert "script_qa_report" in stages["proof_plan"]["required_artifacts_in"]
    assert "visual_continuity_bible" in stages["shotcraft_plan"]["required_artifacts_in"]
    assert "production_preset" in stages["assets"]["required_artifacts_in"]


def test_rank_pains_and_hook_gate(tmp_path: Path):
    pain_path = _write(tmp_path / "pain_library.json", _pain_library())
    ranked = PromoStrategy().execute({"operation": "rank_pains", "pain_library_path": str(pain_path), "top_n": 5})
    assert ranked.success is True, ranked.error
    assert ranked.data["selected_pain_ids"][0] == "pain-01"
    validate_artifact("pain_library", ranked.data["pain_library"])

    paths = _campaign_artifacts(tmp_path / "campaign")
    gated = PromoStrategy().execute({
        "operation": "evaluate_hooks",
        "hook_candidates_path": str(paths["hook_candidates"]),
        "brand_names": ["VibeAha"],
    })
    assert gated.success is True, gated.error
    assert gated.data["passed_count"] == 5


def test_hook_gate_rejects_unsupported_credibility(tmp_path: Path):
    paths = _campaign_artifacts(tmp_path)
    hook_path = paths["hook_candidates"]
    hooks = json.loads(hook_path.read_text(encoding="utf-8"))
    hooks["candidates"][0]["credibility"]["source_refs"] = ["invented-authority"]
    _write(hook_path, hooks)

    result = PromoStrategy().execute({
        "operation": "evaluate_hooks",
        "hook_candidates_path": str(hook_path),
        "brand_names": ["VibeAha"],
    })

    assert result.success is False
    assert result.data["selected_failures"][0]["id"] == "hook-guessing"
    assert "credibility references" in result.data["selected_failures"][0]["notes"]


def test_campaign_cross_reference_gate_and_registry(tmp_path: Path):
    paths = _campaign_artifacts(tmp_path)
    result = PromoStrategy().execute({
        "operation": "validate_campaign",
        **{f"{name}_path": str(path) for name, path in paths.items()},
    })
    assert result.success is True, result.error
    assert result.data["status"] == "ready_for_production"
    assert result.data["audience_job_id"] == "job-model-choice"
    assert result.data["script_qa_status"] == "pass"
    registry = ToolRegistry()
    registry.discover()
    assert registry.get("promo_strategy") is not None


def test_campaign_blocks_failed_script_quality(tmp_path: Path):
    paths = _campaign_artifacts(tmp_path)
    qa_path = paths["script_qa_report"]
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    qa["checks"]["hook_payoff"] = {"passes": False, "evidence": "The proof no longer resolves the hook."}
    qa["overall_status"] = "revise"
    _write(qa_path, qa)

    result = PromoStrategy().execute({
        "operation": "validate_campaign",
        **{f"{name}_path": str(path) for name, path in paths.items()},
    })

    assert result.success is False
    assert "Script quality gate has not passed" in result.error


def test_metric_diagnosis_targets_first_failed_gate():
    result = PromoStrategy().execute({
        "operation": "diagnose",
        "experiment_id": "exp-1",
        "creative_id": "creative-1",
        "platform": "tiktok",
        "metrics": {
            "impressions": 1000,
            "three_second_views": 120,
            "outbound_clicks": 30,
            "conversions": 2,
            "spend": 50,
        },
    })
    assert result.success is True, result.error
    artifact = result.data["experiment_result"]
    assert artifact["diagnosis"] == "hook_problem"
    validate_artifact("experiment_result", artifact)
