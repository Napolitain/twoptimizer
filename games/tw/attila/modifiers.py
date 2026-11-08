"""Translate source-backed technology and religion facts, retaining omissions."""

import re
from pathlib import Path

from games.tw.attila.effects import Reach, Rule
from games.tw.attila.tools.import_online import economic_observations
from games.tw.immutable import read_catalog

CULTURE_TREES = dict(
    zip(
        (
            "barbarian_celtic",
            "barbarian_germanic_east",
            "barbarian_germanic_north",
            "barbarian_germanic_west",
            "eastern_caucasian",
            "eastern_desert",
            "eastern_sassanid",
            "nomadic_hunnic",
            "nomadic_sarmatian",
            "roman_east",
            "roman_west",
        ),
        (
            "picts",
            "ostrogoths",
            "geats",
            "franks",
            "sassanid-empire",
            "garamantians",
            "sassanid-empire",
            "huns",
            "alans",
            "eastern-roman-empire",
            "western-roman-empire",
        ),
        strict=True,
    )
)
RELIGION_KEYS = dict(
    zip(
        (
            "arian",
            "catholic",
            "orthodox",
            "grecoroman",
            "celtic",
            "germanic",
            "zoroastrian",
            "manichaeist",
            "tengris",
            "slavic",
            "semitic_paganism",
            "eastern",
            "judaism",
            "other",
        ),
        (
            "chr_arian",
            "chr_catholic",
            "chr_orthodox",
            "pag_roman",
            "pag_celtic",
            "pag_germanic",
            "east_zoroastrian",
            "east_manichaeism",
            "pag_tengri",
            "pag_slavic",
            "semitic_paganism",
            "church_east",
            "judaism",
            "other",
        ),
        strict=True,
    )
)


def catalog():
    return read_catalog(Path(__file__).parent / "data/online_modifiers.json")


def technology_profile(game, researched=None, enabled=True):
    faction = getattr(getattr(game, "faction", None), "value", None)
    if faction is None or not enabled:
        return None
    data = catalog()
    slug = data["faction_slugs"].get(faction)
    inferred = slug is None
    if inferred:
        culture = game.parser.faction_to_culture[faction].subculture.removeprefix("att_sub_cult_")
        slug = CULTURE_TREES.get(culture)
    if slug is None:
        raise ValueError(f"Missing technology tree for {faction}")
    source = data["technologies"][slug]
    records = source["records"]
    active = set(records) if researched is None else set(researched)
    if unknown := active - records.keys():
        raise ValueError(f"Unknown technologies for {slug}: {sorted(unknown)}")
    disabled = {
        match[1]
        for name in active
        for text in records[name]["effects"]
        if (match := re.fullmatch(r'Disables the legacy technology "(.+)"', text))
    }
    return {
        "source_url": source["source_url"],
        "source_sha256": source["sha256"],
        "tree": slug,
        "culture_representative_for_npc": inferred,
        "active": sorted(active - disabled),
        "disabled_legacy": sorted(disabled),
        "facts": [
            {"source": name, "text": text}
            for name in sorted(active - disabled)
            for text in records[name]["effects"]
        ],
    }


def semantics(text):
    if match := re.fullmatch(r"Wealth: ([+-]?[0-9]+)% from subsistence", text):
        return [(Rule("wealth_percent", ("subsistence",)), int(match[1]))]
    if match := re.fullmatch(r"Trade income: ([+-]?[0-9]+)% trade agreement tariffs", text):
        return [(Rule("tariff_percent"), int(match[1]))]
    if match := re.fullmatch(
        r"Public order: ([+-]?[0-9]+)% penalty due to presence of other religions", text
    ):
        return [(Rule("religious_order_percent"), int(match[1]))]
    facts = economic_observations([text])
    if facts:
        return [
            (Rule(f["kind"], (f["category"],) if f["category"] else ()), f["value"]) for f in facts
        ]
    for pattern, kind in (
        (r"Corruption: ([+-]?[0-9]+)% of current value", "corruption_percent"),
        (r"Public order: ([+-]?[0-9]+) from bureaucratic reforms", "public_order"),
        (r"Growth: ([+-]?[0-9]+)", "growth"),
        (r"Religious influence: ([+-]?[0-9]+) state religion", "religion:state"),
        (r"Trade tariffs: ([+-]?[0-9]+)%", "tariff_percent"),
        (
            r"Research rate: ([+-]?[0-9]+)% for civic developments",
            "research_civil_percent",
        ),
    ):
        if match := re.fullmatch(pattern, text):
            rule = (
                Rule("metric", (kind,))
                if kind in {"growth", "religion:state", "research_civil_percent"}
                else Rule(kind)
            )
            return [(rule, int(match[1]))]
    if text == "Religious influence: +1 Arian Christianity":
        return [(Rule("metric", ("religion:arian",)), 1)]
    if match := re.fullmatch(r"Construction cost: ([+-]?[0-9]+)% for (.+) buildings", text):
        categories = {
            "main settlement": "main",
            "civic": "civic",
            "agricultural": "agriculture",
            "farm": "agriculture",
            "industrial": "industry",
            "industrial and agricultural": "industry_agriculture",
            "religious": "religious",
            "military": "military",
        }
        if match[2] in categories:
            return [(Rule("project_cost_percent", (categories[match[2]],)), int(match[1]))]
    return []


def modifier_profile(game, technology=None, scenario=None):
    scenario = scenario or {}
    if getattr(game, "faction", None) is None:
        return {"technologies": None, "religion": None, "facts": []}, []
    if technology is None:
        technology = technology_profile(game, enabled=scenario.get("technology_effects", True))
    facts = list(technology["facts"]) if technology else []
    faith = getattr(getattr(game, "religion", None), "value", None)
    religion = None
    if scenario.get("religion_traits", True) and faith not in (None, "any", "islam"):
        source = catalog()["religions"]
        key = "att_rel_" + RELIGION_KEYS[faith]
        religion = {
            "religion": faith,
            "source_url": source["source_url"],
            "source_sha256": source["sha256"],
        }
        facts.extend({"source": key, "text": text} for text in source["records"][key])
    effects = []
    for fact in facts:
        text = re.sub(r" \((?:all regions|all provinces|factionwide)\)$", "", fact["text"])
        translated = semantics(text)
        fact["status"] = (
            "modeled"
            if translated
            else "availability_rule"
            if text.startswith("Disables the legacy technology")
            else "outside_settlement_income"
            if any(
                t in text.lower()
                for t in (
                    "units",
                    "morale",
                    "army",
                    "ammunition",
                    "upkeep",
                    "recruitment",
                    "integrity",
                    "agent",
                    "siege",
                    "charge",
                    "replenishment",
                    "movement",
                    "melee",
                    "armour",
                )
            )
            else "unmodeled"
        )
        for rule, value in translated:
            effects.append((fact["source"] + ": " + fact["text"], rule, Reach.FACTION, value))
    return {"technologies": technology, "religion": religion, "facts": facts}, effects
