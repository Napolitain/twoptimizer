"""Source-backed faction traits with explicit handling of campaign conditions.

Text matches are deliberately exact. Unrecognized facts remain in the report,
instead of silently becoming flat income or being attributed to an NPC alias.
"""

import json
from pathlib import Path

TRAITS = {
    "Venedi Farms : Farms do not have any negative effects (squalor or public order).": (
        "farms_without_penalties",
    ),
    "Trade tariffs: +50%": ("effect", "att_effect_economy_trade_tariff_mod", 50),
    "Irrigation: +1 fertility bonus in all provinces": (
        "effect",
        "att_effect_province_fertility_buildings",
        1,
    ),
    "Sunscorched: +2 sanitation": ("effect", "att_effect_sanitation_buildings", 2),
    "Income: +100% from farms": (
        "effect",
        "att_effect_economy_gdp_mod_agriculture_and_livestock",
        100,
    ),
    "Income: -50% from commerce, industry & culture": ("venedian_penalty",),
    "Sanitation: +1 for every province capital held": ("capital_sanitation",),
    "Harsh Sustenance: +15 food for every region with poor fertility.": ("poor_fertility_food",),
    "Commercial Mastery: +10% from trade income": ("trade_income_percent", 10),
    "Income: +100% tribute from puppet states": ("tribute_percent", 100),
    "Subsidised Peace: +500 wealth per turn while at peace with the Sassanids": ("peace_subsidy",),
    "Supply Network: +30 food from each active trade route (Maximum: 150)": ("trade_food",),
    "Construction cost: -50% for main settlement buildings": ("main_construction", -50),
    "+200% conversion cost of the main chain": ("main_conversion", 200),
    "+250% conversion cost of the main chain": ("main_conversion", 250),
    "Income: +5% interest on treasury at end of turn": ("excluded_treasury_interest",),
}


def profile(faction, enabled=True):
    if faction is None or not enabled:
        return {"faction": faction, "enabled": enabled, "traits": []}
    data = json.loads((Path(__file__).parent / "data/online_factions.json").read_text())
    if faction not in data["factions"]:
        raise ValueError(f"Missing faction trait metadata for {faction}")
    record = data["factions"][faction]
    traits = []
    for origin, key in (("culture", "culture_traits"), ("faction", "faction_traits")):
        for text in record[key]:
            rule = TRAITS.get(text)
            # Army, battle and historical event traits do not describe the
            # recurring operation of a settled building layout.
            outside = any(
                word in text.lower()
                for word in (
                    "morale",
                    "melee",
                    "battle",
                    "raiding",
                    "sacking",
                    "looting",
                    "horde",
                    "army",
                    "units",
                    "attrition",
                    "replenishment",
                    "provincial security",
                    "agent",
                    "migrat",
                    "razing",
                    "levy",
                    "levies",
                    "integrity",
                    "colonisation",
                    "occupying",
                    "seasickness",
                )
            )
            traits.append(
                {
                    "origin": origin,
                    "text": text,
                    "rule": rule,
                    "status": "supported"
                    if rule
                    else "outside_settlement_income"
                    if outside
                    else "unmodeled",
                }
            )
    return {
        "faction": faction,
        "enabled": True,
        "source_url": record["source_url"],
        "source_sha256": record["sha256"],
        "ruling_party_identified": record["ruling_party_identified"],
        "traits": traits,
    }


def rules(traits, kind):
    return [
        record["rule"]
        for record in traits["traits"]
        if record["rule"] and record["rule"][0] == kind
    ]
