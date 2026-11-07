"""Import official building eligibility and technologies; retain raw DB scopes."""

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from games.tw.multigame.html import Document
from games.tw.multigame.sources import Sources

DATA = Path(__file__).parent / "data"
BASE = "https://r2encv2.totalwar.com/"
CULTURES = ("rom_Roman", "rom_Hellenistic", "rom_Barbarian", "rom_Eastern")


def entity(href, kind, base):
    path = urlparse(urljoin(base, href)).path
    match = re.fullmatch(r"/en/" + kind + r"/([^/]+)(?:/index.html)?/?", path)
    if match is None:
        raise ValueError(f"Unexpected {kind} URL: {path}")
    return match[1]


def building_records(html, url, culture):
    records = {}
    for table in Document(html).root.nodes("table"):
        if "building-chain" not in table.attrs.get("class", "").split():
            continue
        chain = table.parent
        title = next(chain.nodes("h4"), None)
        group = table
        while group is not None and group.attrs.get("class") != "accordion-group":
            group = group.parent
        if title is None or group is None:
            raise ValueError("Building hierarchy changed")
        category = next(group.nodes("h3")).text()
        factions = sorted(
            {
                entity(a.attrs["href"], "faction", url)
                for a in chain.nodes("a")
                if "/faction/" in a.attrs.get("href", "")
            }
        )
        if not factions:
            raise ValueError("Missing explicit building eligibility")
        factions = [f for f in factions if f.startswith("rom_")]
        if not factions:
            continue  # Other campaigns have different facts for shared IDs.
        for anchor in table.nodes("a"):
            if "/building/" not in anchor.attrs.get("href", ""):
                continue
            source_id = entity(anchor.attrs["href"], "building", url)
            key, separator, _ = source_id.partition(culture)
            if not separator:
                raise ValueError("Building/culture identity changed")
            icon = next(anchor.nodes("img"), None)
            if icon is None or "data-object" not in icon.attrs:
                raise ValueError(f"Building facts missing: {key}")
            facts = json.loads(icon.attrs["data-object"])
            if not {"name", "create_cost", "effects"} <= facts.keys():
                raise ValueError(f"Incomplete building facts: {key}")
            match = re.search(
                r"(?:^| )level([1-5])(?: |$)", anchor.parent.attrs.get("class", "")
            )
            if match is None:
                raise ValueError("Building tier missing")
            occurrence = {
                "culture": culture,
                "name": facts["name"],
                "category": category,
                "chain_title": title.text(),
                "factions": factions,
                "source_url": urljoin(url, anchor.attrs["href"]),
            }
            record = {
                "id": key,
                "name": facts["name"],
                "level": int(match[1]),
                "construction_cost": int(facts["create_cost"]),
                "facts": facts["effects"],
                "occurrences": [occurrence],
            }
            if key in records:
                previous = records[key]
                if any(
                    previous[k] != record[k]
                    for k in ("level", "construction_cost", "facts")
                ):
                    raise ValueError(f"Conflicting official building records: {key}")
                previous["occurrences"].append(occurrence)
            else:
                records[key] = record
    if len(records) < 100:
        raise ValueError("Incomplete official culture roster")
    return records


def technology_records(html, url):
    records = {}
    for anchor in Document(html).root.nodes("a"):
        if "/tech/" not in anchor.attrs.get("href", ""):
            continue
        key = entity(anchor.attrs["href"], "tech", url)
        icon = next(anchor.nodes("img"), None)
        if icon is None or "data-object" not in icon.attrs:
            raise ValueError(f"Technology facts missing: {key}")
        facts = json.loads(icon.attrs["data-object"])
        record = {
            "id": key,
            "name": facts["name"],
            "facts": facts["effects"],
            "source_url": urljoin(url, anchor.attrs["href"]),
        }
        if key in records and records[key] != record:
            raise ValueError("Conflicting technology records")
        records[key] = record
    if len(records) < 20:
        raise ValueError("Incomplete technology tree")
    return records


def named_regions(html):
    # Decode the official map's JSON data, without executing its scripts.
    match = re.search(r"\bvar settlement_info\s*=\s*", html)
    if match is None:
        raise ValueError("Official map payload changed")
    payload, _ = json.JSONDecoder().raw_decode(html[match.end() :])
    result = {}
    for key, fragment in payload.items():
        if not key.startswith("rom_"):
            continue
        fields = {}
        for paragraph in Document(fragment).root.nodes("p"):
            label, sep, value = paragraph.text().partition(":")
            if sep:
                fields[label] = value.strip()
        if (
            not {"Settlement Name", "Belongs to Province", "Provincial Capital"}
            <= fields.keys()
        ):
            raise ValueError(f"Incomplete region identity: {key}")
        result[key] = {
            "id": key,
            "name": fields["Settlement Name"],
            "province_name": fields["Belongs to Province"],
            "capital_name": fields["Provincial Capital"],
            "specialty_name": fields.get("Speciality"),
        }
    return result


