"""Add Desert Kingdoms and replace archival research with scoped public facts."""

import argparse
import copy
import hashlib
import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from games.tw.multigame.detail import detail_record
from games.tw.multigame.html import Document
from games.tw.multigame.import_catalogues import query
from games.tw.multigame.sources import Sources
from games.tw.rome2.import_data import DATA, read_table
from games.tw.rome2.model import CATALOG

DLC = ("rom_kush", "rom_masaesyli", "rom_nabatea", "rom_saba")


def url(page, **kwargs):
    return (
        "https://www.honga.net/totalwar/rome2/"
        + page
        + ".php?"
        + urlencode({"l": "en", "v": "rome2", **kwargs})
    )


def dlc_role(chain):
    if chain == "dk_all_city":
        return "Provincial Capital", "Province Capital"
    if chain == "dk_all_minor_settlement":
        return "Minor Settlement", "Minor Settlement"
    if chain.startswith("dk_minor_"):
        return "Minor Settlement", chain.removeprefix("dk_minor_")
    if chain.endswith("city_centre"):
        return "City Centre", "City Centre"
    if chain.endswith("town_centre"):
        return "City Centre", "Town Centre"
    if chain in {"dk_all_industry", "dk_kush_industry"}:
        return "Industrial", "Industrial"
    if chain == "all_mine":
        return "Industrial", "Minor Settlement"
    if chain == "east_tax":
        return "City Centre", "Tax"
    if chain == "east_agriculture":
        return "Agricultural", "Agriculture"
    if chain == "east_port":
        return "Port", "Port"
    if chain == "dk_gen_sanitation":
        return "Sanitation", "Sanitation"
    if chain == "dk_saba_marib_dam":
        return "Sanitation", "Marib Dam"
    if "military" in chain:
        return "Military", "Training" if "training" in chain else "Recruitment"
    raise ValueError(f"Unclassified Desert Kingdoms chain: {chain}")


def strip_scope(text):
    if re.fullmatch(r"[+-]?\d+ food \(all regions\)", text):
        return text.removesuffix(" (all regions)") + " in all regions"
    if re.fullmatch(r"[+-]?\d+ food \(all provinces\)", text):
        return text.removesuffix(" (all provinces)") + " in all provinces"
    return re.sub(
        r" \((?:this_|regions_|in_all_|all provinces|all regions|all characters|factionwide)[^)]*\)$",
        "",
        text,
    )


