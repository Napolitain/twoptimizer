"""Immutable historical references and deterministic campaign-effect selection."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from games.tw.immutable import freeze, read_catalog
from games.tw.three_kingdoms.parsing import parse_catalog, parse_variant
from games.tw.three_kingdoms.records import Building, Catalog, Effect, EffectVariant, Faction
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


def load_catalog() -> Catalog:
    """Decode the immutable source snapshot into records used by the game engine."""
    return parse_catalog(load_data())


def selected_effects(
    building: Building, faction: Faction, campaign: str = "3k_main_campaign_map"
) -> tuple[Effect, ...]:
    return _select_variant(
        building.effect_variants, building.id, faction.id, faction.subculture, campaign
    ).effects


def building_effects(
    building: Mapping[str, Any],
    faction: Mapping[str, Any],
    campaign: str = "3k_main_campaign_map",
) -> tuple[Mapping[str, Any], ...]:
    """Return original source rows for provenance audits using the engine selector."""
    variants = tuple(parse_variant(row) for row in building["effect_variants"])
    selected = _select_variant(
        variants, building["id"], faction["id"], faction["subculture"], campaign
    )
    return tuple(building["effect_variants"][variants.index(selected)]["effects"])


def _select_variant(
    variants: tuple[EffectVariant, ...], building: str, faction: str, subculture: str, campaign: str
) -> EffectVariant:
    matching = [
        variant for variant in variants if _variant_matches(variant, faction, subculture, campaign)
    ]
    if not matching:
        raise ValueError(f"No source effect group for {building} and {faction}")
    priority = max(variant.priority for variant in matching)
    selected = [variant for variant in matching if variant.priority == priority]
    first = selected[0]
    if any(variant.effects != first.effects for variant in selected[1:]):
        raise ValueError(f"Ambiguous source effect groups for {building}")
    return first


def _variant_matches(variant: EffectVariant, faction: str, subculture: str, campaign: str) -> bool:
    return all(
        not available or value in available
        for available, value in (
            (variant.factions, faction),
            (variant.subcultures, subculture),
            (variant.campaigns, campaign),
        )
    )
