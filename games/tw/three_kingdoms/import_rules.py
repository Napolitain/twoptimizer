"""Extract historical population, city capacity and tax reference rules."""

import argparse
import json
from pathlib import Path

from games.tw.three_kingdoms.source import PIN, RULESET, SourceArchive

DATA = Path(__file__).parent / "data"
POPULATION_PREFIX = "3k_main_campaign_group_population_"


def _bundles(source: SourceArchive) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for row in source.table("effect_bundles_to_effects_junctions"):
        result.setdefault(row["effect_bundle_key"], []).append(row)
    return result


def population_bands(source: SourceArchive) -> list[dict[str, object]]:
    """Keep source integer-thousands intervals, without inferred interpolation."""
    members = {r["group"]: r["id"] for r in source.table("campaign_group_members")}
    ranges = {
        r["member"]: r
        for r in source.table("campaign_group_member_criteria_numeric_ranges")
        if r["context"] == "value"
    }
    resources = {
        r["member"]: r["pooled_resource"]
        for r in source.table("campaign_group_member_criteria_pooled_resources")
    }
    scopes = {
        r["member"]: r["scope"]
        for r in source.table("campaign_group_member_criteria_pooled_resource_scopes")
    }
    bundles = _bundles(source)
    result = []
    for row in source.table("campaign_group_pooled_resource_effects"):
        group = row["campaign_group"]
        if not group.startswith(POPULATION_PREFIX) or any(
            faction in group for faction in ("he_yi", "kong_rong")
        ):
            continue
        member = members[group]
        if resources[member] != "3k_main_pooled_resource_population":
            raise ValueError(f"Unexpected population resource: {group}")
        if scopes[member] != "FACTION_PROVINCE":
            raise ValueError(f"Unexpected population scope: {group}")
        result.append(_population_band(row, ranges[member], bundles[row["effect_bundle"]]))
    result.sort(key=lambda band: int(str(band["minimum"])))
    _validate_bands(result)
    return result


def _population_band(
    row: dict[str, str], bounds: dict[str, str], effects: list[dict[str, str]]
) -> dict[str, object]:
    values = {effect["effect_key"]: int(effect["value"]) for effect in effects}
    if (
        "3k_main_effect_province_public_order_population" not in values
        and values.get("3k_main_effect_population_effects_public_order") != 1
    ):
        raise ValueError("Population public order lacks an explicit value or no-penalty marker")
    return {
        "minimum": int(bounds["min_range"]),
        "maximum": int(bounds["max_range"]),
        "peasantry_percent": values["3k_main_effect_economy_gdp_mod_peasantry_from_population"],
        "public_order": values.get("3k_main_effect_province_public_order_population", 0),
        "source_group": row["campaign_group"],
        "source_bundle": row["effect_bundle"],
        "effects": effects,
    }


def _validate_bands(bands: list[dict[str, object]]) -> None:
    next_minimum = 0
    for band in bands:
        lower, upper = int(str(band["minimum"])), int(str(band["maximum"]))
        if lower != next_minimum or upper < lower:
            raise ValueError("Population source intervals overlap or have a gap")
        next_minimum = upper + 1
    if next_minimum != 2147483648:
        raise ValueError("Population source intervals do not cover the source domain")


def city_levels(source: SourceArchive) -> dict[str, dict[str, object]]:
    variables = {r["variable_key"]: r["value"] for r in source.table("campaign_variables")}
    slot_cost = int(variables["settlement_secondary_slot_unlock_point_cost"])
    capacities = {
        r["campaign_group"]: int(r["value"]) * 1000
        for r in source.table("building_effects_junction")
        if r["effect"] == "3k_main_effect_province_population_capacity"
    }
    result: dict[str, dict[str, object]] = {}
    for row in source.table("building_levels"):
        if row["chain"] != "3k_city":
            continue
        level = int(row["level"])
        points = int(row["settlement_secondary_slot_unlock_points"])
        if slot_cost <= 0 or points % slot_cost:
            raise ValueError("Unsupported settlement slot-unlock point conversion")
        group = f"3k_campaign_group_buildings_city_{level}"
        result[str(level)] = {
            "building": row["level_name"],
            "slots": points // slot_cost,
            "population_capacity": capacities[group] if level else 0,
            "unlock_points": points,
            "slot_point_cost": slot_cost,
        }
    if set(result) != {str(level) for level in range(11)}:
        raise ValueError("Incomplete standard city-level source table")
    return result


