"""Import static economic facts from the historical vanilla 1.2.0 reference."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from games.tw.three_kingdoms.import_effects import EffectMappings, building_variants
from games.tw.three_kingdoms.source import PIN, REPOSITORY, RULESET, SourceArchive

DATA = Path(__file__).parent / "data"
CAMPAIGN = "3k_main_campaign_map"
YELLOW_TURBAN_TRAIT_BUNDLES = {
    "3k_main_faction_yellow_turban_anding": "3k_ytr_faction_trait_gong_du",
    "3k_main_faction_yellow_turban_rebels": "3k_ytr_faction_trait_he_yi",
    "3k_main_faction_yellow_turban_taishan": "3k_ytr_faction_trait_huang_shao",
}
YELLOW_TURBAN_CORROBORATION = "https://steamcommunity.com/sharedfiles/filedetails/?id=1925732692"


def _group(archive: SourceArchive, table: str, key: str, value: str) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in archive.table(table):
        grouped[row[key]].append(row[value])
    return dict(grouped)


def _requirements(archive: SourceArchive) -> dict[str, dict]:
    resources = _group(
        archive,
        "faction_resources_requirement_set_to_resources_junctions",
        "set_id",
        "faction_resource_id",
    )
    sets = {r["set_id"]: r for r in archive.table("faction_resources_requirement_sets")}
    return {
        r["building_level_record"]: {
            "operator": sets[r["set_id"]]["operator_key"],
            "resources": resources[r["set_id"]],
        }
        for r in archive.table("faction_resources_building_levels_requirements_junctions")
    }


def _building_kind(key: str) -> str:
    if key.startswith("3k_city_"):
        return "city"
    if key.startswith("3k_resource_"):
        return "resource"
    return "district"


def _buildings(archive: SourceArchive, mappings: EffectMappings) -> dict[str, dict]:
    variants = building_variants(archive, mappings)
    chains = {r["key"]: r for r in archive.table("building_chains")}
    names = {
        r["building"]: r["name"]
        for r in archive.table("building_culture_variants")
        if not any(r[k] for k in ("faction", "culture", "subculture"))
    }
    technologies = _group(
        archive,
        "building_level_required_technology_junctions",
        "building_level_key",
        "technology_key",
    )
    provided = _group(
        archive,
        "faction_resources_building_levels_permissions_junctions",
        "building_level_record",
        "faction_resource_id_flag",
    )
    requirements = _requirements(archive)
    buildings = {}
    for row in archive.table("building_levels"):
        key = row["level_name"]
        if not key.startswith("3k_") or key not in variants:
            continue
        buildings[key] = {
            "id": key,
            "name": names.get(key, key),
            "chain": row["chain"],
            "superchain": chains[row["chain"]]["building_superchain"],
            "level": int(row["level"]),
            "kind": _building_kind(key),
            "upkeep": int(row["upkeep_cost"]),
            "construction_cost": int(row["create_cost"]),
            "construction_turns": int(row["create_time"]),
            "minimum_city_level": int(row["primary_slot_building_building_level_requirement"]),
            "faction_unique": row["faction_unique"] == "1",
            "only_in_capital": row["only_in_capital"] == "1",
            "visible": row["visible_in_ui"] == "1",
            "required_technologies": technologies.get(key, []),
            "required_resources": requirements.get(key, {"operator": "AND", "resources": []}),
            "provided_resources": provided.get(key, []),
            "effect_variants": variants[key],
        }
    return buildings


def _matches_availability(row: dict[str, str], faction: dict[str, str], culture: str) -> bool:
    values = {
        "campaign": CAMPAIGN,
        "faction": faction["key"],
        "sub_culture": faction["subculture"],
        "culture": culture,
    }
    return all(not row[key] or row[key] == value for key, value in values.items())


def _factions(archive: SourceArchive) -> dict[str, dict]:
    chains = _group(archive, "building_chain_availability_sets", "id", "building_chain")
    available = archive.table("building_chain_availabilities")
    cultures = {r["subculture"]: r["culture"] for r in archive.table("cultures_subcultures")}
    factions = {}
    for row in archive.table("factions"):
        key = row["key"]
        if not key.startswith("3k_main_faction_") or row["category"] != "playable":
            continue
        if "separatist" in key or key == "3k_main_faction_kong_zhou_separatists":
            continue
        matching = [
            r for r in available if _matches_availability(r, row, cultures[row["subculture"]])
        ]
        factions[key] = {
            "id": key,
            "name": row["screen_adjective"],
            "realm_name": row["screen_name"],
            "subculture": row["subculture"],
            "chains": sorted({c for r in matching for c in chains[r["set_id"]]}),
            "availability_sets": sorted({r["set_id"] for r in matching}),
        }
    return factions


def _reforms(archive: SourceArchive, mappings: EffectMappings) -> dict[str, dict]:
    sets = {
        r["key"]: r
        for r in archive.table("technology_node_sets")
        if r["campaign_key"] in ("", CAMPAIGN)
    }
    nodes = {
        r["technology_key"]: r
        for r in archive.table("technology_nodes")
        if r["technology_node_set"] in sets
    }
    effects: dict[str, list[dict]] = defaultdict(list)
    for row in archive.table("technology_effects_junction"):
        effects[row["technology"]].extend(
            mappings.normalize(row["effect"], row["effect_scope"], row["value"])
        )
    return {
        r["key"]: {
            "id": r["key"],
            "name": r["onscreen_name"],
            "subculture": sets[nodes[r["key"]]["technology_node_set"]]["subculture"],
            "faction": nodes[r["key"]]["faction_key"],
            "effects": effects[r["key"]],
        }
        for r in archive.table("technologies")
        if r["key"] in nodes
    }


def _leader_effects(archive: SourceArchive, factions: dict, mappings: EffectMappings) -> None:
    bundles: dict[str, list[dict]] = defaultdict(list)
    for row in archive.table("effect_bundles_to_effects_junctions"):
        bundles[row["effect_bundle_key"]].extend(
            mappings.normalize(row["effect_key"], row["effect_scope"], row["value"])
        )
    leaders = {r["localised_name"]: r for r in archive.table("frontend_faction_leaders")}
    careers: dict[str, list[dict]] = defaultdict(list)
    for row in archive.table("ceo_effect_list_to_effects"):
        if not row["optional_only_in_game_mode"]:
            careers[row["effect_list"]].extend(
                mappings.normalize(row["effect"], row["effect_scope"], row["value"])
            )
    for faction in factions.values():
        leader = leaders[faction["name"]]
        faction["leader_bundle"] = leader["faction_leader_effect_bundle"]
        career = (
            "3k_main_ceo_node_career_historical_"
            + faction["name"].lower().replace(" ", "_")
            + "_01"
        )
        if career not in careers:
            raise ValueError(f"Missing original ruler career: {career}")
        faction["leader_career"] = career
        faction["leader_effects"] = careers[career]
        faction["frontend_leader_effects"] = bundles[faction["leader_bundle"]]
        faction["leader_assumption"] = "Original named faction leader remains ruler"
        faction["specialisation_effects"] = bundles[leader["specialisation_effect_bundle"]]
        trait = YELLOW_TURBAN_TRAIT_BUNDLES.get(faction["id"])
        faction["faction_effects"] = bundles[trait] if trait else []
        faction["faction_trait_bundle"] = trait
        faction["faction_trait_corroboration"] = (
            {
                "url": YELLOW_TURBAN_CORROBORATION,
                "fact": (
                    "Each 190 CE Yellow Turban faction has a permanent -10 corruption modifier"
                ),
                "limitation": (
                    "Trait activation scripts are absent from the public database snapshot"
                ),
            }
            if trait
            else None
        )


def build_reference(archive: SourceArchive) -> dict:
    mappings = EffectMappings(archive)
    buildings = _buildings(archive, mappings)
    factions = _factions(archive)
    _leader_effects(archive, factions, mappings)
    reforms = _reforms(archive, mappings)
    resources = {
        r["faction_resource_flag"]: r["localised_description"]
        for r in archive.table("faction_resource_ids")
    }
    return {
        "schema_version": 1,
        "ruleset": RULESET,
        "campaign": CAMPAIGN,
        "source_revision": PIN,
        "source_repository": REPOSITORY,
        "source_status": (
            "Historical public vanilla-branch export; installed-build validation pending"
        ),
        "coverage": {
            "source_building_levels": len(archive.table("building_levels")),
            "imported_buildings": len(buildings),
            "excluded_buildings": [
                r["level_name"]
                for r in archive.table("building_levels")
                if r["level_name"] not in buildings
            ],
            "building_scope": (
                "190 CE base game and Yellow Turban buildings; Eight Princes excluded"
            ),
            "undated_honga_catalog_buildings": 583,
            "honga_comparison": "Separate later/undated reference; numeric values are not mixed",
            "faction_scope": (
                "Faction building eligibility and original ruler bundle facts are imported. "
                "Dynamic faction resources, diplomacy/trade, court assignments, characters, "
                "rank bonuses and scripted conditions are outside the static reference model."
            ),
        },
        "buildings": buildings,
        "factions": factions,
        "reforms": reforms,
        "resources": resources,
        "sources": sorted(archive.records.values(), key=lambda r: str(r["url"])),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(f".cache/three-kingdoms/{PIN}"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA)
    args = parser.parse_args(argv)
    data = build_reference(SourceArchive(args.cache, args.offline))
    args.output.mkdir(parents=True, exist_ok=True)
    buildings = data.pop("buildings")
    files = []
    for kind in ("city", "district", "resource"):
        # Keep normalized facts compact and separate by settlement role.
        subset = {key: value for key, value in buildings.items() if value["kind"] == kind}
        items = list(subset.items())
        for start in range(0, len(items), 120):
            filename = f"buildings_{kind}_{start // 120 + 1}.json"
            part = dict(items[start : start + 120])
            (args.output / filename).write_text(json.dumps(part, separators=(",", ":")) + "\n")
            files.append(filename)
    data["building_files"] = files
    (args.output / "reference.json").write_text(json.dumps(data, indent=2) + "\n")
    print(
        f"Imported {len(buildings)} buildings, {len(data['factions'])} factions, "
        f"{len(data['reforms'])} reforms from {PIN}"
    )


if __name__ == "__main__":
    main()
