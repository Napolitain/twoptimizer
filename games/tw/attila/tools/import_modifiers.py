"""Import technology and state-religion effect facts from TW Database."""

import argparse
import csv
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen

from games.tw.attila.tools.import_online import DATA, Scripts

SLUGS = [
    "aksum",
    "alamans",
    "alans",
    "anteans",
    "burgundians",
    "caledonians",
    "danes",
    "eastern-roman-empire",
    "ebdanians",
    "franks",
    "garamantians",
    "geats",
    "himyar",
    "huns",
    "jutes",
    "lakhmids",
    "langobards",
    "ostrogoths",
    "picts",
    "sassanid-empire",
    "saxons",
    "sclavenians",
    "suebians",
    "tanukhids",
    "vandals",
    "venedians",
    "visigoths",
    "western-roman-empire",
    "white-huns",
]


def documents(html):
    parser = Scripts()
    parser.feed(html)
    for script in parser.parts:
        if not script.startswith("self.__next_f.push("):
            continue
        try:
            push = json.loads(script[len("self.__next_f.push(") :].rstrip(";)"))
        except (ValueError, TypeError):
            continue
        if len(push) != 2 or push[0] != 1 or not isinstance(push[1], str):
            continue
        for line in push[1].splitlines():
            try:
                yield json.loads(line.split(":", 1)[1])
            except (ValueError, IndexError):
                continue


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def technologies(html):
    records = {}
    for doc in documents(html):
        for value in walk(doc):
            if not isinstance(value, dict) or not {"icons", "fx", "nodes"} <= value.keys():
                continue
            for row in value["nodes"]:
                if len(row) != 11 or row[0] in records:
                    raise ValueError("Technology source format changed or duplicated name")
                records[row[0]] = {
                    "effects": [value["fx"][i][0] for i in row[4]],
                    "prerequisites": [value["nodes"][i][0] for i in row[7]],
                }
    if not records:
        raise ValueError("No technology payload")
    return records


def religions(html):
    records = {}
    for doc in documents(html):
        for value in walk(doc):
            if not isinstance(value, dict) or not str(value.get("id", "")).startswith("att_rel_"):
                continue
            facts = []
            for node in walk(value):
                if (
                    isinstance(node, list)
                    and len(node) == 4
                    and node[:2] == ["$", "span"]
                    and isinstance(node[3], dict)
                    and str(node[3].get("className", "")).startswith("text-sm text-")
                ):
                    if not isinstance(node[3].get("children"), str):
                        raise ValueError("Religion effect source format changed")
                    facts.append(node[3]["children"])
            if value["id"] in records or not facts:
                raise ValueError("Religion source format changed or duplicate identity")
            records[value["id"]] = facts
    if len(records) != 14:
        raise ValueError("Expected 14 Grand Campaign religions")
    return records


def import_data(cache, output, offline=False):
    cache.mkdir(parents=True, exist_ok=True)
    names = {}
    with (DATA / "factions_table.tsv").open() as stream:
        for row in csv.reader(stream, delimiter="\t"):
            if row[0].startswith("att_fact_"):
                names.setdefault(row[4].casefold().replace(" ", "-"), []).append(row[0])

    def fetch(slug):
        relative = "religions" if slug == "religions" else "technologies/" + slug
        url = "https://twdatabase.com/attila/" + relative
        path = cache / (slug + ".html")
        parse = religions if slug == "religions" else technologies
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            request = Request(url, headers={"User-Agent": "twoptimizer-data-import/1.0"})
            with urlopen(request, timeout=45) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("Modifier response exceeds size limit")
            parse(raw.decode("utf-8"))
            path.write_bytes(raw)
        raw = path.read_bytes()
        html = raw.decode("utf-8")
        build = re.search(r"Steam build (?:<!--.*?-->\s*)?([0-9]+)", html)
        if not build:
            raise ValueError("Missing source game build")
        return slug, {
            "source_url": url,
            "sha256": sha256(raw).hexdigest(),
            "game_build": build[1],
            "records": parse(html),
        }

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = dict(pool.map(fetch, [*SLUGS, "religions"]))
    if len({r["game_build"] for r in records.values()}) != 1:
        raise ValueError("Refusing to mix source game builds")
    report = {
        "schema_version": 1,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "verification": "third_party_reference_not_in_game_validation",
        "faction_slugs": {f: slug for slug in SLUGS for f in names.get(slug, [])},
        "technologies": {slug: records[slug] for slug in SLUGS},
        "religions": records["religions"],
    }
    if len(report["faction_slugs"]) < 29:
        raise ValueError("Missing native faction technology identities")
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path(".cache/attila-modifiers"))
    cli.add_argument("--output", type=Path, default=DATA / "online_modifiers.json")
    cli.add_argument("--offline", action="store_true")
    args = cli.parse_args()
    report = import_data(args.cache, args.output, args.offline)
    print(
        "Imported "
        f"{len(report['technologies'])}"
        " technology trees and "
        f"{len(report['religions']['records'])}"
        " religions"
    )


if __name__ == "__main__":
    main()