def tree_links(html, faction):
    keys, nodes = set(), {}
    for anchor in Document(html).root.nodes("a"):
        href = anchor.attrs.get("href", "")
        if not href.startswith("technology.php?"):
            continue
        values = query(href)
        if values.get("f") != faction:
            continue
        if "t" in values:
            keys.add(values["t"])
        if "n" in values:
            nodes[values["n"]] = anchor.text()
    if not keys:
        raise ValueError(f"Public technology tree missing: {faction}")
    return sorted(keys), nodes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rome2-public"))
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(CATALOG.read_text())
    public_path = DATA.parents[1] / "multigame/data/rome2.json"
    public = json.loads(public_path.read_text())
    data.setdefault("technologies_archived", copy.deepcopy(data["technologies"]))
    for building in data["buildings"].values():
        building.setdefault("display_source", "official_archive")
    effects = defaultdict(list)
    for key, effect, amount, scope in read_table("building_effects_junction_table.tsv"):
        effects[key].append({"id": effect, "value": int(amount), "scope": scope})
    excluded = []
    for faction in DLC:
        data["factions"][faction] = public["factions"][faction]
        for key in public["rosters"][public["factions"][faction]["roster_id"]][
            "buildings"
        ]:
            b = public["buildings"][key]
            if key.startswith(("3c_", "inv_", "rom_slum")):
                excluded.append(
                    {
                        "faction": faction,
                        "building": key,
                        "reason": "other_campaign_or_slum_not_a_fresh_economic_build_option",
                    }
                )
                continue
            category, title = dlc_role(b["chain"])
            match = re.search(r"_(\d+)(?:_[a-z]+)?$", key)
            if not match or (
                not effects[key]
                and any(
                    re.search(r"wealth|food|public order|tax rate", s)
                    for s in b["facts"]
                )
            ):
                raise ValueError(
                    f"Missing numeric level/effects for DLC building: {key}"
                )
            occurrence = {
                "culture": "rom_Eastern",
                "name": b["name"],
                "category": category,
                "chain_title": title,
                "factions": [faction],
                "source_url": b["source_url"],
                "eligibility_evidence": "Honga faction-specific roster, excluding other-campaign prefixes; installed building_sets validation remains",
            }
            if b["chain"] == "dk_saba_marib_dam":
                occurrence["allowed_regions"] = [
                    k for k, r in data["regions"].items() if r["name"] == "Marib"
                ]
            if key not in data["buildings"]:
                data["buildings"][key] = {
                    "id": key,
                    "name": b["name"],
                    "level": int(match[1]),
                    "construction_cost": b["construction_cost"],
                    "facts": b["facts"],
                    "effects": effects[key],
                    "has_raw_effect_rows": True,
                    "occurrences": [],
                    "display_source": "honga_public",
                }
            occurrences = data["buildings"][key]["occurrences"]
            existing = next((o for o in occurrences if faction in o["factions"]), None)
            if existing is not None:
                existing.update(occurrence)
            else:
                occurrences.append(occurrence)
    # Spice settlements were introduced after the archived official trees.
    for key, building in public["buildings"].items():
        if not re.fullmatch(r"(?:barb|greek|east|rome)_spice_[1-4]", key):
            continue
        variants_for_key = [
            r for r in read_table("building_culture_variants_table.tsv") if r[0] == key
        ]
        if not variants_for_key:
            raise ValueError(f"Missing raw spice culture variant: {key}")
        eligible = [
            f
            for f in data["factions"]
            if key in public["rosters"][public["factions"][f]["roster_id"]]["buildings"]
        ]
        data["buildings"][key] = {
            "id": key,
            "name": building["name"],
            "level": int(key[-1]),
            "construction_cost": building["construction_cost"],
            "facts": building["facts"],
            "effects": effects[key],
            "has_raw_effect_rows": bool(effects[key]),
            "display_source": "honga_public",
            "occurrences": [
                {
                    "culture": variants_for_key[0][1],
                    "name": building["name"],
                    "category": "Minor Settlement",
                    "chain_title": "Spice",
                    "factions": eligible,
                    "source_url": building["source_url"],
                    "eligibility_evidence": "Honga faction-specific rosters plus raw culture variant; later resource absent from official archive",
                }
            ],
        }
    sources = Sources(args.cache, args.offline)
    # Honga's index has broken DK religious junctions, although individual
    # building pages and explicit faction-specific raw variants are available.
    detail_sources = Sources(Path(".cache/rome2-detail"), args.offline)
    variants = {
        r[0]: r
        for r in read_table("building_culture_variants_table.tsv")
        if r[3] in DLC and r[0] not in public["buildings"]
    }
    wanted_buildings = {
        url("building", f=r[3], b=key): key for key, r in variants.items()
    }
    for source_url, html in detail_sources.many(wanted_buildings).items():
        key = wanted_buildings[source_url]
        row = variants[key]
        detail = detail_record(html)
        if not detail["name"] or detail["metadata"].get("Level Name") != key:
            raise ValueError(f"Missing explicit variant detail: {key}")
        if "_religious" in key:
            category, title = "Religious", "Religious"
        elif "_military" in key or "_stables" in key:
            category, title = "Military", "Recruitment"
        elif key == "dk_all_city_5":
            category, title = "Provincial Capital", "Province Capital"
        else:
            raise ValueError(f"Unclassified explicit faction variant: {key}")
        data["buildings"][key] = {
            "id": key,
            "name": detail["name"],
            "level": int(detail["metadata"]["Building Level"]),
            "construction_cost": int(detail["metadata"]["Create Cost"]),
            "facts": detail["facts"],
            "effects": effects[key],
            "has_raw_effect_rows": bool(effects[key]),
            "display_source": "honga_public_detail",
            "occurrences": [
                {
                    "culture": row[1],
                    "name": row[4],
                    "category": category,
                    "chain_title": title,
                    "factions": [row[3]],
                    "source_url": source_url,
                    "eligibility_evidence": "Explicit faction-specific row in repository building_culture_variants table; missing from Honga index; installed building_sets still need validation",
                }
            ],
        }
    data["raw_variant_supplement"] = {
        "buildings": sorted(variants),
        "source_records": sorted(
            detail_sources.records.values(), key=lambda r: r["url"]
        ),
        "reason": "Public DK index omits these faction-specific raw variants, including temples; detail pages remain available",
    }
    index_urls = {url("technology", f=f): f for f in data["factions"]}
    trees, coverage, tech_owners = {}, {}, defaultdict(list)
    for source_url, html in sources.many(index_urls).items():
        faction = index_urls[source_url]
        ids, nodes = tree_links(html, faction)
        trees[faction] = ids
        for key in ids:
            tech_owners[key].append(faction)
        # Zero-count DK branches are visible in Honga's navigation but have no
        # leaf data. Do not call that a complete researched economy profile.
        detail_text = Document(html).root.text()
        missing = [
            key
            for key, label in nodes.items()
            if key.startswith("dk_")
            and not key.endswith("_top")
            and re.search(re.escape(label) + r" \(0\)", detail_text)
        ]
        coverage[faction] = {
            "source_url": source_url,
            "visible_technologies": len(ids),
            "missing_branch_nodes": missing,
            "complete_public_tree": not missing,
            "archived_ids_not_in_current_tree": sorted(
                set(data["technologies_archived"].get(faction, {})) - set(ids)
            ),
        }
    wanted = {
        url("technology", f=owners[0], t=key): key
        for key, owners in tech_owners.items()
    }
    technologies, unresolved = {}, []
    print(
        f"Fetching {len(wanted)} unique technology detail pages for {len(trees)} factions",
        flush=True,
    )

    def fetch_one(source_url):
        try:
            return source_url, sources.get(source_url), None
        except (RuntimeError, FileNotFoundError) as error:
            return source_url, None, str(error)

    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(fetch_one, wanted))
    errors = []
    for source_url, html, error in responses:
        key = wanted[source_url]
        if error:
            unresolved.append(key)
            errors.append({"technology": key, "source_url": source_url, "error": error})
            continue
        record = detail_record(html)
        if not record["name"]:
            unresolved.append(key)
            continue
        technologies[key] = {
            "id": key,
            "name": record["name"],
            "facts": [strip_scope(s) for s in record["facts"]],
            "scoped_facts": record["facts"],
            "source_url": source_url,
            "explicit_no_effect": record["explicit_no_effect"],
        }
    data["technologies"] = {}
    for faction, ids in trees.items():
        missing_ids = sorted(set(ids) - technologies.keys())
        coverage[faction]["unresolved_technology_ids"] = missing_ids
        coverage[faction]["complete_public_tree"] &= not missing_ids
        data["technologies"][faction] = {
            key: technologies[key] for key in ids if key in technologies
        }
    data["technology_coverage"] = coverage
    data["technology_fetch_errors"] = errors
    data["public_source_records"] = sorted(
        sources.records.values(), key=lambda r: r["url"]
    )
    data["dlc_exclusions"] = excluded
    data["schema_version"] = 2
    data["faction_trait_catalog_sha256"] = hashlib.sha256(
        public_path.read_bytes()
    ).hexdigest()
    data["verification"] = (
        "Raw repository building effect IDs/scopes; Honga public faction traits and current visible technology facts; official archive supplies placement trees for original 32 factions, Honga supplies four Desert Kingdoms rosters. Public data consistency is audited separately. No installed patch certificate; incomplete research trees are explicitly blocked in all-research mode."
    )
    data["missing"] = [
        "Installed patch and building_sets validation",
        "Honga omits some Desert Kingdoms research branches; all-research comparison unavailable for incomplete trees",
        "World resource/wonder references are separately versioned in world.json",
    ]
    CATALOG.write_text(json.dumps(data, indent=2) + "\n")
    print(
        f"Imported {len(data['buildings'])} buildings and {len(data['factions'])} factions; complete visible research profiles: {sum(c['complete_public_tree'] for c in coverage.values())}",
        flush=True,
    )
    return data


if __name__ == "__main__":
    main()
