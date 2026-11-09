"""Import the historical 190 CE commanderies, counties and placement rules.

The published DB contains additional adjacency rules, not the base campaign
graph. Those edges are retained as a partial reference and never advertised as
a complete economic-neighbour map.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from games.tw.maps.catalog import validate_map
from games.tw.three_kingdoms.source import PIN, REPOSITORY, RULESET, SourceArchive

CAMPAIGN = "3k_main_campaign_map"
POPULATION = "3k_main_pooled_resource_population"
DATA = Path(__file__).parent / "data"


def _index(rows: list[dict[str, str]], column: str) -> dict[str, dict[str, str]]:
    result = {row[column]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate geography identity: {column}")
    return result


def _campaign(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row["campaign"] == CAMPAIGN]


def _templates(archive: SourceArchive) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for row in archive.table("slot_template_to_building_superchain_junctions"):
        result[row["slot_template"]].append(row["building_superchain"])
    return {key: sorted(set(values)) for key, values in result.items()}


def _region_slots(archive: SourceArchive, known: set[str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = defaultdict(dict)
    for row in _campaign(archive.table("start_pos_region_slot_templates")):
        region, kind = row["region"], row["slot_type"]
        if region not in known or kind not in {"primary", "secondary", "port"}:
            raise ValueError("Unknown region or slot kind in geography source")
        if kind in result[region]:
            raise ValueError("Duplicate region slot template")
        result[region][kind] = row["slot_template"]
    return dict(result)


def _populations(archive: SourceArchive, starts: dict) -> tuple[dict[str, int], int]:
    """Resolve pooled population by start-position ID, using its documented UI scale."""
    resources = _index(archive.table("pooled_resources"), "key")
    scale = int(resources[POPULATION]["ui_value_scale_factor"])
    if scale <= 0:
        raise ValueError("Population resource must have a positive display scale")
    rows = [
        row
        for row in archive.table("start_pos_region_pooled_resources")
        if row["pooled_resource"] == POPULATION
    ]
    records = _index(rows, "region")
    if not records.keys() <= starts.keys():
        raise ValueError("Population references an unknown start-position region ID")
    values = {key: int(row["amount"]) for key, row in records.items()}
    if any(value < 0 for value in values.values()):
        raise ValueError("Starting population cannot be negative")
    return values, scale


def _region(key, start, definition, junction, slots, templates, populations, scale):
    primary = slots.get("primary")
    if primary is None:
        raise ValueError("Every campaign county must have a primary slot")
    if not set(slots.values()) <= templates.keys():
        raise ValueError("Unknown building slot template in campaign geography")
    result = {
        "id": key,
        "name": definition["onscreen"],
        "battle_name": definition["battle_name"],
        "commandery": junction["province"],
        "province": junction["province"],
        "capital": junction["is_capital"] == "1",
        "slot_template": primary,
        "slot_templates": dict(sorted(slots.items())),
        "primary_superchains": templates[primary],
        "secondary_superchains": templates.get(slots.get("secondary", ""), []),
        "port_superchains": templates.get(slots.get("port", ""), []),
        "initial_population": (
            populations[start["id"]] * scale if start["id"] in populations else None
        ),
        "initial_population_source_amount": populations.get(start["id"]),
        "legacy_population": int(start["population"]),
        "legacy_base_max_population": int(start["base_max_population"]),
        "slot_cap": int(start["slot_cap"]),
        "initial_faction_id": start["owning_faction"],
    }
    if not result["capital"]:
        result["resource_superchain"] = primary
    return result


def _commandery_records(regions, definitions):
    result = {}
    for key in sorted({row["commandery"] for row in regions.values()}):
        members = [row for row in regions.values() if row["commandery"] == key]
        capitals = [row["id"] for row in members if row["capital"]]
        if len(capitals) != 1 or key not in definitions:
            raise ValueError("A commandery must have one capital and a name")
        result[key] = {
            "name": definitions[key]["onscreen"],
            "capital": capitals[0],
            "regions": sorted(members, key=lambda row: (not row["capital"], row["id"])),
        }
    return result


def _additional_borders(archive, known):
    result = set()
    for row in archive.table("campaign_region_additional_adjacency_rules"):
        pair = tuple(sorted((row["first_region"], row["second_region"])))
        if pair[0] == pair[1] or not set(pair) <= known:
            raise ValueError("Invalid additional adjacency endpoint")
        result.add(pair)
    return [list(pair) for pair in sorted(result)]


def build_geography(archive: SourceArchive) -> dict:
    """Join exact campaign identities and source placement rules, failing closed."""
    start_rows = archive.table("start_pos_regions")
    starts = _index(_campaign(start_rows), "region")
    if not starts:
        raise ValueError("The 190 CE campaign has no source regions")
    definitions = _index(archive.table("regions"), "key")
    provinces = _index(archive.table("provinces"), "key")
    junctions = _index(archive.table("region_to_province_junctions"), "region")
    slots = _region_slots(archive, set(starts))
    templates = _templates(archive)
    populations, scale = _populations(archive, _index(start_rows, "id"))
    regions = {
        key: _region(
            key, row, definitions[key], junctions[key], slots[key], templates, populations, scale
        )
        for key, row in sorted(starts.items())
    }
    commanderies = _commandery_records(regions, provinces)
    borders = _additional_borders(archive, set(regions))
    return {
        "schema_version": 1,
        "game": "three_kingdoms",
        "campaign": CAMPAIGN,
        "ruleset": RULESET,
        "source_repository": REPOSITORY,
        "source_revision": PIN,
        "commanderies": commanderies,
        "regions": regions,
        "population_reference": {
            "resource": POPULATION,
            "ui_value_scale_factor": scale,
            "join": "start_pos_region_pooled_resources.region = start_pos_regions.id",
            "missing_regions": [
                key for key, row in regions.items() if row["initial_population"] is None
            ],
            "legacy_fields": (
                "Legacy population/base_max_population fields are retained for provenance only. "
                "They are not added to the pooled population or settlement capacity."
            ),
        },
        "slot_templates": templates,
        "additional_region_adjacency": borders,
        "coverage": {
            "commandery_count": len(commanderies),
            "region_count": len(regions),
            "resource_count": sum(not row["capital"] for row in regions.values()),
            "geography_complete": True,
            "adjacency_complete": False,
            "adjacency_limitation": (
                "Only additional adjacency rules are present in this DB export. "
                "Base campaign map contacts are unavailable; absent edges are unknown."
            ),
        },
        "sources": sorted(archive.records.values(), key=lambda row: row["url"]),
    }


def build_partial_map(geography: dict) -> dict:
    """Expose known edges through the shared map audit without enabling default adjacency."""
    regions = {
        key: {"name": row["battle_name"], "province": row["commandery"]}
        for key, row in geography["regions"].items()
    }
    owners = {key: row["province"] for key, row in regions.items()}
    edges = geography["additional_region_adjacency"]
    province_edges = sorted(
        {tuple(sorted((owners[a], owners[b]))) for a, b in edges if owners[a] != owners[b]}
    )
    result = {
        "schema_version": 1,
        "game": "three_kingdoms",
        "campaign": CAMPAIGN,
        "ruleset": RULESET,
        "regions": regions,
        "region_borders": edges,
        "province_borders": [list(pair) for pair in province_edges],
        "coverage": {
            "complete": False,
            "region_count": len(regions),
            "province_count": len(set(owners.values())),
            "region_border_count": len(edges),
            "province_border_count": len(province_edges),
            "limitation": geography["coverage"]["adjacency_limitation"],
        },
        "sources": geography["sources"],
    }
    validate_map(result, "three_kingdoms", owners)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/three-kingdoms-1.2.0"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA)
    args = parser.parse_args(argv)
    geography = build_geography(SourceArchive(args.cache, args.offline))
    campaign_map = build_partial_map(geography)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in (("geography.json", geography), ("campaign_map.json", campaign_map)):
        (args.output / name).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(geography["coverage"], indent=2))
    return geography


if __name__ == "__main__":
    main()
