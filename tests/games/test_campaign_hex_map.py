"""Check binary decoding and hex topology without depending on online assets."""

import json
from struct import pack
from zlib import crc32

import pytest

from games.tw.maps.import_hex import extract_contacts, parse_hex, region_centroids
from games.tw.rome2.import_map import import_campaign_map
from tests.support.paths import REPO_ROOT


def _string(value):
    raw = value.encode("ascii")
    return pack("<I", len(raw)) + raw


def _strings(values):
    return pack("<I", len(values)) + b"".join(_string(value) for value in values)


def _checksum(data):
    return data + pack("<I", crc32(data))


def _map(rows, *, land=("a", "b"), sea=(), version=13, tail=b""):
    header = pack("<II", 0, version) + _string("rome2") + _string("main_rome_map")
    header += _strings(land) + _strings(sea) + _strings(()) * 4
    header += pack("<IIII", 0, 0, len(rows[0]), len(rows))
    cells = bytearray()
    for row in rows:
        for index, terrain, impassable in row:
            region = index + 1
            cells.extend(((region << 3 & 255) | terrain, region >> 5, impassable << 3))
            cells.extend(b"\0" * (5 if version == 13 else 13))
    return _checksum(header + cells + tail)


@pytest.mark.parametrize("version", [13, 15])
def test_land_sea_indices_and_contacts_are_separate(version):
    model = parse_hex(
        _map(
            [[(0, 0, 0), (1, 0, 1), (2, 1, 0), (3, 1, 0)]],
            sea=("ocean", "river"),
            version=version,
        )
    )
    assert (model.width, model.height, model.version) == (4, 1, version)
    assert extract_contacts(model) == {
        "land": [["a", "b"]],
        "passable_land": [],
        "sea": [["ocean", "river"]],
        "coastal": [["b", "ocean"]],
    }
    assert extract_contacts(model, ("b",))["coastal"] == []


def test_hex_contacts_use_correct_column_parity_without_row_wrapping():
    names = tuple("abcdefghi")
    model = parse_hex(
        _map(
            [[(row * 3 + column, 0, 0) for column in range(3)] for row in range(3)],
            land=names,
        )
    )
    pairs = {"".join(pair) for pair in extract_contacts(model)["land"]}
    assert pairs == {
        "ad",
        "dg",
        "be",
        "eh",
        "cf",
        "fi",  # Vertical edges.
        "ab",
        "bc",
        "de",
        "ef",
        "gh",
        "hi",  # Same-row edges.
        "bd",
        "eg",
        "bf",
        "ei",  # Offset-column diagonal edges.
    }


def test_invalid_cells_and_single_column_boundaries():
    model = parse_hex(_map([[(0, 0, 0)], [(-1, 0, 0)], [(1, 0, 0)]]))
    assert all(not pairs for pairs in extract_contacts(model).values())
    assert region_centroids(model) == {"a": (0, 0), "b": (0, 2)}


def test_centroids_use_all_region_cells_and_native_hex_offset():
    model = parse_hex(_map([[(0, 0, 0), (0, 0, 0)], [(0, 0, 0), (1, 0, 0)]]))
    assert region_centroids(model) == {"a": (0.3333, 0.5), "b": (1, 1.5)}


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"short", "CRC32"),
        (_map([[(0, 0, 0)]])[:-1] + b"!", "CRC32"),
        (_checksum(pack("<II", 0, 999)), "Unsupported"),
        (_checksum(pack("<II", 0, 13)), "Truncated"),
        (_map([[(2, 0, 0)]]), "unknown region"),
        (_map([[(0, 1, 0)]]), "terrain disagrees"),
        (_map([[(0, 0, 0)]], land=("a", "a")), "Duplicate"),
        (_map([[(0, 0, 0)]], tail=b"unexpected"), "trailing"),
    ],
)
def test_bad_binary_sources_fail_before_export(raw, message):
    with pytest.raises(ValueError, match=message):
        parse_hex(raw)


def test_rome_import_requires_the_pinned_source():
    with pytest.raises(ValueError, match="audited revision"):
        import_campaign_map(_map([[(0, 0, 0)]]))


def test_rome_map_covers_world_and_separates_seas():
    data = REPO_ROOT / "games" / "tw" / "rome2" / "data"
    catalog = json.loads((data / "campaign_map.json").read_text())
    world = json.loads((data / "world.json").read_text())["regions"]
    assert set(catalog["regions"]) == set(world)
    assert len(catalog["region_borders"]) == 353
    assert len(catalog["province_borders"]) == 100
    assert len(catalog["sea_regions"]) == 31
    assert len(catalog["sea_borders"]) == 42
    assert len(catalog["coastal_borders"]) == 208
    land, sea = set(world), set(catalog["sea_regions"])
    assert all(a in land and b in land for a, b in catalog["region_borders"])
    assert all(a in sea and b in sea for a, b in catalog["sea_borders"])
    assert all(
        (a in land and b in sea) or (b in land and a in sea) for a, b in catalog["coastal_borders"]
    )