def read_table(name):
    return list(csv.reader((DATA / name).open(), delimiter="\t"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rome2-official"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=DATA / "economy_catalog.json")
    args = parser.parse_args(argv)
    sources = Sources(args.cache, args.offline)
    urls = [BASE + "en/buildings/" + c + "/" for c in CULTURES]
    pages = sources.many(urls)
    buildings = {}
    for culture, url in zip(CULTURES, urls):
        for key, record in building_records(pages[url], url, culture).items():
            if key in buildings:
                old = buildings[key]
                if any(
                    old[k] != record[k] for k in ("level", "construction_cost", "facts")
                ):
                    raise ValueError(f"Conflicting cross-culture building: {key}")
                old["occurrences"].extend(record["occurrences"])
            else:
                buildings[key] = record
    public = json.loads((DATA.parents[1] / "multigame/data/rome2.json").read_text())
    ids = sorted(
        {
            f
            for b in buildings.values()
            for o in b["occurrences"]
            for f in o["factions"]
            if f.startswith("rom_")
        }
    )
    factions = {key: public["factions"][key] for key in ids}
    tech_urls = [BASE + "en/technologies/" + f + "/" for f in ids]
    tech_pages = sources.many(tech_urls)
    technologies = {
        f: technology_records(tech_pages[url], url) for f, url in zip(ids, tech_urls)
    }
    regions = named_regions(sources.get(BASE + "en/regions/"))
    slot_templates = defaultdict(dict)
    for _, campaign, key, slot, template in read_table(
        "start_pos_region_slot_templates_table.tsv"
    ):
        if campaign == "main_rome":
            if slot in slot_templates[key]:
                raise ValueError("Duplicate region slot template")
            slot_templates[key][slot] = template
    for key, templates in slot_templates.items():
        if (
            key not in regions
            or "primary" not in templates
            or "secondary" not in templates
        ):
            raise ValueError("Region/slot identity mismatch")
        regions[key].update(
            major=templates["primary"] == "major_primary",
            has_port="port" in templates,
            ordinary_slots=4 if templates["primary"] == "major_primary" else 2,
        )
    if regions.keys() != slot_templates.keys():
        raise ValueError("Grand Campaign region coverage mismatch")
    provinces = defaultdict(list)
    for region, province in read_table("region_to_provinces_junctions_table.tsv"):
        if region in regions:
            regions[region]["province"] = province
            provinces[province].append(region)
    effects = defaultdict(list)
    for building, effect, amount, scope in read_table(
        "building_effects_junction_table.tsv"
    ):
        if building in buildings:
            effects[building].append(
                {"id": effect, "value": int(amount), "scope": scope}
            )
    for key, record in buildings.items():
        if key not in effects and any(
            re.search(r"wealth|food|tax rate|public order", f) for f in record["facts"]
        ):
            raise ValueError(f"Building has no raw effects: {key}")
        record["effects"] = effects[key]
        record["has_raw_effect_rows"] = bool(effects[key])
    files = [
        "building_effects_junction_table.tsv",
        "start_pos_region_slot_templates_table.tsv",
        "region_to_provinces_junctions_table.tsv",
    ]
    payload = {
        "schema_version": 1,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "buildings": buildings,
        "factions": factions,
        "technologies": technologies,
        "regions": regions,
        "provinces": dict(provinces),
        "sources": sorted(sources.records.values(), key=lambda r: r["url"]),
        "repository_inputs": {
            name: hashlib.sha256((DATA / name).read_bytes()).hexdigest()
            for name in files
        },
        "faction_trait_catalog_sha256": hashlib.sha256(
            (DATA.parents[1] / "multigame/data/rome2.json").read_bytes()
        ).hexdigest(),
        "verification": "Raw repository effects and slot templates, official Emperor Edition building eligibility and technology references, Honga faction traits. Installed patch unknown; no assertion of a uniform or current patch snapshot. New Pantheon/Jupiter campaign changes are not imported.",
        "missing": [
            "Complete region resource assignments and natural-wonder numeric effects",
            "Campaign starting state and characters",
            "Installed patch validation",
            "Four later playable faction rosters absent from the official encyclopedia: Kush, Masaesyli, Nabataea and Saba",
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"Imported {len(buildings)} buildings, {len(factions)} playable Grand Campaign factions, {len(regions)} regions, {len(provinces)} provinces and {sum(map(len, technologies.values()))} faction/technology records",
        flush=True,
    )
    return payload


if __name__ == "__main__":
    main()
