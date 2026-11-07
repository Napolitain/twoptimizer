"""Import factual building metadata from TW Database's public building pages.

No game installation is required. Responses are cached for offline replay;
unmatched/ambiguous identities and conflicting records are reported, never guessed.
"""

import argparse
import csv
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

DATA = Path(__file__).resolve().parents[1] / "data"
BASE = "https://twdatabase.com/attila/buildings/"
CULTURES = (
    "celtic",
    "eastern-germanic",
    "northern-germanic",
    "western-germanic",
    "caucasian",
    "desert",
    "sassanid",
    "hunnic",
    "sarmatian",
    "eastern-roman",
    "western-roman",
)


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.inside = tag == "script"

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.parts.append(data)


def find_payload(value):
    if isinstance(value, dict):
        if all(k in value for k in ("icons", "fx", "chains", "landmarks")):
            yield value
        else:
            for child in value.values():
                yield from find_payload(child)
    elif isinstance(value, list):
        for child in value:
            yield from find_payload(child)


def parse_payload(html):
    parser = Scripts()
    parser.feed(html)
    matches = []
    for script in parser.parts:
        # Decode JSON only. Never execute JavaScript from the source page.
        if not script.startswith("self.__next_f.push("):
            continue
        try:
            push = json.loads(script[len("self.__next_f.push(") :].rstrip(";)"))
        except (ValueError, TypeError):
            continue
        if len(push) != 2 or push[0] != 1 or not isinstance(push[1], str):
            continue
        for line in push[1].splitlines():
            _, separator, body = line.partition(":")
            if not separator:
                continue
            try:
                matches.extend(find_payload(json.loads(body)))
            except ValueError:
                continue
    if len(matches) != 1:
        raise ValueError(
            f"Source format changed: expected one building payload, found {len(matches)}"
        )
    return matches[0]


def normalized_name(name):
    return re.sub(r"\s+", " ", name.split(" (from ", 1)[0]).strip().casefold()


def local_identities(data_dir):
    identities = {}
    with (data_dir / "building_culture_variants_table.tsv").open() as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if row[0].startswith("att_"):
                identities.setdefault((row[9], normalized_name(row[4])), set()).add(
                    row[0]
                )
    return identities


def economic_observations(texts):
    """Translate displayed numeric facts for comparison, without inventing IDs."""
    categories = {
        "agriculture": "agriculture",
        "animal husbandry": "livestock",
        "industry": "industry",
        "culture": "culture",
        "commerce": "commerce",
        "maritime commerce": "maritime",
        "subsistence": "subsistence",
    }
    facts = []
    for text in texts:
        local = text.split(" (", 1)[0]
        scope = (
            "adjacent"
            if "adjacent" in text
            else "faction"
            if "factionwide" in text or "all provinces" in text
            else "province"
            if "province to each region" in text
            else "region"
        )
        match = re.fullmatch(r"Wealth: ([0-9]+) from (.+)", local)
        if match and match[2] in categories:
            facts.append(
                {
                    "kind": "wealth",
                    "category": categories[match[2]],
                    "reach": "building",
                    "value": float(match[1]),
                }
            )
            continue
        match = re.fullmatch(
            r"Additional wealth: \+([0-9]+) from (.+) per local fertility level", local
        )
        if match and match[2] in categories:
            facts.append(
                {
                    "kind": "fertility_wealth",
                    "category": categories[match[2]],
                    "reach": "building",
                    "value": float(match[1]),
                }
            )
            continue
        match = re.fullmatch(r"Wealth: ([+-]?[0-9]+)% from (.+) buildings", local)
        percent_categories = {
            "all": (
                "agriculture",
                "livestock",
                "industry",
                "culture",
                "commerce",
                "maritime",
                "subsistence",
            ),
            "agricultural": ("agriculture",),
            "animal husbandry": ("livestock",),
            "industrial": ("industry",),
            "cultural": ("culture",),
            "commercial": ("commerce", "maritime"),
            "agricultural and animal husbandry": ("agriculture", "livestock"),
            "industrial and agricultural": ("industry", "agriculture"),
        }
        if match and match[2] in percent_categories:
            for category in percent_categories[match[2]]:
                facts.append(
                    {
                        "kind": "wealth_percent",
                        "category": category,
                        "reach": scope,
                        "value": float(match[1]),
                    }
                )
            continue
        match = re.fullmatch(r"Tax rate: ([+-]?[0-9]+)%", local)
        if match:
            facts.append(
                {
                    "kind": "tax_percent",
                    "category": None,
                    "reach": "province" if scope == "region" else scope,
                    "value": float(match[1]),
                }
            )
            continue
        for pattern, kind in (
            (r"Food consumption: -([0-9]+)", "food_consumption"),
            (r"Food: \+([0-9]+)(?: from .+)?", "food"),
            (
                r"Additional food: \+([0-9]+) per local fertility level",
                "fertility_food",
            ),
            (
                r"Public order: ([+-]?[0-9]+)(?: from established authority)?(?: \(all provinces\))?",
                "public_order",
            ),
            (r"Squalor: \+([0-9]+)", "squalor"),
            (
                r"Sanitation: \+([0-9]+)(?: to all regions in this province)?",
                "sanitation",
            ),
        ):
            match = re.fullmatch(pattern, local)
            if match:
                facts.append(
                    {
                        "kind": kind,
                        "category": None,
                        "reach": "province"
                        if kind == "public_order" and scope == "region"
                        else scope,
                        "value": float(match[1]),
                    }
                )
                break
    return facts


