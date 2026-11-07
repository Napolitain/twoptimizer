"""Import public Shogun 2, Rome II and Three Kingdoms economy catalogs.

This imports reference facts, not game assets or executable JavaScript. Every
record keeps source identities and unsupported/missing fields remain explicit.
"""

import argparse
import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from games.tw.multigame.html import Document, number
from games.tw.multigame.sources import Sources

DATA = Path(__file__).parent / "data"
ENC = "https://liquidwork.github.io/shogun2-encyclopedia/"
HONGA = "https://www.honga.net/totalwar/"


def query(url):
    return {k: values[0] for k, values in parse_qs(urlparse(url).query).items()}


def honga_url(game, page, **values):
    return HONGA + game + "/" + page + ".php?" + urlencode({"l": "en", **values})


def faction_index(html):
    factions = {}
    for anchor in Document(html).root.nodes("a"):
        href = anchor.attrs.get("href", "")
        if not href.startswith("faction.php?"):
            continue
        values = query(href)
        if "f" not in values:
            continue
        name = anchor.text() or next(
            (i.attrs.get("alt", "") for i in anchor.nodes("img")), ""
        )
        if name:
            factions[values["f"]] = {"id": values["f"], "name": name}
    if not factions:
        raise ValueError("Faction index format changed")
    return factions


def chains(html, faction):
    result = {}
    for anchor in Document(html).root.nodes("a"):
        href = anchor.attrs.get("href", "")
        if not href.startswith("building.php?"):
            continue
        values = query(href)
        if values.get("f") == faction and "chain" in values:
            result[values["chain"]] = anchor.text()
    return result


def parse_chain(html, game, chain):
    records = {}
    tables = []
    for table in Document(html).root.nodes("table"):
        rows = [
            r
            for r in table.nodes("tr")
            if r.parent is table
            or (r.parent.tag in {"tbody", "thead"} and r.parent.parent is table)
        ]
        if any("Create Time" in r.text() for r in rows):
            tables.append(rows)
    if len(tables) != 1:
        raise ValueError(
            f"Expected exactly one building table for {game}/{chain}, got {len(tables)}"
        )
    pending = None
    for row in tables[0]:
        cells = row.cells()
        ids = [
            query(a.attrs.get("href", ""))["b"]
            for a in row.nodes("a")
            if "b" in query(a.attrs.get("href", ""))
        ]
        if ids:
            if pending is not None or len(set(ids)) != 1 or len(cells) != 3:
                raise ValueError("Building identity row format changed")
            details = cells[-1].lines()
            if len(details) < 2:
                raise ValueError("Missing source building name/level")
            pending = {
                "id": ids[0],
                "name": details[1],
                "chain": chain,
                "source_level_label": details[0],
                "facts": [],
            }
        elif pending is not None:
            if len(cells) != 5:
                raise ValueError(
                    f"Building metadata row format changed for {pending['id']}"
                )
            pending["construction_turns"] = number(cells[0].text())
            pending["construction_cost"] = number(cells[1].text())
            pending["facts"] = cells[4 if game == "three_kingdoms" else 2].lines()
            pending["upkeep"] = (
                number(cells[2].text()) if game == "three_kingdoms" else None
            )
            pending["food_cost"] = (
                number(cells[3].text()) if game == "three_kingdoms" else None
            )
            pending["upkeep_semantics"] = (
                "source_column; food_cost is separate source metadata, not automatically recurring consumption"
                if game == "three_kingdoms"
                else "No separate upkeep column; explicit maintenance effects are retained in facts, not assumed zero"
            )
            if any(
                pending[k] is not None and pending[k] < 0
                for k in ("construction_turns", "construction_cost", "upkeep")
            ):
                raise ValueError("Negative source building cost")
            records[pending["id"]] = pending
            pending = None
    if pending is not None or not records:
        raise ValueError("Incomplete building table")
    return records


