"""Published map captures must join exact IDs and retain a symmetric border graph."""

import json
from copy import deepcopy

import pytest

from games.tw.maps.import_online import build_catalog, capture, extract_map_payload, serialized
from tests.support.paths import REPO_ROOT


def payload():
    return {
        "patch": "test build",
        "width": 100,
        "height": 50,
        "regions": [
            {"k": "a", "n": "A", "p": 0, "x": 10, "y": 20, "nb": [1]},
            {"k": "b", "n": "B", "p": 1, "x": 20, "y": 20, "nb": [0]},
            {"k": "island", "n": "Island", "p": 1, "x": 40, "y": 20, "nb": []},
        ],
        "provinces": [{"k": "west", "n": "West"}, {"k": "east", "n": "East"}],
    }


def page(data):
    flight = "23:" + json.dumps({"children": ["map", {"data": data}]}) + "\n"
    half = len(flight) // 2
    return "".join(
        "<script>self.__next_f.push(" + json.dumps([1, part]) + ")</script>"
        for part in (flight[:half], flight[half:])
    )


def expected():
    return {"a": "west", "b": "east", "island": "east"}


def test_split_flight_records_import_exact_borders_without_guessing_island_links():
    source = capture(page(payload()).encode(), "https://example.test/map", "2026-11-08")
    rebuilt = build_catalog(source, "attila", "main_attila", expected())
    assert rebuilt["region_borders"] == [["a", "b"]]
    assert rebuilt["province_borders"] == [["east", "west"]]
    assert rebuilt["regions"]["island"] == {"name": "Island", "province": "east", "x": 40, "y": 20}
    assert rebuilt["coverage"]["complete"]
    assert rebuilt["coverage"]["region_count"] == 3
    assert len(rebuilt["sources"][0]["sha256"]) == 64
    assert source["source"]["bytes"] == len(page(payload()).encode())
    assert json.loads(serialized(source)) == source


def test_missing_and_ambiguous_map_payloads_are_rejected():
    with pytest.raises(ValueError, match="found 0"):
        extract_map_payload("<script>self.__next_f.push([1,window.execute()])</script>")
    with pytest.raises(ValueError, match="found 2"):
        extract_map_payload(page(payload()) + page(payload()))


@pytest.mark.parametrize("neighbors", [[3], [-1], [True], [0], [1, 1], "1", []])
def test_invalid_neighbors_cannot_be_mistaken_for_a_complete_map(neighbors):
    data = payload()
    data["regions"][0]["nb"] = neighbors
    source = capture(page(data).encode(), "https://example.test/map")
    with pytest.raises(ValueError):
        build_catalog(source, "attila", "main_attila", expected())


def test_exact_campaign_inventory_and_province_membership_are_required():
    source = capture(page(payload()).encode(), "https://example.test/map")
    with pytest.raises(ValueError, match="campaign"):
        build_catalog(source, "attila", "main_attila", {**expected(), "missing": "west"})
    changed = deepcopy(source)
    changed["map"]["regions"][0]["p"] = 1
    with pytest.raises(ValueError, match=r"coverage|campaign"):
        build_catalog(changed, "attila", "main_attila", expected())
    changed = deepcopy(source)
    changed["map"]["regions"][1]["k"] = "a"
    with pytest.raises(ValueError, match="Duplicate region"):
        build_catalog(changed, "attila", "main_attila", expected())


def test_attila_factual_capture_has_complete_ids_and_known_neighbors():
    from games.tw.maps.catalog import region_provinces

    root = REPO_ROOT / "games/tw/attila/data"
    source = json.loads((root / "campaign_map_source.json").read_text())
    result = build_catalog(source, "attila", "main_attila", region_provinces("attila"))
    assert result["coverage"]["region_count"] == 186
    assert result["coverage"]["province_count"] == 62
    assert result["coverage"]["region_border_count"] == 388
    assert result["coverage"]["province_border_count"] == 108
    borders = {tuple(pair) for pair in result["province_borders"]}
    assert ("att_prov_macedonia", "att_prov_thracia") in borders
    assert ("att_prov_britannia_superior", "att_prov_belgica") not in borders
