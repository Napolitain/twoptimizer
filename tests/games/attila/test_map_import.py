"""Attila border import keeps independent source disagreements inspectable."""

import json
from copy import deepcopy

import pytest

from games.tw.attila.tools.import_map import build_attila_map, capture_hex, main
from games.tw.maps.catalog import region_provinces
from tests.support.paths import REPO_ROOT

DATA = REPO_ROOT / "games/tw/attila/data"


def sources():
    return tuple(
        json.loads((DATA / name).read_text())
        for name in ("campaign_map_source.json", "campaign_map_hex_source.json")
    )


def test_offline_attilla_rebuild_preserves_canonical_and_crosschecked_borders(tmp_path):
    online, raw = sources()
    for name, source in zip(
        ("campaign_map_source.json", "campaign_map_hex_source.json"), (online, raw), strict=True
    ):
        (tmp_path / name).write_text(json.dumps(source))
    result = main(["--data", str(tmp_path)])
    assert result == json.loads((DATA / "campaign_map.json").read_text())
    assert result["cross_validation"]["province_borders_identical"]
    assert result["cross_validation"]["matching_region_border_count"] == 387
    assert result["cross_validation"]["hex_only_region_borders"] == [
        ["att_reg_raetia_et_noricum_virunum", "att_reg_venetia_verona"]
    ]
    assert result["cross_validation"]["published_only_region_borders"] == [
        ["att_reg_raetia_et_noricum_iuvavum", "att_reg_venetia_aquileia"]
    ]
    assert len(result["hex_contacts"]["passable_land"]) == 355
    assert len(result["hex_contacts"]["sea_regions"]) == 37
    assert len(result["hex_contacts"]["sea"]) == 36
    assert len(result["hex_contacts"]["coastal"]) == 223
    assert all(not a.startswith("att_sea_") for a, _ in result["region_borders"])
    assert len(result["sources"]) == 2


def test_hex_capture_requires_crc_valid_source():
    with pytest.raises(ValueError, match="CRC32"):
        capture_hex(b"not a hex map")


@pytest.mark.parametrize("error", ["campaign", "land", "sea", "duplicate", "crossing"])
def test_hex_source_cannot_claim_wrong_campaign_or_connection_types(error):
    online, raw = sources()
    raw = deepcopy(raw)
    if error == "campaign":
        raw["map"]["campaign"] = "main_rome_map"
    elif error == "land":
        raw["map"]["land_regions"].pop()
    elif error == "sea":
        raw["contacts"]["sea"].append(raw["contacts"]["land"][0])
    elif error == "duplicate":
        raw["contacts"]["land"].append(raw["contacts"]["land"][0])
    else:
        raw["contacts"]["coastal"].append(raw["contacts"]["land"][0])
    with pytest.raises(ValueError):
        build_attila_map(online, raw, region_provinces("attila"))
