"""Rebuild Grand Campaign borders from the pinned public CA map.hex file."""

import argparse
import hashlib
import json
from pathlib import Path

from games.tw.maps.import_hex import extract_contacts, parse_hex, region_centroids

DATA = Path(__file__).parent / "data"
REVISION = "d7e27bacaf9a5b4656b483b47b4e6212ad3a6cb4"
REPOSITORY = "https://github.com/TW-Campaign-Map-Modding-Team/CampaignMapToolkit"
SOURCE_PATH = "Templates/main_rome_map/map.hex"
SOURCE_SHA256 = "b7b753bd00f5e3311f811c3a104712272f4f2397d2c465ad6aa8f2acc844915a"
SOURCE_URL = (
    "https://raw.githubusercontent.com/TW-Campaign-Map-Modding-Team/"
    f"CampaignMapToolkit/{REVISION}/{SOURCE_PATH}"
)


def import_campaign_map(raw: bytes) -> dict:
    """Require the audited source and exact joins to existing campaign identities."""
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Rome II map source differs from the audited revision")
    model = parse_hex(raw)
    if (model.game, model.campaign) != ("rome2", "main_rome_map"):
        raise ValueError("Expected the Rome II Grand Campaign map")
    world = json.loads((DATA / "world.json").read_text())["regions"]
    excluded = ("rom_terra_incognita",)
    if set(model.land_regions) != set(world) | set(excluded):
        raise ValueError("Rome II map regions do not exactly match the world catalog")
    contacts = extract_contacts(model, excluded)
    positions = region_centroids(model)
    if set(positions) != set(model.land_regions) | set(model.sea_regions):
        raise ValueError("A declared map region has no cells")
    regions = {
        key: {
            "name": row["name"],
            "province": row["province"],
            "x": positions[key][0],
            "y": positions[key][1],
        }
        for key, row in sorted(world.items())
    }
    provinces = sorted(
        {
            tuple(sorted((regions[a]["province"], regions[b]["province"])))
            for a, b in contacts["land"]
            if regions[a]["province"] != regions[b]["province"]
        }
    )
    return {
        "schema_version": 1,
        "game": "rome2",
        "campaign": "main_rome",
        "sources": [_source_metadata(raw)],
        "map": {
            "width": model.width,
            "height": model.height,
            "position_kind": "territory_hex_centroid",
            "coordinates": "x=column; y=row+(column%2)/2 in native map.hex coordinates",
        },
        "regions": regions,
        "region_borders": contacts["land"],
        "province_borders": provinces,
        "sea_regions": {
            key: {"x": positions[key][0], "y": positions[key][1]}
            for key in sorted(model.sea_regions)
        },
        "sea_borders": contacts["sea"],
        "coastal_borders": contacts["coastal"],
        "coverage": {
            "complete": True,
            "region_count": len(regions),
            "province_count": len({row["province"] for row in regions.values()}),
            "region_border_count": len(contacts["land"]),
            "province_border_count": len(provinces),
            "sea_region_count": len(model.sea_regions),
            "sea_border_count": len(contacts["sea"]),
            "coastal_border_count": len(contacts["coastal"]),
            "adjacency_kind": "hex_land_borders",
            "identity_validation": "173/173 existing world region IDs match exactly",
            "excluded_regions": list(excluded),
            "method": "Unique region pairs sharing one of six hex edges; no row wrapping",
            "source_crc32_verified": True,
        },
        "limitations": [
            "The public CA map source has no declared game patch and is not verified "
            "against an installed build.",
            "Land borders include impassable terrain contacts. They describe geography; "
            "they do not certify each economic effect's in-game target semantics.",
            "Sea and coastal borders are geometric contacts, including river/lake regions; "
            "they are not movement links, strait crossings, port access or trade routes.",
            "Coordinates are territory centroids, not settlement positions or map polygons.",
            "Only the Grand Campaign is covered; DLC campaign maps are separate sources.",
        ],
    }


def _source_metadata(raw: bytes) -> dict:
    return {
        "url": SOURCE_URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "revision": REVISION,
        "path": SOURCE_PATH,
        "git_blob_sha1": "f5797888441f28452a5711092f40e237d9887abe",
        "patch": None,
        "credit": "Creative Assembly / OtherTomCA; CampaignMapToolkit public map archive",
        "provenance_url": f"{REPOSITORY}/blob/{REVISION}/README.md",
        "format_url": (
            f"{REPOSITORY}/blob/{REVISION}/FileFormatDefinitions/010_hex_editor_map_hex.bt"
        ),
        "redistribution": (
            "Only derived factual identities, centroids and border pairs are included; "
            "the raw map asset and toolkit implementation are not redistributed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hex_file", type=Path)
    parser.add_argument("--output", type=Path, default=DATA / "campaign_map.json")
    args = parser.parse_args()
    catalog = import_campaign_map(args.hex_file.read_bytes())
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")
    print(f"Imported {catalog['coverage']['region_border_count']} Rome II region borders")


if __name__ == "__main__":
    main()
