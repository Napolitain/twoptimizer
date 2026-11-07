"""Supplement the building catalog with source-backed soil and province rules."""

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from games.tw.multigame.html import Document
from games.tw.multigame.sources import Sources

ROOT = Path(__file__).parents[1]
DATA = Path(__file__).parent / "data"
PROVINCES = "https://shogun2-encyclopedia.com/regions.html"
FOOD = (
    "https://liquidwork.github.io/shogun2-encyclopedia/how_t"
    "o_play/019b_enc_manual_food_shortages.html"
)
SLOTS = (
    "https://liquidwork.github.io/shogun2-encyclopedia/how_t"
    "o_play/018e_enc_manual_actions_campaign_construction.ht"
    "ml"
)
CLAN = "https://steamcommunity.com/sharedfiles/filedetails/?id=2215397548"
FERTILITY = {
    "Barren": 1,
    "Meager": 1.3,
    "Average": 1.5,
    "Fertile": 2,
    "Very Fertile": 3,
}
PORTS = {
    "No",
    "Coastal Village",
    "Harbour",
    "Trading Port",
    "Namban Trade Port (Spreads Christianity)",
}
SPECIALTIES = {
    "holy": "holy_site",
    "horses": "horses",
    "naval": "naval",
    "smithing": "smithing",
    "craftwork": "craftwork",
    "forest": "timber",
    "ninja": "ninja",
    "gold": "gold_mining",
    "iron": "iron_mining",
    "stone": "stone",
    "philos": "intellectual_centre",
}


def normalized(text):
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def province_records(html, names):
    records = {}
    by_name = {normalized(r["name"]): r for r in names.values()}
    for node in Document(html).root.nodes("li"):
        if not node.attrs.get("id") or "Fertility:" not in node.text():
            continue
        heading = next(node.nodes("h3"), None)
        if heading is None:
            raise ValueError("Province card format changed")
        name = heading.text().removesuffix(" Province")
        # The newer index spells the historical Kozuke province "Kozuka".
        lookup_name = {"Kozuka": "Kozuke"}.get(name, name)
        if normalized(lookup_name) not in by_name:
            raise ValueError(f"Unmatched province identity: {name}")
        reference = by_name[normalized(lookup_name)]
        fields = _province_fields(node, name)
        classes = set(node.attrs.get("class", "").split()) - {"playable", "playble"}
        if len(classes) > 1 or classes - SPECIALTIES.keys():
            raise ValueError(f"Unrecognized province specialty: {classes}")
        key = reference["id"]
        if key in records:
            raise ValueError("Duplicate province identity")
        records[key] = {
            "id": key,
            "name": reference["name"],
            "fertility": fields["Fertility"],
            "farm_multiplier": FERTILITY[fields["Fertility"]],
            "has_port": fields["Port"] != "No",
            "specialty": SPECIALTIES[next(iter(classes))] if classes else None,
            "source_fields": fields,
            "source_url": PROVINCES + "#" + node.attrs["id"],
        }
    if set(records) != set(names):
        raise ValueError(f"Province coverage differs: {set(names) - records.keys()}")
    return records


def _province_fields(node, name):
    fields = {}
    for paragraph in node.nodes("p"):
        key, sep, value = paragraph.text().partition(": ")
        if sep and key in {"Clan", "Port", "Fertility", "Speciality/Resource"}:
            fields[key] = value
    if (
        set(fields) != {"Clan", "Port", "Fertility", "Speciality/Resource"}
        or fields["Fertility"] not in FERTILITY
        or fields["Port"] not in PORTS
    ):
        raise ValueError(f"Incomplete province fields: {name}")
    return fields


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path(".cache/shogun2-rules"))
    cli.add_argument("--output", type=Path, default=DATA / "rules.json")
    cli.add_argument("--offline", action="store_true")
    args = cli.parse_args(argv)
    catalog = json.loads((ROOT / "multigame/data/shogun2.json").read_text())
    sources = Sources(args.cache, args.offline)
    pages = sources.many([PROVINCES, FOOD, SLOTS, CLAN])
    guide = Document(pages[CLAN]).root.text()
    if "10% bonus to farm wealth" not in guide:
        raise ValueError("Chosokabe numeric bonus reference changed")
    report = {
        "schema_version": 1,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "provinces": province_records(pages[PROVINCES], catalog["regions"]),
        "fertility_multipliers": FERTILITY,
        "clan_farm_percent": {"chosokabe": 10},
        "clan_religion": {
            f: "christian" if f == "otomo" else "ikko" if f == "ikko_ikki" else "buddhist"
            for f in catalog["factions"]
        },
        "castle_town_slots_by_level": {str(i): i for i in range(1, 6)},
        "shared_surplus_growth_per_province": 1,
        "tax_bonus_semantics": (
            "percentage points added to base tax rate; administration multiplier "
            "supplied separately"
        ),
        "unique_building_policy": (
            "One newly constructed legendary town building of each chain per "
            "clan; one Nanban port/quarter chain. Otomo Jesuit Colleges are not "
            "legendary. Existing conquered duplicates require separate input and "
            "are outside this benchmark."
        ),
        "christian_branches": (
            "Chapel -> Hospital -> Jesuit Seminary -> Jesuit College for Otomo; "
            "Chapel -> Mission -> Church -> Cathedral for other Christian clans"
        ),
        "sources": sorted(sources.records.values(), key=lambda r: r["url"]),
        "additional_rule_references": {
            "fertility_multipliers": (
                "https://totalwar.fandom.com/wiki/User_blog:Brainwasher5/Shogun_2_Economy_breakdown"
            ),
            "tax_percentage_points": (
                "https://forums.somethingawful.com/showthread.php?noseen"
                "=0&pagenumber=20&perpage=40&threadid=3558647"
            ),
            "unique_kabunakama": "https://totalwar.fandom.com/wiki/Kabunakama",
            "unique_mizu_shobai": (
                "https://steamcommunity.com/sharedfiles/filedetails/?id=2354740643"
            ),
            "otomo_christian_branch": "https://wiki.totalwar.com/w/Otomo_Clan_Pack.html",
        },
        "verification": (
            "Public references; current installed build still unverified. "
            "Province narrative wealth values are not used to overwrite "
            "structured building effects."
        ),
        "scope": (
            "Static domestic tax receipts; town wealth, tax, administrative "
            "efficiency and religion/order offsets are explicit scenario inputs. "
            "Trade, army expenditure, agents, first-construction race rewards, "
            "events, capture history and construction sequencing are outside the "
            "model."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Imported "
        f"{len(report['provinces'])}"
        " province soil/port/specialty records and numeric "
        "economy rules"
    )
    return report


if __name__ == "__main__":
    main()
