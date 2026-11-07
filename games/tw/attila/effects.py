"""Explicit Attila effect semantics, with source/target scopes preserved.

Unrecognized effects remain in the source data and audit. They never become a
flat resource merely because their identifier contains 'food' or 'public_order'.
"""

from dataclasses import dataclass
from enum import Enum


class Reach(str, Enum):
    BUILDING = "building"
    LOCAL = "region"
    PROVINCE = "province"
    FACTION = "faction"
    ADJACENT = "adjacent"
    CONDITIONAL = "conditional"
    OTHER = "other"


@dataclass(frozen=True)
class Rule:
    kind: str
    categories: tuple[str, ...] = ()


CATEGORIES = (
    "agriculture",
    "livestock",
    "industry",
    "culture",
    "commerce",
    "maritime",
    "subsistence",
)
RULES = {
    "att_effect_economy_gdp_agriculture_farming": Rule("wealth", ("agriculture",)),
    "att_effect_economy_gdp_agriculture_animal_husbandry": Rule(
        "wealth", ("livestock",)
    ),
    "att_effect_economy_gdp_fertility_agriculture": Rule(
        "fertility_wealth", ("agriculture",)
    ),
    "att_effect_economy_gdp_fertility_livestock": Rule(
        "fertility_wealth", ("livestock",)
    ),
    "att_effect_economy_gdp_industry": Rule("wealth", ("industry",)),
    "att_effect_economy_gdp_culture": Rule("wealth", ("culture",)),
    "att_effect_economy_gdp_trade_local": Rule("wealth", ("commerce",)),
    "att_effect_economy_gdp_trade_sea": Rule("wealth", ("maritime",)),
    "att_effect_economy_gdp_subsistance": Rule("wealth", ("subsistence",)),
    "att_effect_province_fertility_buildings": Rule("fertility"),
    "att_effect_food_base_production": Rule("food"),
    "att_effect_food_production_fertility": Rule("fertility_food"),
    "att_effect_food_consumption": Rule("food_consumption"),
    "att_effect_public_order_base": Rule("public_order"),
    "att_effect_public_order_global": Rule("public_order"),
    "att_effect_public_order_politics": Rule("public_order"),
    "att_effect_public_order_sanitation": Rule("public_order"),
    "att_effect_public_order_immigration": Rule("immigration_order_percent"),
    "att_effect_sanitation_buildings": Rule("sanitation"),
    "att_effect_sanitation_buildings_region": Rule("sanitation"),
    "att_effect_sanitation_squalor_buildings": Rule("squalor"),
    "att_effect_province_tax_rate": Rule("tax_percent"),
    "att_effect_economy_gpd_mod_immigration": Rule("immigration_wealth_percent"),
    "att_effect_public_order_base_neighbouring": Rule("public_order"),
    "cha_effect_sanitation_buildings_adjacent_province": Rule("sanitation"),
    "cha_effect_economy_gdp_mod_all_adjacent_province": Rule(
        "wealth_percent", CATEGORIES
    ),
}
for suffix in (
    "farming_animal_husbandry",
    "farming_grain",
    "fishing",
    "reserves",
    "trade",
):
    RULES[f"att_effect_food_production_{suffix}"] = Rule("food")
for suffix, categories in {
    "all": CATEGORIES,
    "agriculture_and_livestock": ("agriculture", "livestock"),
    "agriculture_farming": ("agriculture",),
    "livestock": ("livestock",),
    "industry": ("industry",),
    "industry_and_agriculture": ("industry", "agriculture"),
    "culture": ("culture",),
    "commerce_all": ("commerce", "maritime"),
    "commerce_land": ("commerce",),
}.items():
    RULES[f"att_effect_economy_gdp_mod_{suffix}"] = Rule("wealth_percent", categories)


def reach(scope):
    # Order matters: 'factionwide armies' does not mean all owned regions.
    if any(
        word in scope
        for word in ("force", "army", "general", "character", "sea_region")
    ):
        return Reach.OTHER
    if "adjacent_food" in scope:
        return Reach.CONDITIONAL
    if "adjacent" in scope or "neighbour" in scope:
        return Reach.ADJACENT
    if "factionwide" in scope or scope.startswith("faction_to_"):
        return Reach.FACTION
    if scope == "building_to_building_own":
        return Reach.BUILDING
    if scope in ("building_to_region_own", "region_to_region_own"):
        return Reach.LOCAL
    if scope in (
        "province_to_province_own",
        "province_to_region_own",
        "building_to_province_own",
        "region_to_province_own",
    ):
        return Reach.PROVINCE
    return Reach.OTHER


def entries(building):
    if building.raw_effects:
        for (key, scope), amount in building.raw_effects.items():
            yield key, RULES.get(key, Rule("unmodeled")), reach(scope), amount
    else:
        # Also support callers constructing Buildings directly through Scope.
        for scope, effects in (
            (Reach.FACTION, building.effects_to_faction),
            (Reach.PROVINCE, building.effects_to_province),
            (Reach.LOCAL, building.effects_to_region),
            (Reach.LOCAL, building.effects_to_building),
        ):
            for key, amount in effects.items():
                yield key, RULES.get(key, Rule("unmodeled")), scope, amount


def amount(
    building, kind, reaches=(Reach.BUILDING, Reach.LOCAL, Reach.PROVINCE, Reach.FACTION)
):
    return sum(
        value
        for _, rule, scope, value in entries(building)
        if rule.kind == kind and scope in reaches
    )


def base_wealth(building, fertility):
    return amount(building, "wealth") + fertility * amount(building, "fertility_wealth")


def base_food(building, fertility):
    return (
        amount(building, "food")
        + fertility * amount(building, "fertility_food")
        - amount(building, "food_consumption")
    )
