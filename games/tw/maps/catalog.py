"""Read and validate immutable campaign maps against the bundled game catalogs."""

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

from games.tw.immutable import FrozenMap, read_catalog

ROOT = Path(__file__).parents[1]
GAMES = {"attila", "rome2", "shogun2", "three_kingdoms"}


def region_provinces(game: str) -> dict[str, str]:
    """Canonical ownership of each land region in the supported base campaign."""
    if game == "attila":
        with (ROOT / "attila/data/region_to_provinces_junctions_table.tsv").open() as stream:
            return {
                region: province
                for province, region in csv.reader(stream, delimiter="\t")
                if province.startswith("att_prov_")
            }
    if game == "rome2":
        data = read_catalog(ROOT / "rome2/data/world.json")
        return {key: row["province"] for key, row in data["regions"].items()}
    if game == "shogun2":
        data = read_catalog(ROOT / "shogun2/data/rules.json")
        return {key: key for key in data["provinces"]}
    if game == "three_kingdoms":
        data = read_catalog(ROOT / "three_kingdoms/data/geography.json")
        return {key: row["commandery"] for key, row in data["regions"].items()}
    raise ValueError("No campaign map for this game")


def _pairs(values, known: set[str]) -> tuple[tuple[str, str], ...]:
    result = set()
    if not isinstance(values, (tuple, list)):
        raise ValueError("Map borders must be a list of pairs")
    for pair in values:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("A map border must have two endpoints")
        a, b = pair
        if not isinstance(a, str) or not isinstance(b, str) or a == b:
            raise ValueError("A map border must join distinct named places")
        if a not in known or b not in known:
            raise ValueError("Map border references an unknown place")
        normalized = (a, b) if a < b else (b, a)
        if normalized in result:
            raise ValueError("Map contains a duplicate undirected border")
        result.add(normalized)
    return tuple(sorted(result))


def validate_map(data: Mapping, game: str, expected: Mapping[str, str]) -> None:
    """Reject mismatched maps and coverage claims instead of dropping unknown edges."""
    if data["schema_version"] != 1 or data["game"] != game or not data["sources"]:
        raise ValueError("Invalid campaign map identity or source provenance")
    regions = data["regions"]
    actual = {key: row["province"] for key, row in regions.items()}
    if not actual.keys() <= expected.keys() or any(
        expected[key] != province for key, province in actual.items()
    ):
        raise ValueError("Map regions or provinces do not match the game catalog")
    region_edges = _pairs(data["region_borders"], set(actual))
    province_edges = _pairs(data["province_borders"], set(actual.values()))
    derived = {
        tuple(sorted((actual[a], actual[b]))) for a, b in region_edges if actual[a] != actual[b]
    }
    if set(province_edges) != derived:
        raise ValueError("Province borders do not match the source region borders")
    _validate_coverage(data["coverage"], actual, expected, region_edges, province_edges)


def _validate_coverage(coverage, actual, expected, region_edges, province_edges):
    if not isinstance(coverage["complete"], bool):
        raise ValueError("Map completeness must be explicit")
    if coverage["complete"] and actual != expected:
        raise ValueError("A complete map must cover every campaign region")
    sizes = {
        "region_count": len(actual),
        "province_count": len(set(actual.values())),
        "region_border_count": len(region_edges),
        "province_border_count": len(province_edges),
    }
    if any(coverage[key] != count for key, count in sizes.items()):
        raise ValueError("Map coverage counts do not match the imported graph")


def load_campaign_map(game: str) -> FrozenMap | None:
    if game not in GAMES:
        return None
    path = ROOT / game / "data/campaign_map.json"
    if not path.exists():
        return None
    data = read_catalog(path)
    try:
        validate_map(data, game, region_provinces(game))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid bundled {game} campaign map: {error}") from error
    return data


def province_borders(game: str, selected: Iterable[str]) -> tuple[tuple[str, str], ...] | None:
    """Return the selected map's sourced adjacency graph; None means unavailable."""
    data = load_campaign_map(game)
    if data is None or not data["coverage"]["complete"]:
        return None
    owned = set(selected)
    known = {row["province"] for row in data["regions"].values()}
    if not owned <= known:
        return None
    return tuple(
        sorted(tuple(sorted((a, b))) for a, b in data["province_borders"] if {a, b} <= owned)
    )
