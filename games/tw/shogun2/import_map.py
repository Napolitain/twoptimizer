"""Combine source-exact display polygons with extracted Sengoku AI boundaries."""

import argparse
import json
import math
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import urljoin

from games.tw.multigame.html import Document
from games.tw.multigame.sources import Sources
from games.tw.shogun2.import_rules import DATA, PROVINCES, ROOT

SNAPSHOT = DATA / "campaign_map_source.json"
ADJACENCY = DATA / "campaign_adjacency_source.json"
OUTPUT = DATA / "campaign_map.json"
UNAVAILABLE_TOPOLOGY = (
    "Empty border, movement and sea-route lists mean unavailable data, "
    "not that the provinces have no neighbors or crossings."
)


def snapshot_text(snapshot):
    """Use a stable source-extract encoding for offline replay and hashing."""
    return json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def extract_snapshot(html, source):
    document = Document(html)
    maps = list(document.root.nodes("map", id="m_outline"))
    images = list(document.root.nodes("img", usemap="#m_outline"))
    if len(maps) != 1 or len(images) != 1:
        raise ValueError("Expected one province image map and its image dimensions")
    return {
        "schema_version": 1,
        "source": source,
        "image": {key: images[0].attrs[key] for key in ("src", "width", "height")},
        "areas": [
            {key: area.attrs.get(key, "") for key in ("href", "shape", "coords")}
            for area in maps[0].nodes("area")
            if area.attrs.get("href", "").startswith("regions/")
        ],
    }


def _polygon(area, width, height):
    if area["shape"] != "poly":
        raise ValueError("Expected polygon province geometry")
    coordinates = [int(value) for value in area["coords"].split(",")]
    if len(coordinates) < 6 or len(coordinates) % 2:
        raise ValueError("Province polygon needs at least three coordinate pairs")
    points = list(zip(coordinates[::2], coordinates[1::2], strict=True))
    if any(not (0 <= x <= width and 0 <= y <= height) for x, y in points):
        raise ValueError("Province polygon lies outside the source image")
    return points


def _centroid(points):
    area = x_total = y_total = 0
    for (x, y), (next_x, next_y) in zip(points, points[1:] + points[:1], strict=True):
        cross = x * next_y - next_x * y
        area += cross
        x_total += (x + next_x) * cross
        y_total += (y + next_y) * cross
    if not area:
        raise ValueError("Province polygon has zero area")
    return round(x_total / (3 * area), 3), round(y_total / (3 * area), 3)


def _region(area, names, width, height):
    match = re.fullmatch(r"regions/(jap_[a-z_]+)\.html", area["href"])
    if match is None:
        raise ValueError(f"Unrecognized province link: {area['href']}")
    source_id = match[1]
    key = {"jap_kozuka": "jap_kozuke"}.get(source_id, source_id)
    if key not in names:
        raise ValueError(f"Unmatched province identity: {key}")
    points = _polygon(area, width, height)
    x, y = _centroid(points)
    return key, {
        "name": names[key]["name"],
        "province": key,
        "x": x,
        "y": y,
        "polygon": [list(point) for point in points],
        "source_region_id": source_id,
    }


def map_catalog(snapshot, names, source_filename=SNAPSHOT.name):
    if snapshot["schema_version"] != 1 or snapshot["source"]["url"] != PROVINCES:
        raise ValueError("Unrecognized province map source snapshot")
    width, height = (int(snapshot["image"][key]) for key in ("width", "height"))
    if width <= 0 or height <= 0:
        raise ValueError("Source image dimensions must be positive")
    regions = {}
    for area in snapshot["areas"]:
        key, record = _region(area, names, width, height)
        if key in regions:
            raise ValueError(f"Duplicate province identity: {key}")
        regions[key] = record
    if set(regions) != set(names) or not regions:
        raise ValueError(f"Province coverage differs: {sorted(set(names) - regions.keys())}")
    return {
        "schema_version": 1,
        "game": "shogun2",
        "campaign": "jap_shogun",
        "sources": [snapshot["source"]],
        "source_snapshot": {
            "file": source_filename,
            "sha256": sha256(snapshot_text(snapshot).encode()).hexdigest(),
        },
        "regions": dict(sorted(regions.items())),
        "region_borders": [],
        "province_borders": [],
        "movement_edges": [],
        "sea_routes": [],
        "geometry": {
            "coordinate_system": "image_pixels",
            "width": width,
            "height": height,
            "source_image_url": urljoin(PROVINCES, snapshot["image"]["src"]),
            "position_method": "polygon_centroid_for_display_only",
        },
        "coverage": {
            "complete": False,
            "regions_complete": True,
            "geometry_complete": True,
            "region_count": len(regions),
            "province_count": len(regions),
            "region_border_count": 0,
            "province_border_count": 0,
            "adjacency_kind": "unavailable",
            "method": "Source-exact HTML image-map polygons; no inferred borders",
            "validation": "Every canonical Sengoku province matched exactly once",
        },
        "limitations": [
            "The public map supplies display hit-area outlines, not game-engine topology. "
            "Gaps between neighboring polygons prevent exact shared-border extraction.",
            UNAVAILABLE_TOPOLOGY,
            "Coordinates are display polygon centroids, not settlement positions.",
            "Classic 65-province Sengoku campaign; installed build and other campaigns "
            "remain unverified.",
            "Neighboring religious conversion is outside the static income model; "
            "this map adds no adjacency income modifiers.",
        ],
    }


