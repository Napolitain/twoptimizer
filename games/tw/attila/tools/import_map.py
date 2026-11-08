"""Rebuild Attila's campaign graph from published facts and the vanilla raw hex map.

Offline captures contain factual identifiers and contacts, not game artwork or
the upstream toolkit. Refreshes validate both sources before replacing artifacts.
"""

import argparse
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from games.tw.maps.catalog import region_provinces, validate_map
from games.tw.maps.import_hex import extract_contacts, parse_hex
from games.tw.maps.import_online import build_catalog, capture, fetch, serialized

DATA = Path(__file__).resolve().parents[1] / "data"
PAGE_URL = "https://twdatabase.com/attila/map"
REVISION = "d7e27bacaf9a5b4656b483b47b4e6212ad3a6cb4"
HEX_URL = (
    "https://raw.githubusercontent.com/TW-Campaign-Map-Modding-Team/CampaignMapToolkit/"
    + REVISION
    + "/Templates/main_attila_map/map.hex"
)
EXCLUDED = ("att_reg_terra_incognita",)


def capture_hex(data: bytes, retrieved_at: str | None = None) -> dict:
    model = parse_hex(data)
    if model.game != "attila" or model.campaign != "main_attila_map":
        raise ValueError("Expected vanilla Attila Grand Campaign hex map")
    return {
        "schema_version": 1,
        "source": {
            "url": HEX_URL,
            "sha256": sha256(data).hexdigest(),
            "bytes": len(data),
            "retrieved_at": retrieved_at or datetime.now(UTC).date().isoformat(),
            "revision": REVISION,
            "description": (
                "Vanilla campaign raw hex map; upstream credits OtherTomCA for raw files"
            ),
            "provenance_url": (
                "https://github.com/TW-Campaign-Map-Modding-Team/CampaignMapToolkit/blob/"
                + REVISION
                + "/README.md"
            ),
        },
        "map": {
            "game": model.game,
            "campaign": model.campaign,
            "format_version": model.version,
            "width": model.width,
            "height": model.height,
            "land_regions": list(model.land_regions),
            "sea_regions": list(model.sea_regions),
        },
        "excluded_regions": list(EXCLUDED),
        "contacts": extract_contacts(model, excluded=EXCLUDED),
    }


def _pairs(values, known):
    if not isinstance(values, list) or any(
        not isinstance(pair, list) or len(pair) != 2 for pair in values
    ):
        raise ValueError("Hex contacts must be pairs of region identities")
    pairs = {tuple(pair) for pair in values}
    if len(pairs) != len(values) or any(
        len(pair) != 2 or pair[0] >= pair[1] or not set(pair) <= known for pair in pairs
    ):
        raise ValueError("Invalid or duplicate hex contact")
    return pairs


def _validate_hex(extract, expected):
    world = extract["map"]
    if world["game"] != "attila" or world["campaign"] != "main_attila_map":
        raise ValueError("Wrong hex campaign identity")
    excluded = set(extract["excluded_regions"])
    land, sea = set(world["land_regions"]), set(world["sea_regions"])
    if len(land) != len(world["land_regions"]) or len(sea) != len(world["sea_regions"]):
        raise ValueError("Duplicate hex region identity")
    if excluded != set(EXCLUDED) or land - excluded != set(expected) or land & sea:
        raise ValueError("Hex region identities do not match the campaign")
    contacts = extract["contacts"]
    borders = _pairs(contacts["land"], set(expected))
    if not _pairs(contacts["passable_land"], set(expected)) <= borders:
        raise ValueError("Passable contacts must be geometric land borders")
    _pairs(contacts["sea"], sea)
    for a, b in _pairs(contacts["coastal"], set(expected) | sea):
        if (a in sea) == (b in sea):
            raise ValueError("A coastal contact must join land and sea")
    return borders


def build_attila_map(online: dict, hex_source: dict, expected: Mapping[str, str]) -> dict:
    result = build_catalog(online, "attila", "main_attila", expected)
    published = {tuple(pair) for pair in result["region_borders"]}
    canonical = _validate_hex(hex_source, expected)
    provinces = {
        tuple(sorted((expected[a], expected[b])))
        for a, b in canonical
        if expected[a] != expected[b]
    }
    published_provinces = {tuple(pair) for pair in result["province_borders"]}
    result["region_borders"] = [list(pair) for pair in sorted(canonical)]
    result["province_borders"] = [list(pair) for pair in sorted(provinces)]
    result["sources"].append(
        {
            **hex_source["source"],
            "extract_sha256": sha256(serialized(hex_source)).hexdigest(),
        }
    )
    result["coverage"].update(
        adjacency_kind="raw_hex_land_borders",
        region_border_count=len(canonical),
        province_border_count=len(provinces),
    )
    result["cross_validation"] = {
        "published_region_borders": [list(pair) for pair in sorted(published)],
        "matching_region_border_count": len(canonical & published),
        "hex_only_region_borders": [list(pair) for pair in sorted(canonical - published)],
        "published_only_region_borders": [list(pair) for pair in sorted(published - canonical)],
        "province_borders_identical": provinces == published_provinces,
    }
    result["hex_contacts"] = {
        "sea_regions": hex_source["map"]["sea_regions"],
        **{key: value for key, value in hex_source["contacts"].items() if key != "land"},
        "description": (
            "Geometric hex contacts, not complete travel routes. Passable land means at least "
            "one shared hex edge has two non-impassable endpoints."
        ),
    }
    result["limitations"].extend(
        [
            "Raw hex borders are canonical; published-map differences remain in cross_validation.",
            "Geometric adjacency is not a claim that every game effect uses the same graph.",
        ]
    )
    validate_map(result, "attila", expected)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--refresh", action="store_true", help="Fetch both public sources")
    args = parser.parse_args(argv)
    online_path, hex_path = (
        args.data / "campaign_map_source.json",
        args.data / "campaign_map_hex_source.json",
    )
    if args.refresh:
        online = capture(fetch(PAGE_URL), PAGE_URL)
        hex_source = capture_hex(fetch(HEX_URL))
    else:
        online = json.loads(online_path.read_text())
        hex_source = json.loads(hex_path.read_text())
    result = build_attila_map(online, hex_source, region_provinces("attila"))
    if args.refresh:
        online_path.write_bytes(serialized(online))
        hex_path.write_bytes(serialized(hex_source))
    (args.data / "campaign_map.json").write_bytes(serialized(result))
    return result


if __name__ == "__main__":
    main()