def faction_traits(html):
    d = Document(html).root
    blocks = [n for n in d.nodes("div") if n.attrs.get("style") == "margin-left:64px"]
    culture, parties = [], []
    for block in blocks:
        facts = block.lines()
        if facts and facts[0].startswith("Playable:"):
            parties.append(
                {
                    "playable": facts[0] == "Playable: True",
                    "facts": [
                        f
                        for f in facts[1:]
                        if not f.startswith("Initial Power:") and f != "No Effect"
                    ],
                }
            )
        elif facts:
            culture.extend(f for f in facts if f != "No Effect")
    return {"culture_facts": culture, "parties": parties}


def import_honga(game, sources, native_only=False):
    index_url = honga_url(game, "faction")
    factions = faction_index(sources.get(index_url))
    if game == "rome2":
        factions = {k: v for k, v in factions.items() if k.startswith("rom_")}
        if native_only:
            from games.tw.models.model_rome2 import Rome2Factions

            ids = {f.value for f in Rome2Factions if f.value.startswith("rom_")}
            factions = {k: v for k, v in factions.items() if k in ids}
    elif native_only:
        # Named campaign leaders, including the different building traditions.
        ids = {
            "3k_main_faction_" + name
            for name in (
                "cao_cao",
                "liu_bei",
                "sun_jian",
                "liu_biao",
                "ma_teng",
                "tao_qian",
                "yuan_shu",
                "kong_rong",
                "liu_yan",
                "gongsun_zan",
                "lu_bu",
                "shi_xie",
                "yuan_shao",
                "zhang_yan",
                "zheng_jiang",
                "dong_zhuo",
                "yellow_turban_he_yi",
                "yellow_turban_huang_shao",
                "yellow_turban_gong_du",
            )
        }
        ids.update(
            k
            for k in factions
            if k.startswith("3k_dlc") and "separatist" not in k and "nanman" in k
        )
        factions = {k: v for k, v in factions.items() if k in ids}
    pages = sources.many(honga_url(game, "building", f=f) for f in factions)
    wanted = {}
    for url, html in pages.items():
        faction = query(url)["f"]
        roster = chains(html, faction)
        factions[faction]["chains"] = sorted(roster)
        factions[faction]["source_url"] = url
        for chain, name in roster.items():
            wanted.setdefault(chain, {"faction": faction, "name": name})
    print(
        f"{game}: {len(factions)} faction rosters, {len(wanted)} distinct building chains",
        flush=True,
    )
    chain_pages = sources.many(
        honga_url(game, "building", f=r["faction"], chain=chain)
        for chain, r in wanted.items()
    )
    buildings, conflicts = {}, []
    for url, html in chain_pages.items():
        chain = query(url)["chain"]
        for key, record in parse_chain(html, game, chain).items():
            record["source_url"] = url
            if key in buildings and {
                k: v
                for k, v in buildings[key].items()
                if k not in {"source_url", "chain"}
            } != {k: v for k, v in record.items() if k not in {"source_url", "chain"}}:
                conflicts.append(
                    {"building": key, "sources": [buildings[key]["source_url"], url]}
                )
            else:
                buildings[key] = record
    for conflict in conflicts:
        buildings.pop(conflict["building"], None)
    if game == "rome2":
        trait_pages = sources.many(honga_url(game, "faction", f=f) for f in factions)
        for url, html in trait_pages.items():
            factions[query(url)["f"]]["traits"] = faction_traits(html)
    for faction in factions.values():
        faction["buildings"] = sorted(
            b["id"] for b in buildings.values() if b["chain"] in faction["chains"]
        )
    return {
        "game": game,
        "campaign_scope": "Grand Campaign faction IDs"
        if game == "rome2"
        else "Reference faction rosters across source start dates; no inferred 190-CE eligibility",
        "roster_semantics": "Public source visibility only; not proof of in-game culture/faction/script eligibility",
        "factions": factions,
        "buildings": buildings,
        "conflicts": conflicts,
        "model_readiness": "Reference catalog only; installed data required to validate economy semantics and eligibility",
    }


def enc_links(html, folder):
    return sorted(
        {
            a.attrs["href"]
            for a in Document(html).root.nodes("a")
            if a.attrs.get("href", "").startswith(folder + "/")
        }
    )


