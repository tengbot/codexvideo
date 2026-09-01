"""Contracts for resumable production and visual continuity adaptations."""

from pathlib import Path

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact


ROOT = Path(__file__).resolve().parent.parent.parent


def test_production_preset_supports_pending_approval_without_silent_runtime_choice():
    artifact = {
        "version": "1.0",
        "preset_id": "promo-v1",
        "provenance": {
            "inspired_by": "MoneyPrinterTurbo",
            "repository": "https://github.com/harry0703/MoneyPrinterTurbo",
            "commit": "d7d4a13a26e7c435ea8a234f1a2d996e9a1c3719",
            "license": "MIT",
            "integration": "independent_contract_adaptation",
        },
        "approval": {"status": "pending", "approved_by": None, "approved_at": None},
        "runtime": {
            "renderer_family": None,
            "render_runtime": None,
            "composition_mode": None,
            "fallback_runtime": None,
        },
        "outputs": [
            {
                "id": "vertical",
                "width": 720,
                "height": 1280,
                "fps": 30,
                "codec": "libx264",
                "caption_mode": "burned",
            }
        ],
        "batch": {
            "variant_axes": ["hook", "body", "cta"],
            "max_changed_dimensions": 2,
            "max_parallel_jobs": 2,
            "cache_policy": "content_addressed",
            "rerun_policy": "failed_or_stale_only",
        },
        "stage_policies": [
            {
                "stage": "assets",
                "stale_when_inputs_change": True,
                "max_retries": 2,
                "preserve_originals": True,
            }
        ],
    }

    validate_artifact("production_preset", artifact)
    assert artifact["approval"]["status"] == "pending"
    assert artifact["runtime"]["render_runtime"] is None


def test_visual_continuity_bible_tracks_locks_and_dependency_invalidation():
    artifact = {
        "version": "1.0",
        "project_id": "promo",
        "provenance": {
            "inspired_by": "OpenStory",
            "repository": "https://github.com/openstory-so/openstory",
            "commit": "02317772b8b06101a5df44ff26ac5609616383ff",
            "license": "MIT",
            "integration": "independent_contract_adaptation",
        },
        "identity": {
            "subject": "Real product surface",
            "brand_mark": "Current first-party mark",
            "product_surfaces": ["source-product"],
            "forbidden_substitutions": ["No fictional UI"],
        },
        "visual_system": {
            "palette": ["black", "white", "gold"],
            "typography": ["Product UI type"],
            "lighting": "Crisp product lighting",
            "camera": ["Portrait-native crop"],
            "motion": ["One primary move per scene"],
        },
        "continuity_locks": [
            {
                "id": "real-product",
                "scope": "product",
                "rule": "Use current first-party screens",
                "verification": "Compare against evidence capture",
            }
        ],
        "scenes": [
            {
                "scene_id": "proof",
                "inherits": ["real-product"],
                "state": "Product proof visible",
                "entry_match": None,
                "exit_match": "Product frame becomes CTA frame",
            }
        ],
        "dependencies": [
            {
                "artifact": "artifacts/product_truth.json",
                "content_hash": "a" * 64,
                "invalidates": ["shot_language_plan", "render_report"],
            }
        ],
    }

    validate_artifact("visual_continuity_bible", artifact)
    assert "render_report" in artifact["dependencies"][0]["invalidates"]


def test_adapted_capabilities_are_registered_and_documented():
    assert {"production_preset", "visual_continuity_bible"}.issubset(ARTIFACT_NAMES)
    ledger = (ROOT / "docs/CAPABILITY_PROVENANCE.md").read_text(encoding="utf-8")
    assert "MoneyPrinterTurbo" in ledger
    assert "OpenStory" in ledger
    assert "DBSkill is not installed globally" in ledger
