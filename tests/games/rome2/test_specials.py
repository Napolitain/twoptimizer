"""Construction coverage stays explicit when special-building rules are missing."""

import hashlib
import json

import pytest

from games.tw.rome2.catalog import CATALOG, load_data
from games.tw.rome2.model import Economy
from games.tw.rome2.world import province_scenario


def test_special_building_audit_matches_the_source_catalog():
    audit = json.loads((CATALOG.parent / "special_buildings_coverage.json").read_text())
    data = load_data()
    special_ids = {key for key, building in data["buildings"].items() if building["level"] > 4}
    assert audit["catalog_sha256"] == hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    assert audit["level_five_count"] == len(special_ids) == 35
    assert {row["id"] for row in audit["level_five_buildings"]} == special_ids
    assert "rome_city_centre_gladiator_5" in special_ids
    assert all(row["status"] == "excluded_pending_rules" for row in audit["level_five_buildings"])
    assert len(audit["missing_rules"]) > 0
    assert "a certain event has occurred" in audit["sources"][0]["quote"]


def test_marib_audit_retains_location_and_once_per_dam_maintenance():
    audit = json.loads((CATALOG.parent / "special_buildings_coverage.json").read_text())
    data = load_data()
    assert len(audit["explicit_regional_buildings"]) == 3
    for row in audit["explicit_regional_buildings"]:
        assert row["allowed_regions"] == ["rom_arabia_felix_saba"]
        building = data["buildings"][row["id"]]
        stage = building["level"] - 1
        amounts = {effect["id"]: effect["value"] for effect in building["effects"]}
        assert (
            amounts[audit["marib_economics"]["effect_id"]]
            == audit["marib_economics"]["stage_values_percent"][stage]
        )
        assert (
            amounts["dk_building_gdp_maintenance"]
            == -audit["marib_economics"]["maintenance_per_turn"][stage]
        )


@pytest.mark.parametrize(
    ("faction", "province", "legendary"),
    [
        ("rom_rome", "Italia", "rome_city_centre_gladiator_5"),
        ("rom_carthage", "Africa", "greek_religious_punic_5"),
    ],
)
def test_default_candidates_do_not_assume_legendary_unlocks(faction, province, legendary):
    data = load_data()
    assert legendary in data["buildings"]
    economy = Economy(province_scenario(province, faction), data)
    assert not any(legendary in buildings for buildings in economy.candidates.values())
    assert all(
        building["level"] <= 4
        for buildings in economy.candidates.values()
        for building in buildings.values()
    )
