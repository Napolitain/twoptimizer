"""Source-backed choices shared by the TUI and its isolated solver worker."""

import csv
from functools import lru_cache
from pathlib import Path

import games.tw
from games.tw.immutable import freeze, read_catalog

ROOT = Path(games.tw.__file__).resolve().parent
GAMES = [
    ("Rome II", "rome2"),
    ("Attila", "attila"),
    ("Shogun 2", "shogun2"),
    ("Three Kingdoms · data incomplete", "three_kingdoms"),
    ("Hearts of Iron IV · redesign pending", "hoi4"),
]
EXACT = {
    "rome2": ("cp-sat", "cbc", "scip", "scip-nonlinear"),
    "shogun2": ("cp-sat", "cbc", "scip"),
    "attila": ("cp-sat", "cbc", "scip"),
}
NOTES = {
    "rome2": (
        "Static domestic income after modeled maintenance. Food and public"
        " order are enforced. Research bonuses default off; mature "
        "buildings remain unlocked. Public full-research mode excludes "
        "seven incomplete trees, including Rome. Named provinces include "
        "the declared community patch-18 regional bonus profile unless "
        "disabled. Each holding is independent. Public references are not "
        "installed-patch certification. No external trade, treasury "
        "interest or campaign timeline."
    ),
    "attila": (
        "Recurring settlement income, including modeled tax and "
        "maintenance. Food, sanitation and public order are enforced. "
        "Factions are compared after settlement, with the selected common "
        "religion and explicit fertility. Hordes are excluded. "
        "Technologies default researched; missing building metadata can "
        "exclude variants. No treasury interest or unsupplied "
        "trade/tribute/campaign inputs. Public references still need "
        "installed-build validation."
    ),
    "shogun2": (
        "Domestic tax income in koku per turn. Food and public order are "
        "enforced. Soil uses the selected province's source profile by "
        "default; town wealth is supplied explicitly. All arts default "
        "researched, native clan faith, no Nanban contact. No external "
        "trade, construction timeline or future growth valuation. Public "
        "references still need installed-build validation."
    ),
    "three_kingdoms": (
        "583 public building pages are audited, but 174 explicitly say No "
        "Effect, including important economic buildings. Slot placeholders"
        " and population/eligibility rules remain unresolved. No complete "
        "optimizer is available yet."
    ),
    "hoi4": (
        "The existing experiments remain available in the repository. A "
        "faithful time-based economy optimizer is pending redesign; they "
        "are not presented here as a finished solver."
    ),
}


def read(relative):
    return read_catalog(ROOT / relative)


@lru_cache
def choices(game):
    return freeze(_choices(game))


def _choices(game):
    if game == "rome2":
        data = read("rome2/data/economy_catalog.json")
        factions = sorted(((r["name"], key) for key, r in data["factions"].items()))
        provinces = [
            ("Coastal reference · 2 settlements", "coastal"),
            ("Inland reference · 2 settlements", "inland"),
            ("Grain reference · 2 settlements", "grain"),
        ]
        world = read("rome2/data/world.json")
        provinces += sorted(
            {(r["province_name"], r["province"]) for r in world["regions"].values()}
        )
        return {
            "factions": factions,
            "provinces": provinces,
            "default_faction": "rom_rome",
            "default_province": "coastal",
            "research": [
                ("Bonuses disabled · buildings unlocked", "none"),
                ("Full public research · complete trees only", "public"),
                ("Full archival research · older profile", "archived"),
            ],
            "default_research": "none",
        }
    if game == "shogun2":
        data, rules = (
            read("multigame/data/shogun2.json"),
            read("shogun2/data/rules.json"),
        )
        return {
            "factions": sorted((r["name"], k) for k, r in data["factions"].items()),
            "provinces": sorted((r["name"], k) for k, r in rules["provinces"].items()),
            "default_faction": "oda",
            "default_province": "jap_owari",
            "research": [
                ("All arts researched", "all"),
                ("No arts researched", "none"),
            ],
            "default_research": "all",
        }
    if game == "attila":
        from games.tw.attila.traits import profile

        native = {
            key
            for key in read("attila/data/online_modifiers.json")["faction_slugs"]
            if not any(word in key for word in ("rebel", "separatist"))
            and profile(key)["ruling_party_identified"]
        }
        with (ROOT / "attila/data/factions_table.tsv").open() as stream:
            factions = sorted(
                (r[4], r[0])
                for r in csv.reader(stream, delimiter="\t")
                if r[0] in native and "nomad" not in r[2]
            )
        with (ROOT / "attila/data/provinces.tsv").open() as stream:
            provinces = sorted(
                (r[1], r[0])
                for r in csv.reader(stream, delimiter="\t")
                if r[0].startswith("att_prov_")
            )
        return {
            "factions": factions,
            "provinces": provinces,
            "default_faction": "att_fact_eastern_roman_empire",
            "default_province": "att_prov_thracia",
            "research": [
                ("All available technologies", "all"),
                ("No technologies researched", "none"),
            ],
            "default_research": "all",
        }
    return {"factions": [], "provinces": []}


def faction_name(game, key):
    return {key: label for label, key in choices(game)["factions"]}[key]
