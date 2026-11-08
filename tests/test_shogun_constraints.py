"""Optional building choices remain subject to Shogun's ordinary legality rules."""

from dataclasses import replace

import pytest

from games.tw.immutable import thaw
from games.tw.shogun2.catalog import load_data
from games.tw.shogun2.model import Economy
from games.tw.shogun2.scenario import Province, Scenario

TEMPLE = "sho_buddhist_4_legendary_temple"
STEALTH = "sho_stealth_4_mizu_shobai"
CASTLE = "sho_castle_2_stronghold"
FARM = "sho_farming_4_consolidation"


@pytest.fixture
def small_holding():
    catalog, rules = thaw(load_data())
    ids = (
        "sho_castle_1_fort",
        CASTLE,
        FARM,
        "sho_crafts_1_market",
        "sho_crafts_4_kanabukama",
        "sho_stealth_3_criminal_syndicate",
        STEALTH,
        TEMPLE,
    )
    catalog["buildings"] = {key: catalog["buildings"][key] for key in ids}
    provinces = (Province("jap_owari"), Province("jap_settsu"))
    for province in provinces:
        rules["provinces"][province.id].update(has_port=False, specialty=None)
    return Scenario("oda", provinces), catalog, rules


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip"])
def test_required_unique_building_is_built_once_across_holding(small_holding, algorithm):
    base, catalog, rules = small_holding
    scenario = replace(base, required_buildings=(TEMPLE,), forbidden_buildings=(STEALTH,))
    economy = Economy(scenario, catalog, rules)
    report = economy.optimize(algorithm, workers=1)
    assert report["solver"]["status"] == "OPTIMAL"
    selected = [key for row in report["provinces"].values() for key in row["buildings"]]
    assert selected.count(TEMPLE) == 1
    assert STEALTH not in selected
    assert report["scenario"]["required_buildings"] == (TEMPLE,)
    assert report["scenario"]["forbidden_buildings"] == (STEALTH,)
    layout = {key: row["buildings"] for key, row in report["provinces"].items()}
    assert economy.evaluate(layout)["domestic_tax_income"] == report["domestic_tax_income"]


def test_independent_evaluation_rejects_missing_and_forbidden_buildings(small_holding):
    base, catalog, rules = small_holding
    layout = {p.id: [CASTLE, FARM] for p in base.provinces}
    Economy(base, catalog, rules).evaluate(layout)
    required = Economy(replace(base, required_buildings=(TEMPLE,)), catalog, rules)
    with pytest.raises(ValueError, match="Required buildings are missing"):
        required.evaluate(layout)
    layout["jap_owari"].append(TEMPLE)
    required.evaluate(layout)
    forbidden = Economy(replace(base, forbidden_buildings=(TEMPLE,)), catalog, rules)
    with pytest.raises(ValueError, match="Forbidden buildings selected"):
        forbidden.evaluate(layout)
    layout["jap_settsu"].append(TEMPLE)
    with pytest.raises(ValueError, match="Unique building duplicated"):
        required.evaluate(layout)


def test_required_choices_cannot_override_chain_occupancy(small_holding):
    base, catalog, rules = small_holding
    scenario = replace(
        base,
        provinces=base.provinces[:1],
        required_buildings=("sho_castle_1_fort", CASTLE),
    )
    assert Economy(scenario, catalog, rules).optimize(workers=1)["solver"]["status"] == "INFEASIBLE"


@pytest.mark.parametrize("kind", ["required_buildings", "forbidden_buildings"])
@pytest.mark.parametrize("ids", ["not-a-list", ("",), (1,), (TEMPLE, TEMPLE)])
def test_malformed_and_duplicate_identifiers_are_rejected(kind, ids):
    with pytest.raises(ValueError, match="building IDs"):
        Scenario("oda", (Province("jap_owari"),), **{kind: ids})


@pytest.mark.parametrize("kind", ["required_buildings", "forbidden_buildings"])
def test_unknown_identifiers_are_rejected(kind):
    scenario = replace(Scenario("oda", (Province("jap_owari"),)), **{kind: ("missing_building",)})
    with pytest.raises(ValueError, match="Unknown building IDs: missing_building"):
        Economy(scenario)


def test_contradictory_constraints_are_rejected():
    with pytest.raises(ValueError, match="both required and forbidden"):
        Scenario(
            "oda",
            (Province("jap_owari"),),
            required_buildings=(TEMPLE,),
            forbidden_buildings=(TEMPLE,),
        )


@pytest.mark.parametrize(
    "changes, building",
    [
        ({}, "sho_christian_1_chapel"),
        ({}, "sho_region_specialty_gold_mining_3_mining_complex"),
        ({"all_arts": False}, TEMPLE),
        ({"religion": "christian"}, TEMPLE),
    ],
)
def test_required_buildings_do_not_bypass_religion_site_or_research(changes, building):
    scenario = Scenario("oda", (Province("jap_owari"),), required_buildings=(building,), **changes)
    with pytest.raises(ValueError, match="Required buildings are unavailable"):
        Economy(scenario)


def test_optional_fields_are_immutable_and_default_reports_keep_their_shape(small_holding):
    base, catalog, rules = small_holding
    assert set(base.to_dict()) == {"clan", "provinces", "all_arts", "religion", "nanban_contact"}
    requirements = [TEMPLE]
    scenario = replace(base, required_buildings=requirements)
    requirements.clear()
    assert scenario.required_buildings == (TEMPLE,)
    report = Economy(base, catalog, rules).optimize(workers=1)
    assert report["scenario"] == base.to_dict()


def test_forbidding_a_known_unavailable_building_is_a_valid_noop():
    scenario = Scenario(
        "oda", (Province("jap_owari"),), forbidden_buildings=("sho_christian_1_chapel",)
    )
    result = Economy(scenario).optimize(workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
