"""Strict joins of public Grand Campaign resource tables and region identities."""

import hashlib
import json
import re
from pathlib import Path

from games.tw.rome2.effects import TARGETS
from games.tw.rome2.model import CATALOG

DATA = Path(__file__).parent / "data"
ALIASES = {
    "Bibrecte": "Bibracte",
    "Brindisium": "Brundisium",
    "Rhodos": "Rhodes",
    "Gazaka": "Gazaca",
    "Ptholemais Theron": "Ptolemais Theron",
}
ICONS = {
    "emp_resource_leather_1.png": "leather",
    "emp_resource_gold_1.png": "gold",
    "emp_resource_lumber_1.png": "lumber",
    "rom_roman_military_equipment_weapon_2.png": "iron",
    "emp_resource_olive_oil_1.png": "olive",
    "emp_all_horse_1.png": "horse",
    "emp_resource_marble_1.png": "marble",
    "emp_commerce_wine_1.png": "wine",
    "emp_commerce_glass_1.png": "glass",
    "emp_commerce_amber_1.png": "amber",
    "emp_resource_lead_1.png": "lead",
    "emp_resource_grain_1.png": "grain",
    "emp_commerce_purple_dye_1.png": "purpledye",
    "emp_commerce_silk_1.png": "silk",
}


def normalized(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def import_world(catalog, extract):
    by_name = {normalized(r["name"]): key for key, r in catalog["regions"].items()}
    if len(by_name) != len(catalog["regions"]):
        raise ValueError("Ambiguous source region names")
    regions, conflicts = {}, []
    for row in extract["rows"]:
        cells = row["text"].split("|")
        if len(cells) != 4:
            raise ValueError("World source table shape changed")
        name = re.sub(r"【.*?】", "", cells[0]).strip()
        name = ALIASES.get(name, name)
        if normalized(name) not in by_name:
            raise ValueError(f"Unmatched world region: {name}")
        key = by_name[normalized(name)]
        if key in regions:
            raise ValueError("Duplicate world region")
        resource = _resource_cell(cells)
        source_port = bool(cells[2].strip())
        region = catalog["regions"][key]
        if source_port != region["has_port"]:
            conflicts.append(
                {
                    "region": key,
                    "field": "has_port",
                    "repository": region["has_port"],
                    "public_table": source_port,
                    "resolution": (
                        "Keep explicit repository port template; public conflict remains visible"
                    ),
                }
            )
        if row["source_capital_marker"] != region["major"]:
            raise ValueError("Public capital designation conflicts with slot templates")
        regions[key] = {
            **region,
            "resource": resource,
            "resource_assignment_status": "explicit_public_table",
            "source_port": source_port,
            "specialty_label_source": cells[3].strip() or None,
            "source_line": row["line"],
            "source_url": extract["source_url"],
        }
    if set(regions) != set(catalog["regions"]):
        raise ValueError(
            f"Incomplete resource assignments: {set(catalog['regions']) - set(regions)}"
        )
    return {
        "schema_version": 1,
        "source_declares_patch": extract["source_declares_patch"],
        "capture_method": extract["capture_method"],
        "regions": regions,
        "conflicts": conflicts,
        "verification": (
            "Community table declares patch 18. All 173 identities and capital "
            "flags match repository tables. Resource assignments are public "
            "references, not an installed-build certification; three conflicting "
            "port flags retain repository templates."
        ),
    }


def _resource_cell(cells):
    icon = re.findall(r"([^/\s†]+\.png)", cells[1])
    if len(icon) > 1 or any(i not in ICONS for i in icon):
        raise ValueError(f"Unknown resource icon: {icon}")
    if icon:
        resource = ICONS[icon[0]]
    elif not cells[1].strip():
        resource = None  # Source explicitly declares an empty resource cell.
    elif cells[1].strip() == "향신료":
        resource = "spice"
    else:
        raise ValueError(f"Unrecognized resource description: {cells[1]}")
    return resource


def main():
    extract_path = DATA / "world_source_extract.json"
    result = import_world(json.loads(CATALOG.read_text()), json.loads(extract_path.read_text()))
    result["source_extract_sha256"] = hashlib.sha256(extract_path.read_bytes()).hexdigest()
    (DATA / "world.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "Joined "
        f"{len(result['regions'])}"
        " resource assignments; "
        f"{len(result['conflicts'])}"
        " port conflicts disclosed"
    )
    return result


def province_scenario(
    province,
    faction,
    *,
    all_technologies=False,
    technology_profile="public",
    world_bonuses=True,
    owned_regions=None,
):
    from games.tw.rome2.model import Scenario, Site

    world = json.loads((DATA / "world.json").read_text())
    modifiers = json.loads((DATA / "world_modifiers.json").read_text())
    matches = {
        r["province"]
        for r in world["regions"].values()
        if normalized(province) in {normalized(r["province"]), normalized(r["province_name"])}
    }
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous province name/ID")
    key = matches.pop()
    regions = [r for r in world["regions"].values() if r["province"] == key]
    owned = set(owned_regions) if owned_regions is not None else {r["id"] for r in regions}
    if owned - world["regions"].keys():
        raise ValueError("Unknown owned region")
    applied = []
    if world_bonuses:
        for row in modifiers["modifiers"]:
            if row["region"] not in owned:
                continue
            if row["scope"] == "province" and world["regions"][row["region"]]["province"] != key:
                continue
            applied.append(
                {
                    "kind": row["kind"],
                    "value": row["value"],
                    "targets": list(TARGETS[row["target"]]) if row["target"] else [],
                    "source_region": row["region"],
                    "name": row["name"],
                    "scope": row["scope"],
                    "source_url": modifiers["source_url"],
                    "source_line": row["source_line"],
                    "interpretation": row["interpretation"],
                }
            )
    return Scenario(
        faction,
        tuple(
            Site(
                r["id"],
                major=r["major"],
                port=r["has_port"],
                resource=r["resource"],
                slots=r["ordinary_slots"],
            )
            for r in regions
        ),
        name=regions[0]["province_name"],
        all_technologies=all_technologies,
        technology_profile=technology_profile,
        modifiers=tuple(applied),
        world_profile=modifiers["profile"]
        if world_bonuses
        else "resource_map_without_wonder_bonuses",
    )


if __name__ == "__main__":
    main()
