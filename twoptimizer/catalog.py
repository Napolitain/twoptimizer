"""Source-backed, immutable choices for individual game integrations."""

import csv
from pathlib import Path

import games.tw
from games.tw.immutable import read_catalog
from twoptimizer.game_plugin import GameChoices

ROOT = Path(games.tw.__file__).resolve().parent


def read(relative: str):
    return read_catalog(ROOT / relative)


def rome_choices() -> GameChoices:
    data = read("rome2/data/economy_catalog.json")
    factions = sorted((r["name"], key) for key, r in data["factions"].items())
    provinces = [
        ("Coastal reference · 2 settlements", "coastal"),
        ("Inland reference · 2 settlements", "inland"),
        ("Grain reference · 2 settlements", "grain"),
    ]
    world = read("rome2/data/world.json")
    provinces += sorted({(r["province_name"], r["province"]) for r in world["regions"].values()})
    return GameChoices(
        factions=tuple(factions),
        provinces=tuple(provinces),
        default_faction="rom_rome",
        default_province="coastal",
        research=(
            ("Bonuses disabled · buildings unlocked", "none"),
            ("Full public research · complete trees only", "public"),
            ("Full archival research · older profile", "archived"),
        ),
        default_research="none",
    )


def shogun_choices() -> GameChoices:
    data, rules = read("multigame/data/shogun2.json"), read("shogun2/data/rules.json")
    return GameChoices(
        factions=tuple(sorted((r["name"], k) for k, r in data["factions"].items())),
        provinces=tuple(sorted((r["name"], k) for k, r in rules["provinces"].items())),
        default_faction="oda",
        default_province="jap_owari",
        research=(("All arts researched", "all"), ("No arts researched", "none")),
        default_research="all",
    )


def attila_choices() -> GameChoices:
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
            (r[1], r[0]) for r in csv.reader(stream, delimiter="\t") if r[0].startswith("att_prov_")
        )
    return GameChoices(
        factions=tuple(factions),
        provinces=tuple(provinces),
        default_faction="att_fact_eastern_roman_empire",
        default_province="att_prov_thracia",
        research=(
            ("All available technologies", "all"),
            ("No technologies researched", "none"),
        ),
        default_research="all",
    )


def three_kingdoms_choices() -> GameChoices:
    from games.tw.three_kingdoms.catalog import DEFAULT_COMMANDERY, DEFAULT_FACTION, load_data

    data = load_data()
    return GameChoices(
        factions=tuple(sorted((row["name"], key) for key, row in data["factions"].items())),
        provinces=tuple(sorted((row["name"], key) for key, row in data["commanderies"].items())),
        default_faction=DEFAULT_FACTION,
        default_province=DEFAULT_COMMANDERY,
        research=(
            ("No reforms researched", "none"),
            ("All compatible historical reforms", "all"),
        ),
        default_research="none",
    )


def faction_name(game: str, key: str) -> str:
    from twoptimizer.registry import choices

    names = {key: label for label, key in choices(game).factions}
    if game == "attila" and key not in names:
        with (ROOT / "attila/data/factions_table.tsv").open() as stream:
            names.update(
                {row[0]: row[4] for row in csv.reader(stream, delimiter="\t") if len(row) > 4}
            )
    return names[key]
