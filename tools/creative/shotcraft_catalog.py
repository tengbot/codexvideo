"""Deterministic access to the vendored video-shotcraft recipe catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

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


ROOT = Path(__file__).resolve().parents[2]
SHOTCRAFT_ROOT = ROOT / ".agents" / "skills" / "video-shotcraft"
DEFAULT_CATALOG = SHOTCRAFT_ROOT / "gallery" / "api" / "library.json"
VENDOR_METADATA = SHOTCRAFT_ROOT / "OPENMONTAGE_VENDOR.json"


class ShotcraftCatalog(BaseTool):
    """Resolve and recommend traceable shot recipes from the local mirror."""

    name = "shotcraft_catalog"
    version = "1.0.0"
    tier = ToolTier.ANALYZE
    stability = ToolStability.BETA
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL
    resume_support = ResumeSupport.FROM_CHECKPOINT
    capability = "shot_design"
    provider = "video-shotcraft"
    capabilities = [
        "shot_catalog_verification",
        "shot_recipe_resolution",
        "intent_to_shot_recommendation",
        "reference_implementation_lookup",
    ]
    best_for = [
        "Mapping an approved product-proof scene to a tuned motion recipe",
        "Locating the exact recipe, demo source, and preview before implementation",
        "Keeping shot selection deterministic and provenance-linked",
    ]
    not_good_for = ["Writing advertising claims", "Replacing product research", "Generating footage"]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["stats", "verify", "resolve", "recommend"]},
            "catalog_path": {"type": "string"},
            "card_name": {"type": "string"},
            "style_key": {"type": "string"},
            "intent": {"type": "string"},
            "beat": {"type": "string"},
            "preferred_categories": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"type": "object"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=8, network_required=False)
    user_visible_verification = [
        "Confirm the selected card and style exist in the vendored catalog",
        "Confirm the recipe document and referenced demo implementation files exist",
        "Compare the adapted shot against its Gallery preview during visual QA",
    ]

    _TOKEN_RE = re.compile(r"[a-z0-9]+")
    _REFERENCE_RE = re.compile(r"demos/[A-Za-z0-9_./-]+/")
    _STOP = {
        "a", "an", "and", "as", "at", "be", "before", "by", "for", "from",
        "in", "into", "is", "it", "of", "on", "or", "the", "this", "to", "with",
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            catalog_path = Path(inputs.get("catalog_path") or DEFAULT_CATALOG)
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            operation = inputs["operation"]
            if operation == "stats":
                return ToolResult(success=True, data=self._stats(catalog, catalog_path))
            if operation == "verify":
                return self._verify(catalog, catalog_path)
            if operation == "resolve":
                return self._resolve(catalog, inputs)
            if operation == "recommend":
                return self._recommend(catalog, inputs)
            return ToolResult(success=False, error=f"Unsupported operation: {operation}")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))

    @staticmethod
    def _stats(catalog: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
        cards = catalog.get("cards", [])
        styles = [style for card in cards for style in card.get("styles", [])]
        metadata = json.loads(VENDOR_METADATA.read_text(encoding="utf-8"))
        return {
            "card_count": len(cards),
            "style_count": len(styles),
            "preview_count": sum(bool((style.get("media") or {}).get("url")) for style in styles),
            "categories": sorted(catalog.get("categories", {}).keys()),
            "catalog_path": str(catalog_path),
            "repository": metadata["repository"],
            "commit": metadata["commit"],
            "license": metadata["license"],
        }

    def _verify(self, catalog: dict[str, Any], catalog_path: Path) -> ToolResult:
        stats = self._stats(catalog, catalog_path)
        missing: list[str] = []
        if not (SHOTCRAFT_ROOT / "SKILL.md").is_file():
            missing.append("SKILL.md")
        if not (SHOTCRAFT_ROOT / "LICENSE").is_file():
            missing.append("LICENSE")
        if not (SHOTCRAFT_ROOT / "template" / "src" / "Root.tsx").is_file():
            missing.append("template/src/Root.tsx")
        for card in catalog.get("cards", []):
            recipe = SHOTCRAFT_ROOT / card["source"]
            if not recipe.is_file():
                missing.append(card["source"])
        expected = catalog.get("stats", {})
        mismatches = []
        if expected.get("cardCount") != stats["card_count"]:
            mismatches.append("cardCount")
        if expected.get("styleCount") != stats["style_count"]:
            mismatches.append("styleCount")
        if expected.get("previewCount") != stats["preview_count"]:
            mismatches.append("previewCount")
        success = not missing and not mismatches
        return ToolResult(
            success=success,
            data={**stats, "missing": missing, "mismatches": mismatches},
            error=None if success else f"Shotcraft mirror verification failed: missing={missing}, mismatches={mismatches}",
        )

    def _resolve(self, catalog: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        card_name = (inputs.get("card_name") or "").strip()
        if not card_name:
            raise ValueError("card_name is required")
        card = next((item for item in catalog.get("cards", []) if item["name"] == card_name), None)
        if card is None:
            raise ValueError(f"Unknown shot card: {card_name}")
        styles = card.get("styles", [])
        style_key = (inputs.get("style_key") or "").strip()
        style = next((item for item in styles if item["key"] == style_key), None) if style_key else (styles[0] if styles else None)
        if style is None:
            raise ValueError(f"Unknown style {style_key!r} for card {card_name}")
        return ToolResult(success=True, data={"shot": self._resolved_card(card, style)})

    def _recommend(self, catalog: dict[str, Any], inputs: dict[str, Any]) -> ToolResult:
        intent = (inputs.get("intent") or "").strip()
        if not intent:
            raise ValueError("intent is required")
        beat = (inputs.get("beat") or "").strip()
        preferred = set(inputs.get("preferred_categories") or [])
        query_tokens = self._tokens(f"{beat} {intent}")
        ranked: list[tuple[float, str, dict[str, Any], dict[str, Any]]] = []
        for card in catalog.get("cards", []):
            haystack = " ".join(
                str(card.get(key, "")) for key in ("name", "summary", "use", "intention", "category")
            ) + " " + " ".join(card.get("tags", []))
            card_tokens = self._tokens(haystack)
            overlap = len(query_tokens & card_tokens)
            category_bonus = 3 if card.get("category") in preferred else 0
            beat_bonus = 2 if beat and (beat == card.get("category") or beat in card.get("tags", [])) else 0
            score = overlap + category_bonus + beat_bonus
            for style in card.get("styles", []):
                ranked.append((score, card["name"], card, style))
        ranked.sort(key=lambda row: (-row[0], row[1], row[3]["key"]))
        limit = int(inputs.get("limit", 5))
        recommendations = [
            {**self._resolved_card(card, style), "match_score": score}
            for score, _, card, style in ranked[:limit]
        ]
        return ToolResult(success=True, data={"intent": intent, "beat": beat, "recommendations": recommendations})

    @classmethod
    def _tokens(cls, value: str) -> set[str]:
        return {token for token in cls._TOKEN_RE.findall(value.lower()) if token not in cls._STOP}

    @staticmethod
    def _resolved_card(card: dict[str, Any], style: dict[str, Any]) -> dict[str, Any]:
        recipe_path = SHOTCRAFT_ROOT / card["source"]
        recipe_text = recipe_path.read_text(encoding="utf-8")
        reference_dirs = ShotcraftCatalog._REFERENCE_RE.findall(recipe_text)
        implementation_files: list[str] = []
        for relative_dir in reference_dirs:
            directory = SHOTCRAFT_ROOT / relative_dir
            if directory.is_dir():
                implementation_files.extend(
                    str(path.relative_to(ROOT)) for path in sorted(directory.glob("*.tsx"))
                )
        return {
            "card_name": card["name"],
            "style_key": style["key"],
            "summary": card.get("summary"),
            "use": style.get("use") or card.get("use"),
            "duration": card.get("duration"),
            "energy": card.get("energy"),
            "category": card.get("category"),
            "tags": card.get("tags", []),
            "recipe_path": str(recipe_path.relative_to(ROOT)),
            "implementation_files": implementation_files,
            "reference_media": (style.get("media") or {}).get("url"),
        }
