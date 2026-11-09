"""Check campaign joins and distinguish recorded contacts from complete adjacency."""

import json

import pytest

from games.tw.immutable import thaw
from games.tw.maps.catalog import load_campaign_map, province_borders, region_provinces
from games.tw.three_kingdoms.import_geography import CAMPAIGN, build_geography, build_partial_map
from games.tw.three_kingdoms.source import SourceArchive
from tests.support.paths import REPO_ROOT

DATA = REPO_ROOT / "games/tw/three_kingdoms/data"


@pytest.fixture
def geography_tables():
    regions = ("a_capital", "a_farm", "b_capital")
    return {
        "start_pos_regions": [
            {
                "campaign": CAMPAIGN,
                "region": key,
                "id": key + "_startpos_id",
                "population": "100000",
                "base_max_population": "500000",
                "slot_cap": "7",
                "owning_faction": "42",
            }
            for key in regions
        ],
        "regions": [{"key": key, "onscreen": key, "battle_name": key} for key in regions],
        "provinces": [{"key": key, "onscreen": key.upper()} for key in ("a", "b")],
        "region_to_province_junctions": [
            {
                "region": key,
                "province": key[0],
                "is_capital": "1" if key.endswith("capital") else "0",
            }
            for key in regions
        ],
        "start_pos_region_slot_templates": [
            {
                "campaign": CAMPAIGN,
                "region": key,
                "slot_type": "primary",
                "slot_template": "city" if key.endswith("capital") else "farm",
            }
            for key in regions
        ]
        + [
            {
                "campaign": CAMPAIGN,
                "region": "a_capital",
                "slot_type": "secondary",
                "slot_template": "districts_port",
            }
        ],
        "slot_template_to_building_superchain_junctions": [
            {"slot_template": key, "building_superchain": value}
            for key, value in (("city", "city"), ("farm", "grain"), ("districts_port", "port"))
        ],
        "campaign_region_additional_adjacency_rules": [
            {"first_region": "a_farm", "second_region": "b_capital"}
        ],
        "pooled_resources": [
            {"key": "3k_main_pooled_resource_population", "ui_value_scale_factor": "1000"}
        ],
        "start_pos_region_pooled_resources": [
            {
                "region": "a_capital_startpos_id",
                "pooled_resource": "3k_main_pooled_resource_population",
                "amount": "248",
            }
        ],
    }


def _archive(tmp_path, monkeypatch, tables):
    archive = SourceArchive(tmp_path, offline=True)
    monkeypatch.setattr(archive, "table", lambda name: tables[name])
    archive.records["fixture"] = {"url": "fixture", "sha256": "test", "bytes": 1}
    return archive


def test_geography_resolves_resource_and_capital_placement(tmp_path, monkeypatch, geography_tables):
    data = build_geography(_archive(tmp_path, monkeypatch, geography_tables))
    assert data["regions"]["a_farm"]["resource_superchain"] == "farm"
    assert data["regions"]["a_farm"]["primary_superchains"] == ["grain"]
    assert data["regions"]["a_capital"]["secondary_superchains"] == ["port"]
    assert data["regions"]["a_capital"]["initial_population"] == 248000
    assert data["regions"]["a_capital"]["legacy_population"] == 100000
    assert data["regions"]["a_capital"]["legacy_base_max_population"] == 500000
    assert data["regions"]["a_farm"]["initial_population"] is None
    assert data["population_reference"]["missing_regions"] == ["a_farm", "b_capital"]
    assert data["commanderies"]["a"]["capital"] == "a_capital"
    assert data["coverage"]["geography_complete"] is True
    assert data["coverage"]["adjacency_complete"] is False
    partial = build_partial_map(data)
    assert partial["province_borders"] == [["a", "b"]]
    assert partial["coverage"]["complete"] is False


@pytest.mark.parametrize("failure", ["empty", "duplicate", "slot", "capital", "edge"])
def test_import_rejects_unsafe_geography(tmp_path, monkeypatch, geography_tables, failure):
    tables = geography_tables
    if failure == "empty":
        tables["start_pos_regions"] = []
    elif failure == "duplicate":
        tables["regions"].append(tables["regions"][0])
    elif failure == "slot":
        tables["start_pos_region_slot_templates"][-1]["slot_template"] = "unknown"
    elif failure == "capital":
        tables["region_to_province_junctions"][0]["is_capital"] = "0"
    else:
        tables["campaign_region_additional_adjacency_rules"][0]["second_region"] = "unknown"
    with pytest.raises(ValueError):
        build_geography(_archive(tmp_path, monkeypatch, tables))


def test_bundled_geography_preserves_historical_placement_and_missing_adjacency():
    data = json.loads((DATA / "geography.json").read_text())
    assert len(data["commanderies"]) == 70
    assert len(data["regions"]) == 187
    assert data["coverage"]["resource_count"] == 117
    # The key's spelling must not determine province ownership: this county is Luoyang's.
    lumber = data["regions"]["3k_main_chenjun_resource_3"]
    assert lumber["commandery"] == "3k_main_province_luoyang"
    assert lumber["resource_superchain"] == "3k_resource_wood_lumber_pine"
    assert (
        "3k_district_market_port_city"
        in data["regions"]["3k_main_jincheng_capital"]["secondary_superchains"]
    )
    assert (
        "3k_district_market_land_city"
        not in data["regions"]["3k_main_jincheng_capital"]["secondary_superchains"]
    )
    graph = load_campaign_map("three_kingdoms")
    assert graph is not None
    assert graph["coverage"]["complete"] is False
    assert len(graph["region_borders"]) == 55
    assert province_borders("three_kingdoms", data["commanderies"]) is None
    assert region_provinces("three_kingdoms") == {
        key: row["commandery"] for key, row in data["regions"].items()
    }
    assert thaw(graph) == build_partial_map(data)
    assert data["regions"]["3k_main_anding_capital"]["initial_population"] == 15000
    assert data["regions"]["3k_main_chenjun_capital"]["initial_population"] == 248000
    assert data["population_reference"]["missing_regions"] == [
        "3k_main_hepu_resource_2",
        "3k_main_yizhou_island_capital",
        "3k_main_yizhou_island_resource_1",
    ]


@pytest.mark.parametrize("failure", ["duplicate", "unknown", "negative", "scale"])
def test_population_join_rejects_bad_source_ids_and_units(
    tmp_path, monkeypatch, geography_tables, failure
):
    rows = geography_tables["start_pos_region_pooled_resources"]
    if failure == "duplicate":
        rows.append(rows[0])
    elif failure == "unknown":
        rows[0]["region"] = "not_a_startpos_id"
    elif failure == "negative":
        rows[0]["amount"] = "-1"
    else:
        geography_tables["pooled_resources"][0]["ui_value_scale_factor"] = "0"
    with pytest.raises(ValueError):
        build_geography(_archive(tmp_path, monkeypatch, geography_tables))
