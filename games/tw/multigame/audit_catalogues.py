"""Check the public reference catalogs and identify blockers to full rankings."""

import argparse
import json
import re
from pathlib import Path

from games.tw.multigame.import_catalogues import DATA


def audit(catalog):
    game = catalog["game"]
    buildings, factions = catalog["buildings"], catalog["factions"]
    errors, placeholders = [], []
    for key, building in buildings.items():
        if building["id"] != key:
            errors.append({"building": key, "error": "identity mismatch"})
        for field in ("construction_cost", "construction_turns", "upkeep"):
            value = building.get(field)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                errors.append({"building": key, "error": "invalid " + field})
        for text in building["facts"] + building.get("clan_facts", []):
            if re.search(r"%[+-]?n", text):
                placeholders.append(
                    {
                        "building": key,
                        "fact": text,
                        "source_url": building["source_url"],
                    }
                )
    for faction_id, faction in factions.items():
        if "roster_id" not in faction:
            continue
        roster = catalog.get("rosters", {}).get(faction["roster_id"])
        if roster is None or set(roster["buildings"]) - buildings.keys():
            errors.append(
                {"faction": faction_id, "error": "missing roster/building reference"}
            )
    if len({s["url"] for s in catalog["sources"]}) != len(catalog["sources"]):
        errors.append({"error": "duplicate source identities"})
    if any(not re.fullmatch(r"[a-f0-9]{64}", s["sha256"]) for s in catalog["sources"]):
        errors.append({"error": "invalid source hash"})
    gaps = {
        "shogun2": [
            "Archived encyclopedia patch is unspecified",
            "Clan traits are descriptive; numeric magnitudes need installed effect tables",
            "Province pages provide names, not numerical fertility/resource/starting wealth data",
            "Food-surplus growth, town wealth and tax-state inputs need a time/scenario model",
            "Faction/religion/unique-building legality needs installed tables",
        ],
        "rome2": [
            "Public roster visibility is not proof of faction/campaign eligibility",
            "No separate upkeep column; maintenance effects must be interpreted",
            "Technology, edict, family, slavery and campaign inputs need validated tables",
            "Settlement capacities, food sharing and province scopes need game-specific validation",
        ],
        "three_kingdoms": [
            "Numeric placeholders include building-slot values",
            "Public rosters mix settlement traditions; faction restrictions are not certified",
            "Faction/leader/reform/population effects have not been imported from installed tables",
            "The food-cost metadata column must not be confused with recurring food effects",
            "Commandery/county slot and resource rules need installed tables",
        ],
    }
    return {
        "game": game,
        "faction_entries": len(factions),
        "building_records": len(buildings),
        "distinct_public_rosters": len(catalog.get("rosters", {})),
        "technology_records": len(catalog.get("technologies", {})),
        "province_names": len(catalog.get("regions", {})),
        "source_responses": len(catalog["sources"]),
        "numeric_placeholder_count": len(placeholders),
        "numeric_placeholders": placeholders,
        "missing_separate_upkeep_values": sum(
            b.get("upkeep") is None for b in buildings.values()
        ),
        "identity_conflicts": catalog.get("conflicts", []),
        "integrity_errors": errors,
        "ready_for_full_economy_model": False,
        "required_validation": gaps[game],
        "note": "Counts measure imported reference facts, not modeled mechanics or completeness. Missing numbers are not substituted with zero.",
    }


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data", type=Path, default=DATA)
    cli.add_argument("--output", type=Path, default=DATA / "coverage.json")
    args = cli.parse_args(argv)
    report = {
        "catalogs": [
            audit(json.loads((args.data / (g + ".json")).read_text()))
            for g in ("shogun2", "rome2", "three_kingdoms")
        ]
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for row in report["catalogs"]:
        print(
            row["game"],
            row["building_records"],
            "buildings,",
            row["faction_entries"],
            "factions,",
            row["numeric_placeholder_count"],
            "placeholder facts,",
            len(row["integrity_errors"]),
            "integrity errors",
        )
    if any(row["integrity_errors"] for row in report["catalogs"]):
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
