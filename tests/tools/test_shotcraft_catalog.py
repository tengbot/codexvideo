"""Contracts for the vendored video-shotcraft integration."""

from pathlib import Path

from schemas.artifacts import ARTIFACT_NAMES, validate_artifact
from tools.creative.shotcraft_catalog import ShotcraftCatalog
from tools.tool_registry import ToolRegistry


ROOT = Path(__file__).resolve().parent.parent.parent
COMMIT = "0022ec45d28800cecb5b16624a3179093c93f4e9"


def test_complete_shotcraft_mirror_and_registry():
    result = ShotcraftCatalog().execute({"operation": "verify"})
    assert result.success is True, result.error
    assert result.data["card_count"] == 104
    assert result.data["style_count"] == 161
    assert result.data["preview_count"] == 161
    assert result.data["commit"] == COMMIT
    assert (ROOT / ".agents/skills/video-shotcraft/LICENSE").is_file()
    assert "shot_language_plan" in ARTIFACT_NAMES

    registry = ToolRegistry()
    registry.discover()
    assert registry.get("shotcraft_catalog") is not None


def test_resolve_returns_recipe_and_exact_demo_sources():
    result = ShotcraftCatalog().execute({
        "operation": "resolve",
        "card_name": "ui-to-brand-morph",
        "style_key": "input-morph-assemble",
    })
    assert result.success is True, result.error
    shot = result.data["shot"]
    assert shot["recipe_path"].endswith("references/shots/outro/ui-to-brand-morph.md")
    assert any(path.endswith("InputMorphsIntoLogo.tsx") for path in shot["implementation_files"])


def test_shot_language_plan_schema_accepts_traceable_vertical_plan():
    validate_artifact(
        "shot_language_plan",
        {
            "version": "1.0",
            "source": {
                "repository": "https://github.com/Vincentwei1021/video-shotcraft",
                "commit": COMMIT,
                "license": "Apache-2.0",
                "catalog_path": ".agents/skills/video-shotcraft/gallery/api/library.json",
            },
            "format": "product_promo",
            "canvas": {"aspect": "9:16", "width": 720, "height": 1280, "fps": 30},
            "energy_curve": ["high", "medium", "medium_high", "rest"],
            "scenes": [
                {
                    "scene_id": "hook",
                    "beat": "hook",
                    "start_seconds": 0,
                    "end_seconds": 3,
                    "shot_card": "crash-zoom-punch",
                    "style_key": "crash-zoom",
                    "recipe_path": ".agents/skills/video-shotcraft/references/shots/camera/crash-zoom-punch.md",
                    "implementation_files": [
                        ".agents/skills/video-shotcraft/demos/camera/crash-zoom-punch/CrashZoomReal.tsx"
                    ],
                    "reference_media": "./media/crash-zoom.mp4",
                    "visual_intent": "Make model-choice overload immediately legible.",
                    "primary_motion": "Six-frame crash zoom into the wrong-model cost.",
                    "transition_in": None,
                    "transition_out": "flash cut",
                    "sfx_cues": [
                        {"frame": 42, "action": "zoom impact", "source_path": "assets/audio/sfx/impact/impact-deep-whoosh.mp3", "gain": 0.6}
                    ],
                    "asset_requirements": ["High-resolution model selector capture"],
                    "responsive_rules": ["Keep the cost and hook inside the portrait safe area"],
                    "acceptance_frames": [15, 75],
                    "adaptation_notes": "Recomposed for portrait; no center crop.",
                }
            ],
        },
    )
