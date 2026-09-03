"""Load the consumer format, style, and provider-pack catalog."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "config" / "consumer_profiles.yaml"


@lru_cache(maxsize=1)
def load_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or CATALOG_PATH
    with open(catalog_path, encoding="utf-8") as handle:
        catalog = yaml.safe_load(handle) or {}
    for section in ("formats", "styles", "provider_packs", "destinations"):
        if not isinstance(catalog.get(section), dict) or not catalog[section]:
            raise ValueError(f"Consumer catalog is missing a non-empty {section!r} section")
    return catalog


def choose_format(
    *,
    requested: str,
    prompt: str,
    source_url: str | None,
    has_source_media: bool = False,
) -> str:
    catalog = load_catalog()
    if requested != "auto":
        if requested not in catalog["formats"]:
            raise ValueError(f"Unknown video format: {requested}")
        return requested

    text = prompt.lower()
    keyword_routes = (
        ("ai-podcast", ("podcast", "two host", "two-host", "dialogue", "conversation")),
        ("faceless", ("faceless", "no presenter", "narration only")),
        ("avatar", ("avatar", "digital human", "spokesperson")),
        ("screen-demo", ("screen demo", "walkthrough", "tutorial", "recording")),
        ("clip", ("clip", "repurpose", "highlights", "livestream")),
    )
    for format_id, needles in keyword_routes:
        if any(needle in text for needle in needles):
            return format_id
    if source_url:
        return "product-promo"
    if has_source_media:
        return "clip"
    return "faceless"


def choose_style(format_id: str, requested: str) -> str:
    catalog = load_catalog()
    format_config = catalog["formats"][format_id]
    style_id = format_config["default_style"] if requested == "auto" else requested
    style = catalog["styles"].get(style_id)
    if style is None:
        raise ValueError(f"Unknown consumer style: {style_id}")
    if format_id not in style["formats"]:
        raise ValueError(f"Style {style_id!r} is not compatible with format {format_id!r}")
    return style_id


def destination_settings(destination: str, aspect: str | None) -> dict[str, Any]:
    catalog = load_catalog()
    if destination not in catalog["destinations"]:
        raise ValueError(f"Unknown destination: {destination}")
    settings = dict(catalog["destinations"][destination])
    if aspect:
        settings["aspect"] = aspect
    return settings
