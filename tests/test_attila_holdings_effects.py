"""Joint economics, explicit uniqueness rules and regional special placement."""

import pytest

from games.tw.attila.economy import Economy
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.scenario import Scenario
from games.tw.competition import BinaryModel, solve
from games.tw.enums import ProblemState
from games.tw.models.model_attila import AttilaFactions, AttilaRegionResources, AttilaReligion
from games.tw.problem import Problem
from games.tw.region import Region
from games.tw.solver_ortools import SolverOrTools
from tests.support.attila import building, province


def _joint_model(context, rules):
    scenario = {
        "regions": {key: {"minimum_sanitation": 0} for key in ("one", "two")},
        "building_rules": rules,
    }
    problem = Problem(context=context, scenario=scenario)
    for key in ("one", "two"):
        region = Region(key, context=problem.context)
        problem.add_province(province(key, region))
        building(
            region,
            key + "_farm",
            ("economy_gdp_agriculture_farming", "building_to_building_own", 100),
        )
        building(
            region,
            key + "_wonder",
            ("economy_gdp_mod_agriculture_farming", "faction_to_region_own", 100),
            upkeep=120,
        )
        for candidate in region.buildings:
            assert isinstance(problem.problem, SolverOrTools)
            candidate.lp_variable = problem.problem.solver.BoolVar(candidate.name)
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    assert isinstance(problem.problem, SolverOrTools)
    assert problem.economy is not None
    return BinaryModel.from_solver(problem.problem.solver), problem.economy


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip"])
def test_joint_limit_and_location_change_optimal_layout(context, algorithm):
    model, economy = _joint_model(
        context, [{"buildings": ["wonder"], "maximum": 1, "regions": ["two"]}]
    )
    result = solve(model, algorithm, seconds=5)
    assert result.status == "OPTIMAL"
    assert result.objective == pytest.approx(280)
    assert result.values is not None
    selected = {name for name, value in zip(model.names, result.values, strict=True) if value > 0.5}
    assert "two_wonder" in selected and "one_wonder" not in selected
    report = economy.evaluate_layout(selected)
    assert report["objective"] == pytest.approx(280)
    rule = report["assumptions"]["building_rules"][0]
    assert rule["source"] == "user_supplied_campaign_rule"
    assert rule["selected_count"] == 1 and rule["satisfied"]
    invalid = economy.evaluate_layout(set(economy.by_id))
    assert not invalid["assumptions"]["building_rules"][0]["satisfied"]


def test_no_inferred_uniqueness_and_explicit_zero_cap(context):
    model, _ = _joint_model(context, [])
    assert solve(model, "cp-sat").objective == pytest.approx(360)
    model, _ = _joint_model(context, [{"buildings": ["wonder"], "maximum": 0}])
    assert solve(model, "cp-sat").objective == pytest.approx(200)
    model, _ = _joint_model(context, [{"buildings": ["wonder"], "regions": []}])
    assert solve(model, "cp-sat").objective == pytest.approx(200)


def test_one_maximum_is_shared_by_every_listed_building_id(context):
    model, _ = _joint_model(context, [{"buildings": ["farm", "wonder"], "maximum": 2}])
    assert solve(model, "cp-sat").objective == pytest.approx(200)


@pytest.mark.parametrize(
    "rules",
    [
        None,
        [{}],
        [{"buildings": ["wonder"]}],
        [{"buildings": ["wonder"], "maximum": -1}],
        [{"buildings": ["wonder"], "maximum": True}],
        [{"buildings": ["wonder"], "maximum": 1.5}],
        [{"buildings": [], "maximum": 1}],
        [{"buildings": ["wonder", "wonder"], "maximum": 1}],
        [{"buildings": "wonder", "maximum": 1}],
        [{"buildings": ["wonder"], "regions": None}],
        [{"buildings": ["wonder"], "regions": ["one", "one"]}],
        [{"buildings": ["wonder"], "cap": 1}],
    ],
)
def test_building_rule_validation(rules):
    with pytest.raises((ValueError, TypeError)):
        Scenario({"building_rules": rules})


def test_building_rule_bind_and_immutable_json_roundtrip(context):
    rule = {"buildings": ["wonder"], "maximum": 1, "regions": ["two"]}
    scenario = Scenario({"building_rules": [rule]})
    rule["buildings"].append("other")
    assert scenario.building_rules[0].buildings == ("wonder",)
    assert Scenario(scenario.to_dict()).building_rules == scenario.building_rules
    with pytest.raises(ValueError, match="Unknown building IDs"):
        _joint_model(context, [{"buildings": ["typo"], "maximum": 1}])
    with pytest.raises(ValueError, match="unselected regions"):
        _joint_model(context, [{"buildings": ["wonder"], "regions": ["unowned"]}])


