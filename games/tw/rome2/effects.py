"""Rome II effect IDs and public faction/technology fact recognition."""

import re
from dataclasses import dataclass

CATEGORIES = (
    "agriculture_farming",
    "agriculture_animal_husbandry",
    "culture_entertainment",
    "culture_learning",
    "industry_manufacture",
    "industry_mining",
    "trade_local",
    "trade_sea",
    "subsistence",
)
TARGETS = {
    "all": CATEGORIES,
    "agriculture_all": CATEGORIES[:2],
    "agriculture_farming": CATEGORIES[:1],
    "agriculture_animal_husbandry": CATEGORIES[1:2],
    "culture_all": CATEGORIES[2:4],
    "culture_entertainment": CATEGORIES[2:3],
    "industry": CATEGORIES[4:6],
    "industry_manufacturing": CATEGORIES[4:5],
    "industry_mining": CATEGORIES[5:6],
    "trade_all": CATEGORIES[6:8],
    "trade_local": CATEGORIES[6:7],
    "trade_sea": CATEGORIES[7:8],
    "subsistence": CATEGORIES[8:],
}
LABELS = {
    "all sources": "all",
    "agriculture": "agriculture_all",
    "agricultural buildings": "agriculture_all",
    "farming (agriculture)": "agriculture_farming",
    "livestock (agriculture)": "agriculture_animal_husbandry",
    "culture": "culture_all",
    "all culture": "culture_all",
    "entertainment (culture)": "culture_entertainment",
    "industry": "industry",
    "industry buildings": "industry",
    "manufacturing (industry)": "industry_manufacturing",
    "mining (industry)": "industry_mining",
    "all industrial buildings": "industry",
    "livestock buildings": "agriculture_animal_husbandry",
    "all commerce": "trade_all",
    "all commerce buildings": "trade_all",
    "commerce": "trade_all",
    "local commerce": "trade_local",
    "maritime commerce": "trade_sea",
    "subsistence": "subsistence",
}


@dataclass(frozen=True)
class Effect:
    kind: str
    value: int
    targets: tuple[str, ...] = ()


def raw_effect(key, value):
    if key.startswith("rom_province_initiative_"):
        return Effect("edict_conditional", value)
    if key.startswith("rom_building_slave_"):
        return Effect("slaves_conditional", value)
    if key.startswith("rom_building_gdp_mod_"):
        suffix = key.removeprefix("rom_building_gdp_mod_")
        if suffix in TARGETS:
            return Effect("wealth_percent", value, TARGETS[suffix])
    if key.startswith("rom_building_gdp_"):
        suffix = key.removeprefix("rom_building_gdp_")
        if suffix in CATEGORIES:
            return Effect("wealth", value, (suffix,))
    if key == "rom_building_food_consumption":
        return Effect("food", -value)
    if key.startswith("rom_building_food_") and "reserves" not in key:
        return Effect("food", value)
    if key.startswith("rom_building_public_order_"):
        return Effect("order", value)
    if key == "rom_building_tax_level":
        return Effect("tax_percent", value)
    if key.startswith("rom_building_growth_"):
        return Effect("growth", value)
    return None


def fact_effect(text):
    text = text.split(": ", 1)[-1]
    if match := re.fullmatch(r"([+-]?\d+)% wealth from minor settlements", text):
        return Effect("minor_wealth_percent", int(match[1]), CATEGORIES)
    if match := re.fullmatch(
        r"([+-]?\d+)% (?:wealth from|income from|bonus to income from|income from all) (.+)",
        text,
    ):
        label = (
            match[2].removesuffix(" buildings") if match[2] not in LABELS else match[2]
        )
        if label in LABELS:
            return Effect("wealth_percent", int(match[1]), TARGETS[LABELS[label]])
    if match := re.fullmatch(
        r"([+-]?\d+)% (?:all culture income|cultural income)", text
    ):
        return Effect("wealth_percent", int(match[1]), TARGETS["culture_all"])
    if match := re.fullmatch(r"([+-]?\d+)% tax rate", text):
        return Effect("tax_percent", int(match[1]))
    if match := re.fullmatch(r"([+-]?\d+) food in all (provinces|regions)", text):
        return Effect("food_per_" + match[2], int(match[1]))
    if match := re.fullmatch(r"([+-]?\d+) (?:food|food production)", text):
        return Effect("food_per_provinces", int(match[1]))
    if match := re.fullmatch(
        r"([+-]?\d+) public order(?: per turn)?(?: in all provinces)?", text
    ):
        return Effect("order", int(match[1]))
    if match := re.fullmatch(
        r"[Pp]ublic order (?:bonus|penalty) \((?:maximum|minimum) of ([+-]?\d+)\) from presence of .+ culture",
        text,
    ):
        return Effect("own_culture_order", int(match[1]))
    if match := re.fullmatch(r"Up to ([+-]?\d+) public order from .+ culture", text):
        return Effect("own_culture_order", int(match[1]))
    return None
