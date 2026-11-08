"""Compare archived economic facts, raw effects and current public detail pages."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from games.tw.multigame.detail import detail_record
from games.tw.multigame.sources import Sources
from games.tw.rome2.catalog import CATALOG
from games.tw.rome2.effects import CATEGORIES, LABELS, TARGETS, fact_effect, raw_effect


def observation(text):
    if "Edict:" in text or "edict:" in text:
        return None
    body = re.sub(r" \((?:this_|regions_|in_all_|all regions|all provinces)[^)]*\)$", "", text)
    if match := re.fullmatch(r"([+-]?\d+) wealth from (.+)", body):
        label = match[2]
        if label == "learning (culture)":
            return "wealth", ("culture_learning",), int(match[1])
        if label in LABELS:
            targets = TARGETS[LABELS[label]]
            if len(targets) == 1 and targets[0] in CATEGORIES:
                return "wealth", targets, int(match[1])
    if match := re.match(r"([+-]?\d+) food(?:$| \()", body):
        return "food", (), int(match[1])
    if match := re.fullmatch(
        r"([+-]?\d+) public order per turn(?: \((?:squalor|sanitation)\))?", body
    ):
        return "order", (), int(match[1])
    effect = fact_effect(body)
    if effect and effect.kind in {"wealth_percent", "tax_percent", "order"}:
        return effect.kind, effect.targets, effect.value
    return None


def compare(building, public_facts):
    raw = Counter()
    for row in building["effects"]:
        effect = raw_effect(row["id"], row["value"])
        if effect and effect.kind in {
            "wealth",
            "wealth_percent",
            "tax_percent",
            "food",
            "order",
        }:
            raw[(effect.kind, effect.targets, effect.value)] += 1
    seen = Counter(o for text in public_facts if (o := observation(text)))
    return {
        "displayed_not_matched": [
            {"kind": k, "targets": list(t), "value": v, "count": n}
            for (k, t, v), n in (seen - raw).items()
        ],
        "raw_not_displayed": [
            {"kind": k, "targets": list(t), "value": v, "count": n}
            for (k, t, v), n in (raw - seen).items()
        ],
        "matched": sum((seen & raw).values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rome2-detail"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Also cross-check current Honga detail pages",
    )
    parser.add_argument("--output", type=Path, default=Path("reports/rome2-source-audit.json"))
    args = parser.parse_args(argv)
    data = json.loads(CATALOG.read_text())
    sources = Sources(args.cache, args.offline)
    checks = {}
    for key, building in data["buildings"].items():
        checks[key] = {
            "catalog_display_vs_raw": compare(building, building["facts"]),
            "display_source": building.get("display_source", "official_archive"),
        }
    if args.download:
        wanted = {}
        for key, building in data["buildings"].items():
            faction = building["occurrences"][0]["factions"][0]
            url = "https://www.honga.net/totalwar/rome2/building.php?" + urlencode(
                {"l": "en", "v": "rome2", "f": faction, "b": key}
            )
            wanted[url] = key
        for url, html in sources.many(wanted).items():
            key = wanted[url]
            detail = detail_record(html)
            checks[key]["honga_vs_raw"] = compare(data["buildings"][key], detail["facts"])
            checks[key]["current_public_detail"] = {**detail, "source_url": url}
    payload = {
        "schema_version": 1,
        "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        "building_checks": checks,
        "sources": sorted(sources.records.values(), key=lambda r: r["url"]),
        "interpretation": (
            "Matches compare displayed numeric facts, not proof of equivalent "
            "recipient scopes or installed patch. Missing/changed display facts "
            "remain visible; no raw numbers are silently replaced."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    archived = sum(
        bool(r["catalog_display_vs_raw"]["displayed_not_matched"]) for r in checks.values()
    )
    current = sum(
        bool(r.get("honga_vs_raw", {}).get("displayed_not_matched")) for r in checks.values()
    )
    print(
        (
            "Checked "
            f"{len(checks)}"
            " buildings; archived display mismatches="
            f"{archived}"
            "; current Honga display mismatches="
            f"{current}"
        ),
        flush=True,
    )
    return payload


if __name__ == "__main__":
    main()
