"""Recover public building details and document Three Kingdoms model blockers."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from games.tw.multigame.detail import detail_record
from games.tw.multigame.sources import Sources

DATA = Path(__file__).parent / "data"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)
    catalog_path = DATA / "three_kingdoms.json"
    catalog = json.loads(catalog_path.read_text())
    sources = Sources(Path(".cache/three-kingdoms-detail"), args.offline)
    wanted = {}
    for key, building in catalog["buildings"].items():
        faction = parse_qs(urlparse(building["source_url"]).query)["f"][0]
        url = "https://www.honga.net/totalwar/three_kingdoms/building.php?" + urlencode(
            {"l": "en", "v": "three_kingdoms", "f": faction, "b": key}
        )
        wanted[url] = key
    records = {}
    for url, html in sources.many(wanted).items():
        records[wanted[url]] = {**detail_record(html), "source_url": url}
    absent = [k for k, r in records.items() if r["explicit_no_effect"]]
    recovered = [
        k
        for k, r in records.items()
        if r["facts"] and not catalog["buildings"][k]["facts"]
    ]
    details = {
        "catalog_sha256": hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
        "buildings": records,
        "sources": sorted(sources.records.values(), key=lambda r: r["url"]),
        "interpretation": "Literal public page facts and metadata; explicit No Effect is a source statement, not proof that the game building has no effects. Conditional and faction-specific rules are not normalized away.",
    }
    output = DATA / "three_kingdoms_details.json"
    output.write_text(json.dumps(details, indent=2) + "\n")
    report = {
        "catalog_buildings": len(catalog["buildings"]),
        "detail_pages_checked": len(records),
        "explicit_no_effect_buildings": absent,
        "newly_recovered_effect_pages": recovered,
        "ready_for_complete_optimizer": False,
        "blockers": [
            {
                "issue": "Settlement administration pages omit usable city slot/population rules",
                "examples": [k for k in absent if k.startswith("3k_city_")],
            },
            {
                "issue": "Some economic buildings explicitly publish No Effect; zero is not a defensible substitute",
                "examples": [k for k in absent if "artisan_minting" in k],
            },
            {
                "issue": "Commandery/county eligibility, population income and public-order functions, corruption, faction rules, and research bonuses require a consistent numeric reference"
            },
        ],
        "official_kit_availability": "Anonymous official Steam depot access was attempted for Assembly Kit app 1012260 and denied; no authenticated installed data is available in this workspace.",
        "details_path": "games/tw/multigame/data/three_kingdoms_details.json",
        "details_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    Path("reports/three-kingdoms-readiness.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(
        f"Checked {len(records)} detail pages; {len(absent)} explicitly say No Effect; {len(recovered)} newly recovered effect pages",
        flush=True,
    )
    return report


if __name__ == "__main__":
    main()
