"""Historical population and city rules retain source scopes and boundaries."""

import json
from pathlib import Path

import pytest

from games.tw.three_kingdoms.import_rules import DATA, _population_band, _validate_bands


@pytest.fixture
def rules():
    return json.loads((DATA / "rules.json").read_text())


def test_population_intervals_cover_thousand_person_domain(rules):
    assert rules["population_unit"] == 1000
    assert rules["population_scope"] == "FACTION_PROVINCE"
    _validate_bands(rules["population_bands"])
    assert len(rules["population_bands"]) == 21
    bands = {band["minimum"]: band for band in rules["population_bands"]}
    assert (bands[0]["maximum"], bands[0]["peasantry_percent"]) == (50, 0)
    assert (bands[51]["maximum"], bands[51]["peasantry_percent"]) == (100, 25)
    assert (bands[801]["maximum"], bands[801]["peasantry_percent"]) == (1000, 65)
    assert (bands[801]["public_order"], bands[1001]["public_order"]) == (-2, -4)
    assert (bands[5501]["peasantry_percent"], bands[5501]["public_order"]) == (350, -30)


@pytest.mark.parametrize(
    "bands",
    [
        [],
        [{"minimum": 1, "maximum": 2147483647}],
        [{"minimum": 0, "maximum": 10}, {"minimum": 10, "maximum": 2147483647}],
        [{"minimum": 0, "maximum": 10}, {"minimum": 12, "maximum": 2147483647}],
        [{"minimum": 0, "maximum": -1}],
    ],
)
def test_population_import_rejects_missing_overlapping_or_incomplete_bands(bands):
    with pytest.raises(ValueError, match="Population source intervals"):
        _validate_bands(bands)


def test_no_public_order_effect_requires_explicit_source_marker():
    row = {"campaign_group": "population_group", "effect_bundle": "population_bundle"}
    bounds = {"min_range": "0", "max_range": "50"}
    effects = [
        {"effect_key": "3k_main_effect_economy_gdp_mod_peasantry_from_population", "value": "0"}
    ]
    with pytest.raises(ValueError, match="explicit value"):
        _population_band(row, bounds, effects)
    effects.append({"effect_key": "3k_main_effect_population_effects_public_order", "value": "1"})
    assert _population_band(row, bounds, effects)["public_order"] == 0


def test_city_capacity_and_slots_use_pinned_database(rules):
    cities = rules["city_levels"]
    assert [cities[str(level)]["slots"] for level in range(11)] == [0, 1, 2, 2, 3, 4, 4, 5, 6, 6, 6]
    assert cities["5"]["population_capacity"] == 1_000_000
    assert cities["7"]["population_capacity"] == 2_000_000
    assert cities["10"]["population_capacity"] == 7_500_000
    assert cities["10"]["building"] == "3k_city_10"
    assert all(city["slot_point_cost"] == 2 for city in cities.values())


def test_tax_rules_and_raw_corruption_curve_remain_auditable(rules):
    assert {key: row["income_percent"] for key, row in rules["tax_levels"].items()} == {
        "exempt": 0,
        "minimal": 80,
        "low": 90,
        "normal": 100,
        "high": 110,
        "extortionate": 120,
    }
    points = [
        row
        for row in rules["corruption_reference_points"]
        if row["difficulty"] == "HUMAN_IN_NORMAL_GAME" and row["region_count"] == "35"
    ]
    assert points[0]["administration_cost"] == "-50"


def test_rules_record_pinned_raw_source_hashes(rules):
    sources = {Path(row["url"]).name: row for row in rules["sources"]}
    assert "campaign_variables.xml" in sources
    assert "campaign_group_member_criteria_pooled_resource_scopes.xml" in sources
    assert all(rules["source_commit"] in row["url"] for row in sources.values())
    assert all(len(row["sha256"]) == 64 and row["bytes"] > 0 for row in sources.values())


def test_fertility_season_bundles_keep_distinct_income_and_food_effects(rules):
    bundles = rules["fertility_bundles"]
    assert set(bundles) == {
        "low",
        "normal",
        "high",
        "harvest_low",
        "harvest_normal",
        "harvest_high",
    }
    assert bundles["low"]["peasantry_percent"] == -25
    assert bundles["harvest_low"]["peasantry_percent"] == -10
    assert bundles["harvest_high"]["farming_fishing_percent"] == 25
    assert (
        bundles["normal"]["peasantry_percent"] == bundles["normal"]["farming_fishing_percent"] == 0
    )
