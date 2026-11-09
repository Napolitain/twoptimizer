"""Immutable historical references and deterministic campaign-effect selection."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from games.tw.immutable import freeze, read_catalog
from games.tw.three_kingdoms.source import PIN

DATA = Path(__file__).parent / "data"
DEFAULT_FACTION = "3k_main_faction_cao_cao"
DEFAULT_COMMANDERY = "3k_main_province_yingchuan"


def load_data() -> Mapping[str, Any]:
    reference = read_catalog(DATA / "reference.json")
    geography = read_catalog(DATA / "geography.json")
    rules = read_catalog(DATA / "rules.json")
    revisions = (reference["source_revision"], geography["source_revision"], rules["source_commit"])
    if any(revision != PIN for revision in revisions):
        raise ValueError("Three Kingdoms reference files use different source revisions")
    buildings = {}
    for filename in reference["building_files"]:
        buildings.update(read_catalog(DATA / filename))
    return freeze(
        {
            **reference,
            "buildings": buildings,
            "commanderies": geography["commanderies"],
            "regions": geography["regions"],
            "geography": geography,
            "rules": rules,
        }
    )


def building_effects(
    building: Mapping[str, Any],
    faction: Mapping[str, Any],
    campaign: str = "3k_main_campaign_map",
) -> tuple[Mapping[str, Any], ...]:
    """Select the most specific whole effect group; variants replace, not add."""
    matching = [
        variant
        for variant in building["effect_variants"]
        if _variant_matches(variant, faction, campaign)
    ]
    if not matching:
        raise ValueError(f"No source effect group for {building['id']} and {faction['id']}")
    priority = max(variant["priority"] for variant in matching)
    selected = [variant for variant in matching if variant["priority"] == priority]
    first = tuple(selected[0]["effects"])
    if any(tuple(variant["effects"]) != first for variant in selected[1:]):
        raise ValueError(f"Ambiguous source effect groups for {building['id']}")
    return first


def _variant_matches(variant: Mapping, faction: Mapping, campaign: str) -> bool:
    values = {
        "factions": faction["id"],
        "subcultures": faction["subculture"],
        "campaigns": campaign,
    }
    return all(not variant[key] or value in variant[key] for key, value in values.items())
