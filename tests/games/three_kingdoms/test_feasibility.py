"""Concrete sustainable holdings for every historical faction, without native solves."""

import pytest

from games.tw.three_kingdoms.catalog import load_data
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.scenario import Commandery, Scenario

# A level-four town and the initial resource settlements form an explicit witness.
# Temples and specialist craftsmen begin at level zero in the historical database.
PRIMARY_BUILDINGS = frozenset(
    {
        "3k_city_4",
        "3k_resource_earth_temple_0",
        "3k_resource_fire_iron_1",
        "3k_resource_fire_northern_horses_1",
        "3k_resource_metal_copper_1",
        "3k_resource_metal_craftsmen_animal_0",
        "3k_resource_metal_craftsmen_armour_0",
        "3k_resource_metal_craftsmen_weapon_0",
        "3k_resource_metal_jade_1",
        "3k_resource_metal_tools_1",
        "3k_resource_water_salt_1",
        "3k_resource_water_silk_1",
        "3k_resource_water_spice_1",
        "3k_resource_water_trading_port_1",
        "3k_resource_wood_farms_grain_1",
        "3k_resource_wood_farms_rice_1",
        "3k_resource_wood_fish_1",
        "3k_resource_wood_livestock_1",
        "3k_resource_wood_lumber_bamboo_1",
        "3k_resource_wood_lumber_pine_1",
        "3k_resource_wood_tea_1",
        "3k_ytr_resource_earth_temple_yellow_turban_0",
    }
)


def self_sufficient_layout(model, yellow_turban):
    districts = (
        [
            "3k_ytr_district_residential_farming_yellow_turban_3",
            "3k_ytr_district_government_religion_yellow_turban_1",
        ]
        if yellow_turban
        else ["3k_district_residential_landlords_3", "3k_district_government_religion_1"]
    )
    layout = {}
    for county, buildings in model.candidates.items():
        primary = PRIMARY_BUILDINGS.intersection(buildings)
        assert len(primary) == 1, county
        selected = list(primary)
        if "3k_city_4" in primary:
            selected.extend(districts)
        if "3k_district_market_harbour_fish_3" in buildings:
            selected.append("3k_district_market_harbour_fish_3")
        layout[county] = selected
    return layout


@pytest.mark.parametrize("faction", tuple(load_data()["factions"]))
def test_every_faction_can_sustain_all_commanderies_without_forced_city_upgrades(faction):
    data = load_data()
    scenario = Scenario(
        faction,
        tuple(Commandery(key, city_level=None) for key in data["commanderies"]),
    )
    model = Economy(scenario)
    layout = self_sufficient_layout(model, faction.startswith("3k_main_faction_yellow_turban_"))

    # Evaluating a concrete layout proves feasibility; it makes no optimality claim.
    result = model.evaluate(layout)

    assert len(layout) == 187
    assert len(result["commanderies"]) == 70
    assert not scenario.all_reforms
    assert scenario.external_food == 0
    assert scenario.external_resources == ()
    assert result["food_surplus"] == pytest.approx(213)
    assert result["domestic_income"] > 0
    for commandery in result["commanderies"].values():
        assert commandery["city_level"] == 4
        assert commandery["population"] == 1_000_000
        assert commandery["population_capacity"] >= 1_300_000
        assert commandery["public_order"] >= 1
        # Each commandery also supports itself if run independently.
        assert commandery["food_surplus"] >= 1
