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
    if hasattr(building, "semantic_effects"):
        yield from building.semantic_effects
        return
    if building.raw_effects:
        for (key, scope), amount in building.raw_effects.items():
            yield key, RULES.get(key, Rule("unmodeled")), reach(scope), amount
    else:
        # Also support callers constructing Buildings directly through Scope.
        for scope, effects in (
            (Reach.FACTION, building.effects_to_faction),
            (Reach.PROVINCE, building.effects_to_province),
            (Reach.LOCAL, building.effects_to_region),
            (Reach.BUILDING, building.effects_to_building),
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


# Additional economic channels. These remain separate from flat wealth/order.
RULES.update(
    {
        "att_effect_building_corruption": Rule("corruption_percent"),
        "cha_effect_building_corruption_adjacent_province": Rule("corruption_percent"),
        "att_effect_economy_trade_tariff_mod": Rule("tariff_percent"),
        "att_effect_building_construction_cost_mod": Rule("construction_percent"),
        "att_effect_building_construction_cost_mod_sanitation": Rule(
            "sanitation_cost_percent"
        ),
        "att_effect_building_conversion_cost_mod": Rule("conversion_cost_percent"),
        "att_effect_province_growth_building": Rule("metric", ("growth",)),
        "att_effect_technology_research_points": Rule("metric", ("research_percent",)),
        "att_effect_technology_research_civil_points": Rule(
            "metric", ("research_civil_percent",)
        ),
        "att_effect_building_road": Rule("metric", ("roads",)),
        # The recipients of this exceptional scope must be supplied explicitly.
        "att_effect_food_production_fertility_neighbouring": Rule(
            "conditional_fertility_food"
        ),
    }
)
for resource in (
    "dyes",
    "gem",
    "iron",
    "lead",
    "leather",
    "marble",
    "olive",
    "salt",
    "silk",
    "spice",
    "wine",
    "wood",
):
    RULES[f"att_effect_region_resource_{resource}_production"] = Rule(
        "metric", (f"resource:{resource}",)
    )
RULES["cha_effect_region_resource_cloth_production"] = Rule(
    "metric", ("resource:cloth",)
)
for religion in (
    "arian",
    "catholic",
    "celtic",
    "church_east",
    "germanic",
    "grecoroman",
    "judaism",
    "manichaeist",
    "orthodox",
    "other",
    "semitic_paganism",
    "slavic",
    "state",
    "tengri",
    "zoroastrian",
):
    for prefix, metric in (("conversion", "religion"), ("osmosis", "osmosis")):
        key = f"att_effect_religion_{prefix}_{religion}"
        if prefix != "osmosis" or religion not in ("state", "tengri"):
            RULES[key] = Rule("metric", (f"{metric}:{religion}",))
for religion in ("christianity", "islam", "paganism", "tengri"):
    for prefix, metric in (("conversion", "religion"), ("osmosis", "osmosis")):
        RULES[f"cha_effect_religion_{prefix}_{religion}"] = Rule(
            "metric", (f"{metric}:{religion}",)
        )
RULES["att_effect_religion_conversion_catholic_faction"] = Rule(
    "metric", ("religion:catholic",)
)
for agent in ("champion", "dignitary", "spy"):
    RULES[f"att_effect_agent_enable_recruitment_{agent}"] = Rule(
        "metric", (f"agent_enable:{agent}",)
    )
    if agent != "spy":
        RULES[f"att_effect_agent_recruitment_cap_{agent}"] = Rule(
            "metric", (f"agent_cap:{agent}",)
        )
for agent in ("all_agents", "dignitary", "spy"):
    RULES[f"att_effect_agent_recruitment_xp_{agent}"] = Rule(
        "metric", (f"agent_xp:{agent}",)
    )
for agent in ("assassin", "imam"):
    RULES[f"cha_effect_agent_enable_recruitment_{agent}"] = Rule(
        "metric", (f"agent_enable:{agent}",)
    )
RULES["att_effect_unit_recruitment_points"] = Rule("metric", ("recruitment_points",))
RULES["att_effect_agent_action_outcome_local_province_recruitment_points"] = Rule(
    "metric", ("agent_recruitment_points",)
)
for troop in ("all", "artillery", "cavalry", "infantry"):
    key = (
        "att_effect_force_all_campaign_experience_base_all"
        if troop == "all"
        else f"att_effect_force_army_campaign_experience_base_{troop}"
    )
    RULES[key] = Rule("metric", (f"recruitment_xp:{troop}",))
RULES["att_effect_force_army_campaign_recruitment_cost_land"] = Rule(
    "metric", ("land_recruitment_cost_percent",)
)
for equipment in ("ammo", "armour", "shields", "weapon"):
    for tier in ("bronze", "silver", "gold"):
        RULES[f"att_effect_unit_equipment_{equipment}_{tier}"] = Rule(
            "metric", (f"equipment:{equipment}:{tier}",)
        )
for tier in ("i", "ii", "iii"):
    RULES[f"att_effect_unit_equipment_cavalry_horse_bonus_{tier}"] = Rule(
        "metric", (f"equipment:horse:{tier}",)
    )

METRICS = frozenset(
    category
    for rule in RULES.values()
    if rule.kind == "metric"
    for category in rule.categories
)
ECONOMIC_KINDS = frozenset(
    rule.kind for rule in RULES.values() if rule.kind not in ("metric", "unmodeled")
)