def records_from_payload(payload, identities):
    records, unresolved = {}, []
    for chain, _, levels in payload["chains"]:
        for row in levels:
            if len(row) != 9:
                raise ValueError("Source building row shape changed")
            name, icon_index, level, cost, turns, upkeep, fx_indices, _, _ = row
            icon = Path(payload["icons"][icon_index]).stem
            keys = identities.get((icon, normalized_name(name)), set())
            if len(keys) != 1:
                unresolved.append(
                    {
                        "icon": icon,
                        "name": normalized_name(name),
                        "reason": "ambiguous" if keys else "not_in_local_table",
                    }
                )
                continue
            if any(
                not isinstance(v, (int, float)) or v < 0
                for v in (level, cost, turns, upkeep)
            ):
                raise ValueError("Source contains invalid building numbers")
            effects = [payload["fx"][index][0] for index in fx_indices]
            technologies = [
                t.removeprefix("Needs technology: ").split(" or ")
                for t in effects
                if t.startswith("Needs technology: ")
            ]
            # Only factual fields; no descriptions, images or unit assets.
            record = {
                "source_tree_group": chain,
                "source_level": level,
                "construction_cost": cost,
                "construction_turns": turns,
                "upkeep": upkeep,
                "required_technologies_any": technologies,
                "economic_observations": economic_observations(effects),
            }
            keys = sorted(keys)
            records[keys[0]] = record
    return records, unresolved


def import_data(cache, output, offline=False, cultures=CULTURES, data_dir=DATA):
    identities = local_identities(data_dir)
    all_records, sources, unresolved, conflicts = {}, [], [], []
    game_builds = set()
    cache.mkdir(parents=True, exist_ok=True)
    for culture in cultures:
        path = cache / f"{culture}.html"
        url = BASE + culture
        if not path.exists():
            if offline:
                raise FileNotFoundError(f"Offline source cache missing: {path}")
            request = Request(
                url, headers={"User-Agent": "twoptimizer-data-import/1.0"}
            )
            with urlopen(request, timeout=45) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("Source response exceeds size limit")
            # Validate before replacing or retaining a cached response.
            parse_payload(raw.decode("utf-8"))
            path.write_bytes(raw)
        raw = path.read_bytes()
        build = re.search(
            r"Steam build (?:<!--.*?-->\s*)?([0-9]+)", raw.decode("utf-8")
        )
        if build is None:
            raise ValueError(f"Source page no longer declares a game build: {url}")
        game_builds.add(build[1])
        if len(game_builds) != 1:
            raise ValueError("Refusing to mix source pages from different game builds")
        records, unmatched = records_from_payload(
            parse_payload(raw.decode("utf-8")), identities
        )
        for key, record in records.items():
            technologies = record.pop("required_technologies_any")
            observations = record.pop("economic_observations")
            if key in all_records and all_records[key]["metadata"] != record:
                conflicts.append(
                    {
                        "building": key,
                        "source": url,
                        "previous": all_records[key]["metadata"],
                        "incoming": record,
                    }
                )
                continue
            entry = all_records.setdefault(
                key,
                {
                    "metadata": record,
                    "sources": [],
                    "requirements_by_culture": {},
                    "observations_by_culture": {},
                },
            )
            entry["sources"].append(url)
            entry["requirements_by_culture"][culture] = technologies
            entry["observations_by_culture"][culture] = observations
        sources.append(
            {
                "url": url,
                "sha256": sha256(raw).hexdigest(),
                "matched_buildings": len(records),
                "unresolved": len(unmatched),
            }
        )
        unresolved.extend({"source": url, **record} for record in unmatched)
        print(f"{culture}: {len(records)} matched, {len(unmatched)} unresolved")
    # Drop conflicting metadata entirely rather than silently picking a version.
    for key in {record["building"] for record in conflicts}:
        all_records.pop(key, None)
    report = {
        "schema_version": 1,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "source": "TW Database public Attila building pages",
        "game_build": next(iter(game_builds)),
        "campaign": "Attila Grand Campaign",
        "verification": "third_party_reference_not_in_game_validation",
        "sources": sources,
        "buildings": dict(sorted(all_records.items())),
        "unresolved": unresolved,
        "conflicts": conflicts,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(output)
    print(
        f"Imported {len(all_records)} buildings; {len(conflicts)} conflicting observations"
    )
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path(".cache/attila-online"))
    cli.add_argument("--output", type=Path, default=DATA / "online_buildings.json")
    cli.add_argument("--offline", action="store_true")
    cli.add_argument("--cultures", nargs="+", choices=CULTURES, default=CULTURES)
    args = cli.parse_args()
    import_data(args.cache, args.output, args.offline, args.cultures)


if __name__ == "__main__":
    main()