@pytest.mark.parametrize(
    "religion, resource",
    [
        (AttilaReligion.CHRIST_ORTHODOX, AttilaRegionResources.ATTILA_REGION_CHURCH_ORTHODOX),
        (AttilaReligion.CHRIST_CATHOLIC, AttilaRegionResources.ATTILA_REGION_CHURCH_CATHOLIC),
        (AttilaReligion.CHRIST_ARIAN, AttilaRegionResources.ATTILA_REGION_CHURCH_ARIAN),
    ],
)
def test_patriarchal_sites_and_dam_are_distinct(religion, resource):
    parser = load_attila(AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE, religion)
    assert parser.regions["att_reg_italia_roma"].has_ressource == resource
    assert parser.regions["att_reg_thracia_constantinopolis"].has_ressource == resource
    zafar = parser.regions["att_reg_arabia_felix_zafar"]
    assert zafar.has_ressource == AttilaRegionResources.ATTILA_REGION_NO_RESSOURCE
    problem = Problem(context=parser.context)
    for name in ("att_prov_thracia", "att_prov_arabia_felix"):
        problem.add_province(parser.provinces[name])
    for p in problem.provinces:
        for r in p.regions:
            r.add_buildings()
            patriarchal = [
                b for b in r.buildings if "religion_" in b.name and "legendary" in b.name
            ]
            assert bool(patriarchal) == (r.name == "att_reg_thracia_constantinopolis")
            assert all(religion.value in b.name for b in patriarchal)
            assert not [
                b
                for b in r.buildings
                if b.name.endswith("att_bld_eos_marib_dam") and r.name != zafar.name
            ]


def test_real_palace_faction_order_reaches_every_owned_province_once():
    parser = load_attila(
        AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE, AttilaReligion.CHRIST_ORTHODOX
    )
    regions = [Region(str(i), context=parser.context) for i in range(3)]
    palace = parser.buildings["att"]["att_bld_roman_east_civic_governor_5_legendary"].instantiate(
        parser.context
    )
    palace.region = regions[0]
    regions[0].buildings.append(palace)
    economy = Economy(
        [province("capital", regions[0]), province("other", *regions[1:])],
        scenario={"faction_traits": False, "religion_traits": False, "technology_effects": False},
    )
    report = economy.evaluate_layout(set(economy.by_id))
    assert report["public_order"] == {"capital": 18, "other": 1}


def test_catholic_alexandria_restores_its_patriarchal_chain_only_at_the_special_site():
    parser = load_attila(
        AttilaFactions.ATT_FACT_WESTERN_ROMAN_EMPIRE, AttilaReligion.CHRIST_CATHOLIC
    )
    snapshot = compile_scenario(
        [parser.provinces["att_prov_aegyptus"]], SnapshotOptions(fertility=5)
    )
    assert snapshot.economy is not None
    churches = {
        b.name for b in snapshot.economy.buildings if "religion_catholic_legendary" in b.name
    }
    assert churches == {
        "att_reg_aegyptus_alexandria_att_bld_religion_catholic_legendary_" + str(level)
        for level in range(1, 6)
    }


def test_real_celtic_market_bonuses_only_reach_selected_neighbors():
    parser = load_attila(AttilaFactions.ATT_FACT_EBDANI, AttilaReligion.PAGAN_CELTIC)
    regions = [Region(str(i), context=parser.context) for i in range(3)]
    for i, region in enumerate(regions):
        building(
            region,
            str(i) + "_trader",
            ("economy_gdp_trade_local", "building_to_building_own", 100),
        )
    market = parser.buildings["att"][
        "att_bld_barbarian_civic_market_general_5_legendary_celts"
    ].instantiate(parser.context)
    market.region = regions[0]
    regions[0].buildings.append(market)
    economy = Economy(
        [province("p" + str(i), r) for i, r in enumerate(regions)],
        adjacency={"p0": ["p1"], "p1": ["p0"], "p2": []},
        scenario={"faction_traits": False, "religion_traits": False, "technology_effects": False},
    )
    report = economy.evaluate_layout(set(economy.by_id))
    assert [report["regions"][str(i)]["wealth"] for i in range(3)] == [3100, 115, 100]