def enc_record(html, url):
    d = Document(html).root
    page = next(d.nodes("div", id="page"), None)
    if page is None or not list(page.nodes("h2")):
        raise ValueError("Encyclopedia page format changed")
    result = {
        "id": Path(urlparse(url).path).stem,
        "name": next(page.nodes("h2")).text(),
        "source_url": url,
        "facts": [],
        "clan_facts": [],
        "requires": [],
        "enables": [],
    }
    current = None
    for node in page.nodes():
        if node.tag == "h3":
            current = node.text()
        elif node.tag == "li":
            if current and (current.startswith("Basic") or current == "Effects"):
                result["facts"].append(node.text())
            elif current in {"Clan Effects", "Clan Traits"}:
                result["clan_facts"].append(node.text())
            elif current in {"Requires", "Enables"}:
                result[current.lower()].extend(
                    urljoin(url, a.attrs["href"])
                    for a in node.nodes("a")
                    if "href" in a.attrs
                )
    return result


def import_shogun(sources):
    indices = sources.many(
        ENC + file
        for file in ("buildings.html", "arts.html", "clans.html", "regions.html")
    )
    folders = {
        "buildings": "buildings.html",
        "techs": "arts.html",
        "clans": "clans.html",
        "regions": "regions.html",
    }
    records = {}
    for folder, file in folders.items():
        pages = sources.many(
            ENC + path for path in enc_links(indices[ENC + file], folder)
        )
        records[folder] = {
            r["id"]: r for url, html in pages.items() if (r := enc_record(html, url))
        }
    return {
        "game": "shogun2",
        "campaign_scope": "Sengoku main campaign; Rise/Fall of Samurai excluded",
        "factions": records["clans"],
        "buildings": records["buildings"],
        "technologies": records["techs"],
        "regions": records["regions"],
        "verification": "Archived official encyclopedia mirror; current game patch not declared. Region pages provide names/descriptions, not numerical fertility/resource/start-position tables.",
    }


def share_rosters(report):
    """Deduplicate identical reference rosters while retaining every faction."""
    rosters = {}
    for faction in report["factions"].values():
        if "chains" not in faction:
            continue
        roster = {
            "chains": faction.pop("chains"),
            "buildings": faction.pop("buildings"),
        }
        key = sha256(json.dumps(roster, sort_keys=True).encode()).hexdigest()
        rosters.setdefault(key, roster)
        faction["roster_id"] = key
        faction["roster_visibility_status"] = (
            "public_chains_present"
            if roster["chains"]
            else "no_public_chains; eligibility unknown"
        )
    if rosters:
        report["rosters"] = rosters
    return report


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--games",
        nargs="+",
        choices=("shogun2", "rome2", "three_kingdoms"),
        default=["shogun2", "rome2", "three_kingdoms"],
    )
    cli.add_argument("--cache", type=Path, default=Path(".cache/multigame"))
    cli.add_argument("--output", type=Path, default=DATA)
    cli.add_argument("--offline", action="store_true")
    cli.add_argument("--native-only", action="store_true")
    cli.add_argument("--workers", type=int, default=3)
    args = cli.parse_args(argv)
    if args.workers < 1 or args.workers > 3:
        cli.error("Use 1 to 3 source workers")
    args.output.mkdir(parents=True, exist_ok=True)
    for game in args.games:
        sources = Sources(args.cache / game, args.offline, args.workers)
        report = (
            import_shogun(sources)
            if game == "shogun2"
            else import_honga(game, sources, args.native_only)
        )
        share_rosters(report)
        report.setdefault(
            "verification",
            "Third-party reference; installed game patch/build is unspecified",
        )
        report.update(
            {
                "schema_version": 1,
                "imported_at_utc": datetime.now(UTC).isoformat(),
                "sources": sorted(sources.records.values(), key=lambda r: r["url"]),
                "native_only": args.native_only,
                "ready_for_full_economy_model": False,
                "scope_note": "Reference catalog, not a completeness claim or a faction economy ranking; validate against installed game data",
            }
        )
        path = args.output / (game + ".json")
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(
            f"{game}: imported {len(report['buildings'])} buildings, {len(report['factions'])} factions",
            flush=True,
        )


if __name__ == "__main__":
    main()
