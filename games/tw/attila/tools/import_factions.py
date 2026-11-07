"""Import faction/culture trait facts from Honga's public Grand Campaign pages.

Only the faction-group and ruling-party effect lists are active. Opposition
party effects are retained separately, never added to the player's bonuses.
Raw responses are cached for reproducible offline imports.
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

from games.tw.attila.tools.import_online import DATA
from games.tw.models.model_attila import AttilaFactions

BASE = "https://www.honga.net/totalwar/attila/faction.php?l=en&f="


class Lines(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "blockquote", "p"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"blockquote", "p"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def lines(html):
    parser = Lines()
    parser.feed(html)
    return [
        " ".join(s.split()) for s in "".join(parser.parts).splitlines() if s.strip()
    ]


def parse_faction(html):
    """Fail on changed sections; never scrape effect text from unit tooltips."""
    if len(re.findall(r"<p>Campaign</p>main_attila", html)) != 1:
        raise ValueError("Expected exactly one Grand Campaign faction identity")
    group_marker = "<!-- Faction Group Effects -->"
    party_marker = "<!-- Political Parties Effects -->"
    if html.count(group_marker) != 1 or html.count(party_marker) != 1:
        raise ValueError("Faction trait source format changed")
    group, parties = html.split(group_marker)[1].split(party_marker)
    parties = parties.split('<div class="table-responsive">', 1)[0]
    pattern = r'<div style="margin-left:64px">(.*?)</div>'
    group_blocks = re.findall(pattern, group, re.DOTALL)
    if len(group_blocks) > 1:
        raise ValueError("Ambiguous faction-group effects")
    active, inactive = [], []
    for block in re.findall(pattern, parties, re.DOTALL):
        facts = lines(block)
        if not facts or facts[0] not in {"Playable: True", "Playable: False"}:
            raise ValueError("Political party source format changed")
        effects = [
            s
            for s in facts[1:]
            if not s.startswith("Initial Power:") and s != "No Effect"
        ]
        (active if facts[0] == "Playable: True" else inactive).append(effects)
    if len(active) > 1:
        raise ValueError("More than one ruling party")
    return {
        "culture_traits": [s for s in lines(group_blocks[0]) if s != "No Effect"]
        if group_blocks
        else [],
        "faction_traits": active[0] if active else [],
        "other_party_traits": inactive,
        "ruling_party_identified": bool(active),
    }


def import_data(cache, output, offline=False, factions=None):
    cache.mkdir(parents=True, exist_ok=True)
    factions = (
        list(factions)
        if factions is not None
        else [f.value for f in AttilaFactions if f.value.startswith("att_fact_")]
    )

    def fetch(faction):
        path = cache / (faction + ".html")
        url = BASE + faction
        if not path.exists():
            if offline:
                raise FileNotFoundError(path)
            request = Request(
                url, headers={"User-Agent": "twoptimizer-data-import/1.0"}
            )
            with urlopen(request, timeout=45) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("Faction response exceeds size limit")
            parse_faction(raw.decode("utf-8"))
            path.write_bytes(raw)
        raw = path.read_bytes()
        record = parse_faction(raw.decode("utf-8"))
        return faction, {"source_url": url, "sha256": sha256(raw).hexdigest(), **record}

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = dict(pool.map(fetch, factions))
    report = {
        "schema_version": 1,
        "imported_at_utc": datetime.now(UTC).isoformat(),
        "verification": "third_party_reference_not_in_game_validation; source patch unspecified",
        "factions": dict(sorted(records.items())),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path(".cache/attila-factions"))
    cli.add_argument("--output", type=Path, default=DATA / "online_factions.json")
    cli.add_argument("--offline", action="store_true")
    args = cli.parse_args()
    report = import_data(args.cache, args.output, args.offline)
    print(f"Imported {len(report['factions'])} faction entries")


if __name__ == "__main__":
    main()
