"""Refresh public evidence for excluded special buildings without changing eligibility."""

import argparse
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from games.tw.multigame.detail import detail_record
from games.tw.multigame.html import Document
from games.tw.multigame.sources import Sources
from games.tw.rome2.audit_sources import compare
from games.tw.rome2.catalog import CATALOG
from games.tw.rome2.import_public import url

AUDIT = CATALOG.parent / "special_buildings_coverage.json"


def _links(node, source_url):
    result = []
    for anchor in node.nodes("a"):
        href = anchor.attrs.get("href", "")
        if not href or "/faction/" in href:
            continue
        icon = next(anchor.nodes("img"), None)
        name = anchor.text()
        if icon is not None:
            name = icon.attrs.get("data-title", icon.attrs.get("alt", name))
        result.append({"name": name, "url": urljoin(source_url, href)})
    return result


def _official_requirements(document, factions, source_url):
    requirements = []
    for table in document.nodes("table"):
        if "requires-table" not in table.attrs.get("class", "").split():
            continue
        for cell in table.nodes("td"):
            groups = list(cell.nodes("div", **{"class": "faction-nested"}))
            for group in groups or [cell]:
                owners = {
                    a.attrs["href"].rsplit("/", 1)[-1]
                    for a in group.nodes("a")
                    if a.attrs.get("href", "").startswith("/en/faction/")
                }
                if owners and not owners.intersection(factions):
                    continue
                requirements.append(
                    {
                        "label": cell.text(),
                        "factions": sorted(owners.intersection(factions)),
                        "links": _links(group, source_url),
                    }
                )
    return requirements


def official_detail(html, building, source_url):
    """Read this building's effects, not other buildings' tooltip effects."""
    document = Document(html).root
    title = next(document.nodes("h1"), None)
    abilities = next(document.nodes("ul", **{"class": "abilities"}), None)
    expected = urlparse(source_url).path.removesuffix("/index.html").rstrip("/")
    selected = {
        anchor.attrs.get("href", "").rstrip("/")
        for anchor in document.nodes("a")
        if "selected" in anchor.attrs.get("class", "").split()
    }
    if (
        title is None
        or title.text() != building["name"]
        or abilities is None
        or expected not in selected
    ):
        raise ValueError("Official building identity/effect section does not match catalog")
    factions = {f for occurrence in building["occurrences"] for f in occurrence["factions"]}
    return {
        "kind": "official_encyclopedia",
        "name": title.text(),
        "facts": [node.text() for node in abilities.nodes("li")],
        "requirements": _official_requirements(document, factions, source_url),
        "scope_warning": "Displayed facts do not consistently identify effect recipients.",
    }


def honga_detail(html, building, source_url):
    record = detail_record(html)
    if record["metadata"].get("Level Name") != building["id"]:
        raise ValueError("Honga building key does not match catalog")
    requirements = []
    for table in Document(html).root.nodes("table", **{"class": "table_stat"}):
        for cell in table.nodes("td"):
            label = next(cell.nodes("p"), None)
            if label is not None and label.text().startswith("Require "):
                requirements.append(
                    {
                        "label": label.text(),
                        "value": record["metadata"].get(label.text(), ""),
                        "links": _links(cell, source_url),
                    }
                )
    return {"kind": "honga_detail", **record, "requirements": requirements}


def source_requests(building):
    official = {
        occurrence["source_url"]
        for occurrence in building["occurrences"]
        if occurrence["source_url"].startswith("https://r2encv2.totalwar.com/")
    }
    faction = building["occurrences"][0]["factions"][0]
    return [*sorted(official), url("building", f=faction, b=building["id"])]


def fetch_detail(sources, building, source_url):
    try:
        html = sources.get(source_url)
        parser = official_detail if "r2encv2.totalwar.com" in source_url else honga_detail
        record = parser(html, building, source_url)
        return {
            **record,
            "source": sources.records[source_url],
            "display_vs_catalog_raw": compare(building, record["facts"]),
        }
    except (RuntimeError, OSError, ValueError) as error:
        return {"source_url": source_url, "error": str(error)}


def refresh_audit(baseline, catalog, sources):
    audit = copy.deepcopy(baseline)
    buildings = {k: b for k, b in catalog["buildings"].items() if b["level"] > 4}
    jobs = [(key, source_url) for key, b in buildings.items() for source_url in source_requests(b)]

    def fetch(job):
        key, source_url = job
        return key, fetch_detail(sources, buildings[key], source_url)

    details = {key: [] for key in buildings}
    with ThreadPoolExecutor(max_workers=sources.workers) as pool:
        for key, record in pool.map(fetch, jobs):
            details[key].append(record)
    for row in audit["level_five_buildings"]:
        row["public_details"] = details[row["id"]]
        row["unresolved_rules"] = list(audit["rule_evidence_needed"])
        row["status"] = "excluded_pending_rules"
    audit["schema_version"] = 2
    audit["audited_at_utc"] = datetime.now(UTC).isoformat()
    audit["catalog_sha256"] = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    records = [record for group in details.values() for record in group]
    audit["public_detail_summary"] = {
        "buildings": len(buildings),
        "pages_checked": len(records),
        "pages_parsed": sum("error" not in r for r in records),
        "pages_failed": sum("error" in r for r in records),
        "buildings_with_public_requirements": sum(
            any(r.get("requirements") for r in group) for group in details.values()
        ),
        "pages_with_numeric_disagreement": sum(
            bool(
                r.get("display_vs_catalog_raw", {}).get("displayed_not_matched")
                or r.get("display_vs_catalog_raw", {}).get("raw_not_displayed")
            )
            for r in records
        ),
        "newly_enabled_buildings": 0,
        "interpretation": (
            "Public prerequisite lists are partial observations, not eligibility certificates. "
            "A missing resource/technology/cap field does not prove no requirement. "
            "Numeric comparisons do not certify scope, first-builder rewards or game patch."
        ),
    }
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path(".cache/rome2-specials"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, default=AUDIT)
    args = parser.parse_args(argv)
    audit = refresh_audit(
        json.loads(AUDIT.read_text()),
        json.loads(CATALOG.read_text()),
        Sources(args.cache, args.offline),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit["public_detail_summary"], indent=2))
    return audit


if __name__ == "__main__":
    main()
