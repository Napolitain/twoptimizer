"""Import published campaign border facts from a Next.js map page.

The extractor only decodes JSON; it never evaluates source JavaScript. A factual
snapshot keeps offline rebuilds reproducible without bundling page artwork.
"""

import argparse
import json
import re
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite
from pathlib import Path


def _payloads(value):
    if isinstance(value, dict):
        if "regions" in value and "provinces" in value:
            yield value
        else:
            for child in value.values():
                yield from _payloads(child)
    elif isinstance(value, list):
        for child in value:
            yield from _payloads(child)


def _flight_text(html):
    chunks = []
    prefix = "self.__next_f.push("
    for script in re.findall(r"<script\b[^>]*>(.*?)</script>", html, re.DOTALL):
        script = script.strip()
        if not script.startswith(prefix):
            continue
        try:
            push = json.loads(script[len(prefix) :].removesuffix(";").removesuffix(")"))
        except ValueError:
            continue
        if isinstance(push, list) and len(push) == 2 and push[0] == 1 and isinstance(push[1], str):
            chunks.append(push[1])
    return "".join(chunks)


def extract_map_payload(html: str) -> dict:
    matches = []
    # Flight records may be split across script elements: concatenate first.
    for line in _flight_text(html).splitlines():
        _, separator, body = line.partition(":")
        if separator:
            try:
                matches.extend(_payloads(json.loads(body)))
            except ValueError:
                continue
    if len(matches) != 1:
        raise ValueError(f"Expected one published map payload, found {len(matches)}")
    return matches[0]


def capture(html: bytes, url: str, retrieved_at: str | None = None) -> dict:
    payload = extract_map_payload(html.decode("utf-8"))
    return {
        "schema_version": 1,
        "source": {
            "url": url,
            "sha256": sha256(html).hexdigest(),
            "bytes": len(html),
            "retrieved_at": retrieved_at or datetime.now(UTC).date().isoformat(),
            "patch": payload["patch"],
            "description": "Factual region/province and published Borders (nb) map fields",
        },
        "map": {
            "patch": payload["patch"],
            "width": payload["width"],
            "height": payload["height"],
            "regions": [
                {key: row[key] for key in ("k", "n", "p", "x", "y", "nb")}
                for row in payload["regions"]
            ],
            "provinces": [{key: row[key] for key in ("k", "n")} for row in payload["provinces"]],
        },
    }


def serialized(record: dict) -> bytes:
    return (json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def fetch(url: str) -> bytes:
    """Explicit refresh helper; curl supports the source site's HTTP transport."""
    return subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "60", "--", url],
        capture_output=True,
        check=True,
    ).stdout


def _unique_keys(rows, label):
    keys = [row["k"] for row in rows]
    if not keys or any(not isinstance(key, str) or not key for key in keys):
        raise ValueError(f"Invalid {label} identities")
    if len(set(keys)) != len(keys):
        raise ValueError(f"Duplicate {label} identities")
    return keys


def _index(value, count):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < count:
        raise ValueError("Invalid published map index")
    return value


def _regions(payload):
    _unique_keys(payload["regions"], "region")
    province_keys = _unique_keys(payload["provinces"], "province")
    regions = {}
    for row in payload["regions"]:
        province = province_keys[_index(row["p"], len(province_keys))]
        if not all(isinstance(row[key], (int, float)) and isfinite(row[key]) for key in ("x", "y")):
            raise ValueError("Invalid settlement coordinates")
        regions[row["k"]] = {"name": row["n"], "province": province, "x": row["x"], "y": row["y"]}
    if set(province_keys) != {row["province"] for row in regions.values()}:
        raise ValueError("Published provinces lack region coverage")
    return dict(sorted(regions.items()))


def _borders(rows):
    neighbors = []
    for i, row in enumerate(rows):
        if not isinstance(row["nb"], list):
            raise ValueError("Neighbor indices must be a list")
        indices = {_index(j, len(rows)) for j in row["nb"]}
        if i in indices or len(indices) != len(row["nb"]):
            raise ValueError("Self border or duplicate neighbor in published map")
        neighbors.append(indices)
    borders = set()
    for i, indices in enumerate(neighbors):
        for j in indices:
            if i not in neighbors[j]:
                raise ValueError("Asymmetric published border")
            borders.add(tuple(sorted((rows[i]["k"], rows[j]["k"]))))
    return sorted(borders)


def build_catalog(
    extract: dict, game: str, campaign: str, expected_regions: Mapping[str, str]
) -> dict:
    payload = extract["map"]
    regions = _regions(payload)
    if {key: row["province"] for key, row in regions.items()} != dict(expected_regions):
        raise ValueError("Published map region/province identities do not match the campaign")
    borders = _borders(payload["regions"])
    province_borders = sorted(
        {
            tuple(sorted((regions[a]["province"], regions[b]["province"])))
            for a, b in borders
            if regions[a]["province"] != regions[b]["province"]
        }
    )
    return {
        "schema_version": 1,
        "game": game,
        "campaign": campaign,
        "sources": [
            {**extract["source"], "extract_sha256": sha256(serialized(extract)).hexdigest()}
        ],
        "map": {
            "width": payload["width"],
            "height": payload["height"],
            "coordinate_system": "Source map pixels; settlement points are not border geometry",
        },
        "regions": regions,
        "region_borders": [list(pair) for pair in borders],
        "province_borders": [list(pair) for pair in province_borders],
        "coverage": {
            "complete": True,
            "region_count": len(regions),
            "province_count": len(set(expected_regions.values())),
            "region_border_count": len(borders),
            "province_border_count": len(province_borders),
            "adjacency_kind": "published_land_borders",
            "identity_validation": (
                "Exact region-to-province match against bundled campaign inventory"
            ),
            "symmetry_validated": True,
        },
        "limitations": [
            "Land borders only: sea travel, strait crossings and army movement connections "
            "are not inferred.",
            "The published map has not been validated against a local installed game build.",
        ],
    }


def main(argv=None):
    from games.tw.maps.catalog import region_provinces

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, choices=("attila", "rome2", "shogun2"))
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--source", type=Path, required=True, help="Factual capture JSON")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", help="Explicitly refresh the capture from this published map URL")
    args = parser.parse_args(argv)
    if args.url:
        html = fetch(args.url)
        extract = capture(html, args.url)
    else:
        extract = json.loads(args.source.read_text())
    catalog = build_catalog(extract, args.game, args.campaign, region_provinces(args.game))
    # Validate before replacing either artifact; failed captures preserve existing data.
    if args.url:
        args.source.write_bytes(serialized(extract))
    args.output.write_bytes(serialized(catalog))
    return catalog


if __name__ == "__main__":
    main()
