"""Joint Rome economics: exhaustive layouts, recipients and shared constraints."""

import copy
import itertools
import json
from dataclasses import replace

import pytest

from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario, joint_model_fingerprint
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import effect, tiny_catalog


def provinces():
    return tuple(
        Scenario(
            "rom_rome",
            (Site(site, major=True, slots=1),),
            name=name,
            external_food=2,
            minimum_order=-10,
        )
        for name, site in (("one", "a"), ("two", "b"))
    )


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip", "scip-nonlinear", "portfolio"])
def test_joint_backends_match_exhaustive_economics(algorithm):
    data = tiny_catalog()
    data["buildings"]["rome_religious_alpha_4"]["effects"][0]["scope"] = "in_all_your_regions"
    scenario = HoldingScenario.from_provinces(provinces(), ())
    economy = HoldingEconomy(scenario, data)
    optimum = max(
        economy.evaluate({"a": ["rome_city_4", *first], "b": ["rome_city_4", *second]}, party)[
            "domestic_net_income"
        ]
        for first, second, party in itertools.product(
            ((), ("rome_religious_alpha_4",), ("rome_religious_beta_4",)),
            ((), ("rome_religious_alpha_4",), ("rome_religious_beta_4",)),
            economy.parties,
        )
    )
    result = economy.optimize(algorithm, seconds=5, workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["domestic_net_income"] == pytest.approx(optimum)
    assert result["solver"]["bound"] == pytest.approx(optimum)
    assert len(result["provinces"]) == 2


def test_worldwide_bonus_reaches_other_province_and_maintenance_paid_once():
    data = tiny_catalog()
    data["buildings"]["rome_religious_alpha_4"]["effects"] = [
        effect("rom_building_gdp_mod_industry", 20, "in_all_your_regions"),
        effect("dk_building_gdp_maintenance", -7, "this_faction"),
        effect("rom_building_public_order_happiness", 3, "in_all_your_provinces"),
    ]
    scenario = HoldingScenario.from_provinces(tuple(replace(p, party=0) for p in provinces()), ())
    economy = HoldingEconomy(scenario, data)
    layout = {"a": ["rome_city_4", "rome_religious_alpha_4"], "b": ["rome_city_4"]}
    row = economy.evaluate(layout, 0)
    assert row["domestic_tax_income"] == pytest.approx(2 * 100 * 1.3 * 1.1)
    assert row["building_maintenance"] == 7
    assert row["domestic_net_income"] == pytest.approx(279)
    assert row["provinces"]["two"]["public_order"] == 3
    assert row["provinces"]["two"]["building_maintenance"] == 0


def test_adjacent_food_counts_owned_regions_once_and_not_source_or_unlinked():
    data = tiny_catalog()
    data["buildings"]["rome_religious_alpha_4"]["effects"] = [
        effect("rom_building_food_farming_grain", 4, "in_all_your_regions_in_adjacent_provinces")
    ]
    one, two = (replace(p, external_food=0, party=0) for p in provinces())
    two = replace(two, sites=(Site("b", major=True, slots=0), Site("c", slots=0)))
    three = replace(one, name="three", sites=(Site("d", major=True, slots=0),))
    layout = {
        "a": ["rome_city_4", "rome_religious_alpha_4"],
        "b": ["rome_city_4"],
        "c": ["rome_town_4"],
        "d": ["rome_city_4"],
    }
    economy = HoldingEconomy(
        HoldingScenario.from_provinces((one, two, three), (("two", "one"),)), data
    )
    row = economy.evaluate(layout, 0)
    assert row["food_surplus"] == 8
    assert [p["food_surplus"] for p in row["provinces"].values()] == [0, 8, 0]
    isolated = HoldingEconomy(HoldingScenario.from_provinces((one, two, three), ()), data)
    assert isolated.evaluate(layout, 0)["food_surplus"] == 0
    result = economy.optimize("cp-sat", seconds=5, workers=1)
    assert result["solver"]["status"] == "OPTIMAL"


def test_food_shared_but_order_is_local():
    data = tiny_catalog()
    one, two = provinces()
    one = replace(one, external_food=2)
    two = replace(two, external_food=0)
    layout = {"a": ["rome_city_4"], "b": ["rome_city_4", "rome_religious_beta_4"]}
    with pytest.raises(ValueError, match="Food deficit"):
        Economy(two, data).evaluate({"b": layout["b"]}, 0)
    holding = HoldingEconomy(HoldingScenario.from_provinces((one, two), ()), data)
    row = holding.evaluate(layout, 0)
    assert row["food_surplus"] == 0
    assert row["provinces"]["two"]["food_surplus"] == -2
    two = replace(two, minimum_order=0)
    with pytest.raises(ValueError, match="local public order"):
        HoldingEconomy(HoldingScenario.from_provinces((one, two), ()), data).evaluate(layout, 0)


@pytest.mark.parametrize(
    ("scope", "food_each"),
    [("this_building", 4), ("this_province", 4), ("in_all_your_provinces", 8)],
)
def test_nonregional_food_is_not_multiplied_by_the_province_region_count(scope, food_each):
    data = tiny_catalog()
    data["buildings"]["rome_city_4"]["effects"].append(
        effect("rom_building_food_farming_grain", 4, scope)
    )
    one = Scenario("rom_rome", (Site("a", major=True, slots=0), Site("b", slots=0)), name="one")
    two = Scenario("rom_rome", (Site("c", major=True, slots=0),), name="two")
    economy = HoldingEconomy(HoldingScenario.from_provinces((one, two), ()), data)
    layout = {"a": ["rome_city_4"], "b": ["rome_town_4"], "c": ["rome_city_4"]}
    checked = economy.evaluate(layout, 0)
    assert [row["food_surplus"] for row in checked["provinces"].values()] == [food_each] * 2
    result = economy.optimize("cp-sat", seconds=5, workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["food_surplus"] == 2 * food_each


def test_warm_start_and_portable_proof_replay_joint_layout():
    scenario = HoldingScenario.from_provinces(provinces(), ())
    economy = HoldingEconomy(scenario, tiny_catalog())
    result = economy.optimize("cp-sat", workers=1)
    for algorithm in ("cp-sat", "scip-nonlinear"):
        new = HoldingEconomy(scenario, tiny_catalog()).optimize(
            algorithm, workers=1, incumbent=result
        )
        assert new["solver"]["status"] == "OPTIMAL"
        assert new["domestic_net_income"] == result["domestic_net_income"]
    reused = HoldingEconomy(scenario, tiny_catalog()).reuse_optimum(result)
    assert reused["domestic_net_income"] == result["domestic_net_income"]
    invalid = copy.deepcopy(result)
    invalid["domestic_net_income"] += 1
    with pytest.raises(ValueError, match="Warm start"):
        economy.warm_values(invalid)


def test_joint_round_trip_and_validation():
    scenario = HoldingScenario.from_provinces(provinces(), (("one", "two"),))
    restored = HoldingScenario.from_dict(json.loads(json.dumps(scenario.to_dict())))
    assert restored == scenario
    assert len(joint_model_fingerprint()) == 64
    for borders in ((("one", "one"),), (("one", "missing"),), (("one", "two"), ("two", "one"))):
        with pytest.raises(ValueError):
            HoldingScenario.from_provinces(provinces(), borders)
    with pytest.raises(ValueError, match="at least one"):
        HoldingScenario.from_provinces((), ())
    one, two = provinces()
    with pytest.raises(ValueError, match="names"):
        HoldingScenario.from_provinces((one, replace(two, name="one")), ())
    with pytest.raises(ValueError, match="one faction"):
        HoldingScenario.from_provinces((one, replace(two, faction="other")), ())
    with pytest.raises(ValueError, match="regions"):
        HoldingScenario.from_provinces((one, replace(two, sites=one.sites)), ())


def test_application_joint_preparation_spreads_owned_world_bonus():
    from twoptimizer.adapters.rome2 import prepare_scenario
    from twoptimizer.models import RunConfig

    config = RunConfig(
        game="rome2",
        faction="rom_rome",
        province="rome_main_italia",
        provinces=("rome_main_italia", "rome_main_africa"),
        joint=True,
        adjacency=(),
    )
    scenario = prepare_scenario(config)
    assert isinstance(scenario, HoldingScenario)
    africa = next(p for p in scenario.provinces if p.name == "rome_main_africa")
    assert any(
        m.source_region == "rom_italia_samnium" and m.scope == "faction" for m in africa.modifiers
    )
    disabled = prepare_scenario(replace(config, world_bonuses=False))
    assert isinstance(disabled, HoldingScenario)
    assert all(not p.modifiers for p in disabled.provinces)
    with pytest.raises(ValueError, match="named campaign"):
        prepare_scenario(replace(config, provinces=("coastal", "rome_main_africa")))


@pytest.mark.parametrize(
    "key,value",
    [
        ("faction", "wrong"),
        ("name", "wrong"),
        ("joint", False),
        ("unknown", 1),
        ("all_technologies", True),
    ],
)
def test_joint_report_rejects_inconsistent_metadata(key, value):
    record = HoldingScenario.from_provinces(provinces(), ()).to_dict()
    record[key] = value
    with pytest.raises(ValueError, match="metadata"):
        HoldingScenario.from_dict(record)


def test_joint_research_is_one_faction_profile():
    one, two = provinces()
    with pytest.raises(ValueError, match="research profile"):
        HoldingScenario.from_provinces((one, replace(two, all_technologies=True)), ())
    scenario = HoldingScenario.from_provinces(
        tuple(
            replace(p, all_technologies=True, technology_profile="archived") for p in provinces()
        ),
        (),
    )
    assert scenario.all_technologies
    assert scenario.technology_profile == "archived"
    assert HoldingScenario.from_dict(scenario.to_dict()) == scenario


def test_direct_inconsistent_joint_scenario_is_rejected():
    scenario = HoldingScenario.from_provinces(provinces(), ())
    with pytest.raises(ValueError, match="consistent joint settings"):
        HoldingEconomy(replace(scenario, faction="wrong"), tiny_catalog())


def test_joint_growth_report_includes_remote_recipient():
    data = tiny_catalog()
    data["buildings"]["rome_religious_alpha_4"]["effects"].append(
        effect("rom_building_growth_all", 6, "in_all_your_provinces")
    )
    economy = HoldingEconomy(HoldingScenario.from_provinces(provinces(), ()), data)
    report = economy.evaluate(
        {"a": ["rome_city_4", "rome_religious_alpha_4"], "b": ["rome_city_4"]}, 0
    )
    assert report["provinces"]["one"]["growth_contribution_unvalued"] == 6
    assert report["provinces"]["two"]["growth_contribution_unvalued"] == 6
    assert report["sites"]["a"]["growth_contribution_unvalued"] == 6
    assert report["sites"]["b"]["growth_contribution_unvalued"] == 0


def test_indexed_selection_bound_preserves_signed_duplicate_terms():
    from ortools.linear_solver import pywraplp

    from games.tw.rome2.compiler import RomeCompiler, variable_name
    from games.tw.rome2.holding_compiler import HoldingProducts
    from games.tw.rome2.linear import LinearProducts

    economy = HoldingEconomy(HoldingScenario.from_provinces(provinces(), ()), tiny_catalog())
    solver = pywraplp.Solver.CreateSolver("CBC")
    choices = {}
    for local in economy.locals.values():
        selected, _ = RomeCompiler(local)._compile_choices(solver)
        choices.update(selected)
    parties = {i: solver.BoolVar("party:" + str(i)) for i in economy.parties}
    cached = HoldingProducts(
        economy, solver, choices, parties, HoldingProducts.index(economy, choices)
    )
    legacy = LinearProducts(economy, solver, choices, parties)
    amounts = [(-7, 3), (30, -5), (-40, 12), (2, 0), (10, 30), (5, -20)]
    terms = [
        (amount, variable)
        for variable, pair in zip(choices.values(), amounts, strict=True)
        for amount in pair
    ] + [(12, next(iter(parties.values())))]
    bound = cached.selection_upper(terms)
    assert bound == legacy.selection_upper(terms)
    for first, second, party in itertools.product(
        (None, "rome_religious_alpha_4", "rome_religious_beta_4"),
        (None, "rome_religious_alpha_4", "rome_religious_beta_4"),
        parties,
    ):
        selected = {"a:rome_city_4", "b:rome_city_4", "party:" + str(party)}
        selected.update(
            f"{site}:{building}" for site, building in (("a", first), ("b", second)) if building
        )
        assert (
            sum(amount for amount, variable in terms if variable_name(variable) in selected)
            <= bound
        )


@pytest.mark.parametrize(
    "effect_id,scope",
    [
        ("rom_building_gdp_mod_industry", "this_region"),
        ("rom_building_gdp_industry_manufacture", "in_all_your_regions"),
        ("rom_building_tax_level", "this_building"),
        ("rom_building_public_order_happiness", "in_all_your_regions"),
    ],
)
def test_joint_rejects_economic_scopes_needing_finer_recipient_rules(effect_id, scope):
    data = tiny_catalog()
    data["buildings"]["rome_religious_alpha_4"]["effects"].append(effect(effect_id, 10, scope))
    with pytest.raises(ValueError, match="additional recipient rules"):
        HoldingEconomy(HoldingScenario.from_provinces(provinces(), ()), data)


def test_imported_rome_scopes_fit_joint_aggregation():
    from games.tw.rome2.catalog import load_data
    from games.tw.rome2.holding_scopes import validate_economic_scope

    for building in load_data()["buildings"].values():
        for raw in building["effects"]:
            validate_economic_scope(raw)