def tax_levels(source: SourceArchive) -> dict[str, dict[str, object]]:
    percentages = {r["tax_level"]: int(r["percentage"]) for r in source.table("taxes_levels")}
    keys = {r["tax_lookup"]: r for r in source.table("taxes_keys")}
    effects: dict[str, list[dict[str, str]]] = {}
    for row in source.table("taxes_effects_jct"):
        effects.setdefault(row["tax_name"], []).append(row)
    return {
        key.removeprefix("lower_"): {
            "income_percent": percentages[row["tax_level"]],
            "effects": effects[key],
        }
        for key, row in sorted(keys.items())
        if row["tax_class"] == "lower_classes"
    }


def fertility_bundles(source: SourceArchive) -> dict[str, dict[str, object]]:
    """Retain explicit seasonal bundles; do not infer their geographic allocation."""
    bundles = _bundles(source)
    prefix = "3k_main_effect_bundle_fertility_"
    result: dict[str, dict[str, object]] = {}
    for key, effects in bundles.items():
        if not key.startswith(prefix):
            continue
        values = {effect["effect_key"]: int(effect["value"]) for effect in effects}
        result[key.removeprefix(prefix)] = {
            "peasantry_percent": values.get("3k_main_effect_economy_gdp_mod_peasantry", 0),
            "farming_fishing_percent": values.get("3k_main_effect_province_food_mod", 0),
            "source_bundle": key,
            "effects": effects,
        }
    return result


def import_rules(source: SourceArchive) -> dict[str, object]:
    """Derive facts only from the same pinned vanilla export as the catalog."""
    resources = {r["key"]: r for r in source.table("pooled_resources")}
    scale = int(resources["3k_main_pooled_resource_population"]["ui_value_scale_factor"])
    result: dict[str, object] = {
        "ruleset": RULESET,
        "source_commit": PIN,
        "population_unit": scale,
        "population_scope": "FACTION_PROVINCE",
        "population_bands": population_bands(source),
        "city_levels": city_levels(source),
        "tax_levels": tax_levels(source),
        "fertility_bundles": fertility_bundles(source),
        "corruption_reference_points": source.table("campaign_tax_administration_costs"),
        "interpretation": {
            "population": (
                "The snapshot uses integer thousands of people. A supplied person count is "
                "divided by 1000 with its fractional remainder discarded before band lookup. "
                "Population is the total in owned regions of the commandery, not only its "
                "capital. Population is fixed; growth, migration and replenishment "
                "are not optimized."
            ),
            "population_scope": (
                "These are standard 190 CE population economy/public-order bands. "
                "Kong Rong/He Yi special trade or recruitment effects are separate rules."
            ),
            "corruption": (
                "Raw difficulty/region-count reference points are retained for audit. "
                "Interpolation and in-engine rounding are not inferred; the current model "
                "takes base corruption as a supplied snapshot input."
            ),
            "taxation": (
                "All tax levels and their scoped effects are retained. The initial optimizer "
                "uses the normal level; other taxation policies are not automatically chosen."
            ),
            "fertility": (
                "Seasonal fertility bundles are retained without inventing per-commandery "
                "geographic assignments. The controlled baseline is normal fertility outside "
                "the harvest season unless explicit scenario inputs select another bundle."
            ),
            "version": (
                "Historical 1.2.0 reference only. Later population and faction-rule changes "
                "are not mixed into these tables. This is not installed-build validation."
            ),
        },
    }
    result["sources"] = sorted(source.records.values(), key=lambda record: str(record["url"]))
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/three-kingdoms-vanilla"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA / "rules.json")
    args = parser.parse_args(argv)
    result = import_rules(SourceArchive(args.cache, args.offline))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Wrote historical Three Kingdoms rules to {args.output}")


if __name__ == "__main__":
    main()