def _boundary_groups(boundaries, names):
    groups: dict[str, list[list[str]]] = {"0": [], "1": []}
    seen = set()
    for boundary in boundaries:
        if set(boundary) != {"a", "b", "kind", "distance"}:
            raise ValueError("Unrecognized engine boundary fields")
        a, b = boundary["a"], boundary["b"]
        pair = tuple(sorted((a, b)))
        if a == b or a not in names or b not in names or pair in seen:
            raise ValueError("Invalid or duplicate engine region boundary")
        kind, distance = boundary["kind"], boundary["distance"]
        if type(kind) is not int or str(kind) not in groups:
            raise ValueError("Unrecognized engine boundary kind")
        if not isinstance(distance, (float, int)) or not math.isfinite(distance) or distance <= 0:
            raise ValueError("Invalid engine boundary distance")
        groups[str(kind)].append(list(pair))
        seen.add(pair)
    return {kind: sorted(pairs) for kind, pairs in groups.items()}


def _validate_adjacency(snapshot, names):
    if (
        snapshot["schema_version"] != 1
        or snapshot["campaign"] != "jap_shogun"
        or snapshot["game"] != "shogun2"
    ):
        raise ValueError("Unrecognized engine adjacency source")
    if set(snapshot["regions"]) != set(names):
        raise ValueError("Engine adjacency region coverage differs")
    ids = [region["ai_id"] for region in snapshot["regions"].values()]
    if len(set(ids)) != len(ids) or any(type(key) is not int or key <= 0 for key in ids):
        raise ValueError("Invalid or duplicate engine region AI identity")
    if any(
        not math.isfinite(region[axis])
        for region in snapshot["regions"].values()
        for axis in ("x", "y")
    ):
        raise ValueError("Invalid engine region position")
    if not snapshot["sources"]:
        raise ValueError("Engine adjacency source provenance is missing")


def _validate_comparison(snapshot, groups):
    verification = snapshot["verification"]
    checks = (
        "canonical_region_coverage_complete",
        "source_ai_ids_equal",
        "source_boundary_distances_equal",
        "source_coordinates_equal",
        "source_graphs_equal",
    )
    if len(snapshot["sources"]) < 2 or any(verification.get(key) is not True for key in checks):
        raise ValueError("Engine adjacency requires agreeing independent source extracts")
    counts = {kind: len(pairs) for kind, pairs in groups.items()}
    if (
        verification["region_count"] != len(snapshot["regions"])
        or verification["boundary_count"] != sum(counts.values())
        or verification["boundary_kind_counts"] != counts
    ):
        raise ValueError("Engine adjacency verification counts differ")
    _validate_boundary_digest(snapshot)


def _validate_boundary_digest(snapshot):
    normalized = [
        {
            "a": min(row["a"], row["b"]),
            "b": max(row["a"], row["b"]),
            "kind": row["kind"],
            "distance": row["distance"],
        }
        for row in snapshot["boundaries"]
    ]
    normalized.sort(key=lambda row: (row["a"], row["b"]))
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    digest = sha256(encoded).hexdigest()
    recorded = [
        snapshot["verification"].get("normalized_boundaries_sha256"),
        *(source.get("extracted_boundaries_sha256") for source in snapshot["sources"]),
    ]
    if any(value != digest for value in recorded):
        raise ValueError("Engine boundary digest differs from audited source extracts")


def add_adjacency(report, snapshot, source_filename=ADJACENCY.name):
    """Preserve every sourced boundary and its code without interpreting the enum."""
    _validate_adjacency(snapshot, report["regions"])
    groups = _boundary_groups(snapshot["boundaries"], report["regions"])
    _validate_comparison(snapshot, groups)
    borders = sorted(pair for pairs in groups.values() for pair in pairs)
    report["region_borders"] = borders
    report["province_borders"] = borders
    report["source_boundary_types"] = groups
    report["sources"].extend(
        {**source, "sha256": source["pack_sha256"], "bytes": source["pack_bytes"]}
        for source in snapshot["sources"]
    )
    report["adjacency_source_snapshot"] = {
        "file": source_filename,
        "sha256": sha256(snapshot_text(snapshot).encode()).hexdigest(),
    }
    report["adjacency_verification"] = snapshot["verification"]
    for key, region in report["regions"].items():
        region["engine_ai_position"] = dict(snapshot["regions"][key])
    report["coverage"].update(
        complete=True,
        region_border_count=len(borders),
        province_border_count=len(borders),
        adjacency_kind="engine_region_boundaries",
        boundary_kind_counts={kind: len(pairs) for kind, pairs in groups.items()},
        method="CAI_WORLD_REGIONS and CAI_REGION_BOUNDARY extracted from campaign startpos",
        validation="All canonical provinces matched; two public campaign extracts agree",
    )
    report["limitations"] = [
        limit for limit in report["limitations"] if limit != UNAVAILABLE_TOPOLOGY
    ] + snapshot["limitations"]
    return report


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cache", type=Path, default=Path(".cache/shogun2-map"))
    cli.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    cli.add_argument("--adjacency-source", type=Path, default=ADJACENCY)
    cli.add_argument("--output", type=Path, default=OUTPUT)
    cli.add_argument("--offline", action="store_true", help="Replay the bundled source extract")
    args = cli.parse_args(argv)
    if args.offline:
        snapshot = json.loads(args.snapshot.read_text())
    else:
        sources = Sources(args.cache)
        html = sources.get(PROVINCES)
        snapshot = extract_snapshot(html, sources.records[PROVINCES])
    names = json.loads((ROOT / "multigame/data/shogun2.json").read_text())["regions"]
    report = map_catalog(snapshot, names, args.snapshot.name)
    adjacency = json.loads(args.adjacency_source.read_text())
    add_adjacency(report, adjacency, args.adjacency_source.name)
    if not args.offline:
        args.snapshot.write_text(snapshot_text(snapshot))
    args.output.write_text(snapshot_text(report))
    return report


if __name__ == "__main__":
    main()
