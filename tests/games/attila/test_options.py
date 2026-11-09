"""Scenario options checked against direct arithmetic and exhaustive layouts."""

from itertools import product

import pytest

from games.optimization.competition import BinaryModel, solve
from games.tw.attila.builder import BinaryBuilder
from games.tw.attila.construction import Construction
from games.tw.attila.economy import Economy
from games.tw.attila.region import Region
from games.tw.attila.scenario import Scenario
from tests.support.attila import building, province
from tests.support.paths import REPO_ROOT


def test_scenario_clamps_offsets_targets_and_budget_against_enumeration(context):
    r = Region("r", context=context)
    p = province("p", r)
    scenario = {
        "provinces": {
            "p": {
                "corruption_percent": 50,
                "public_order": 20,
                "immigration_order": -10,
            }
        },
        "external_effects": [
            {
                "effect": "att_effect_sanitation_buildings",
                "scope": "region_to_region_own",
                "amount": 1,
                "region": "r",
            }
        ],
        "base_tariffs": 50,
        "resource_prices": {"wood": 2},
        "resource_demand": {"wood": 6},
        "targets": [{"metric": "resource:wood", "scope": "faction", "value": 4}],
        "projects": [
            {
                "name": "future well",
                "region": "r",
                "base_cost": 1000,
                "sanitation": True,
            }
        ],
        "project_budget": 450,
    }
    problem = Construction(objective="income", scenario=scenario, context=context)
    problem.add_province(p)
    candidates = [building(r, "factory", ("economy_gdp_industry", "building_to_building_own", 100))]
    for name in ("reducer1", "reducer2"):
        candidates.append(
            building(
                r,
                name,
                ("building_corruption", "building_to_province_own", -60),
                (
                    "building_construction_cost_mod_sanitation",
                    "province_to_region_own",
                    -60,
                ),
                ("public_order_immigration", "province_to_province_own", -60),
            )
        )
    candidates.append(
        building(
            r,
            "exporter",
            ("region_resource_wood_production", "building_to_building_own", 10),
            ("economy_trade_tariff_mod", "faction_to_faction_own", 20),
        )
    )
    for b in candidates:
        assert isinstance(problem.builder, BinaryBuilder)
        b.lp_variable = problem.builder.solver.BoolVar(b.name)
    problem.builder.create_constraint(
        "slots", [b.lp_variable for b in candidates], constraint_fn=lambda x: x <= 3
    )
    problem.add_objective()
    economy = problem.economy
    assert economy is not None
    model = BinaryModel.from_solver(problem.builder.solver)
    assert model.offset == 50
    auxiliary = {v.name(): key for key, v in economy.products.items()}
    for bits in product((0, 1), repeat=4):
        factory, a, b, exporter = bits
        selected = {
            candidate.name for candidate, enabled in zip(candidates, bits, strict=False) if enabled
        }
        values = []
        for name in model.names:
            monomial = auxiliary.get(name, (name,))
            values.append(economy.evaluate({monomial: 1}, selected))
        factor = max(0, 1 - 0.6 * a - 0.6 * b)
        expected = (
            100 * factory * (1 - 0.5 * factor)
            + 50 * (1 + 0.2 * exporter)
            + 2 * min(10 * exporter, 6)
        )
        feasible = sum(bits) <= 3 and exporter == 1 and 1000 * factor <= 450
        assert model.feasible(values) == feasible
        assert model.profit @ values + model.offset == pytest.approx(expected)
        layout = economy.evaluate_layout(selected, "income")
        assert layout["objective"] == pytest.approx(expected)
        assert layout["public_order"]["p"] == pytest.approx(20 - 10 * factor)
        assert layout["project_cost"] == pytest.approx(1000 * factor)
        assert layout["corruption_percent"]["r"] == pytest.approx(50 * factor)
    for name in ("cp-sat", "highs"):
        result = solve(model, name)
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(152)
        assert result.bound == pytest.approx(152)


def test_metrics_use_natural_recipient_counts_and_enable_is_boolean(context):
    a, b, c = (
        Region("a", context=context),
        Region("b", context=context),
        Region("c", context=context),
    )
    ps = [province("one", a, b), province("two", c)]
    building(
        a,
        "global",
        ("technology_research_points", "faction_to_faction_own", 10),
        ("religion_conversion_state", "faction_to_region_own", 2),
        ("province_growth_building", "faction_to_province_own", 3),
    )
    for i in (0, 1):
        building(
            a,
            f"spy{i}",
            ("agent_enable_recruitment_spy", "province_to_province_own", 1),
        )
    e = Economy(ps)
    selected = set(e.by_id)
    assert e.evaluate(e.metric("research_percent"), selected) == 10
    assert e.evaluate(e.metric("religion:state"), selected) == 6
    assert e.evaluate(e.metric("growth"), selected) == 6
    assert e.evaluate(e.metric("growth", "province", "one"), selected) == 3
    assert e.evaluate(e.metric("agent_enable:spy"), selected) == 1


def test_conditional_food_and_order_only_reach_explicit_recipients(context):
    a, b, c = (
        Region("a", context=context),
        Region("b", context=context),
        Region("c", context=context),
    )
    ps = [province("one", a), province("two", b), province("three", c)]
    building(
        a,
        "wonder",
        (
            "food_production_fertility_neighbouring",
            "region_to_province_own_factionwide",
            2,
        ),
        ("public_order_base_neighbouring", "province_to_province_own_adjacent_food", 3),
    )
    scenario = {
        "conditional_targets": {
            "att_effect_food_production_fertility_neighbouring": {"one": ["two"]},
            "att_effect_public_order_base_neighbouring": {"one": ["two"]},
        }
    }
    e = Economy(ps, scenario=scenario)
    selected = set(e.by_id)
    assert [e.evaluate(e.food(r), selected) for r in (a, b, c)] == [0, 4, 0]
    assert [e.evaluate(e.public_order(p), selected) for p in ps] == [0, 3, 0]
    without = Economy(ps)
    assert without.evaluate(without.food(b), selected) == 0
    assert any(reason == "requires_explicit_recipients" for _, _, reason in without.omitted)


def test_metric_weight_can_change_choice_and_external_wealth_is_constant(context):
    r = Region("r", context=context)
    p = province("p", r)
    scenario = {
        "weights": [{"metric": "research_percent", "scope": "faction", "value": 20}],
        "external_effects": [
            {
                "effect": "att_effect_sanitation_buildings",
                "scope": "region_to_region_own",
                "amount": 1,
                "region": "r",
            },
            {
                "effect": "att_effect_economy_gdp_culture",
                "scope": "building_to_building_own",
                "amount": 10,
                "region": "r",
            },
        ],
    }
    problem = Construction(scenario=scenario, context=context)
    problem.add_province(p)
    a = building(r, "factory", ("economy_gdp_industry", "building_to_building_own", 100))
    b = building(r, "library", ("technology_research_points", "faction_to_faction_own", 6))
    for v in (a, b):
        assert isinstance(problem.builder, BinaryBuilder)
        v.lp_variable = problem.builder.solver.BoolVar(v.name)
    problem.builder.create_constraint(
        "slots", [a.lp_variable, b.lp_variable], constraint_fn=lambda x: x <= 1
    )
    problem.add_objective()
    model = problem.builder.binary_model()
    result = solve(model, "cp-sat", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective == 130
    assert result.values[model.names.index("library")] == 1
    assert problem.economy is not None
    assert problem.economy.evaluate_layout({"library"})["objective_kind"] == "weighted_income"


@pytest.mark.parametrize(
    "data",
    [
        {"corupton": 10},
        {"provinces": {"p": {"corruption_percent": 120}}},
        {"resource_prices": {"fake": 10}},
        {"base_tariffs": float("nan")},
        {"targets": [{"metric": "fake", "scope": "faction", "value": 1}]},
        {
            "external_effects": [
                {
                    "effect": "fake",
                    "scope": "region_to_region_own",
                    "amount": 1,
                    "region": "r",
                }
            ]
        },
    ],
)
def test_invalid_scenario_is_rejected(data):
    with pytest.raises((ValueError, TypeError)):
        Scenario(data)


@pytest.mark.parametrize("base", [0.1, 0.3])
def test_rational_threshold_equality_and_both_clamp_boundaries(context, base):
    from games.tw.attila.algebra import add

    r = Region("r", context=context)
    p = province("p", r)
    problem = Construction(context=context)
    for name in ("x", "y"):
        b = building(r, name)
        assert isinstance(problem.builder, BinaryBuilder)
        b.lp_variable = problem.builder.solver.BoolVar(name)
    e = Economy([p])
    polynomial = add({(): base}, {("x",): -0.1, ("y",): -0.2})
    objective = e.cap(e.floor_zero(polynomial), 0.15)
    problem.builder.add_objective_terms(e.compile(objective, problem.builder))
    model = BinaryModel.from_solver(problem.builder.solver)
    auxiliaries = {v.name(): k for k, v in e.products.items()}
    for x, y in product((0, 1), repeat=2):
        selected = {n for n, enabled in (("x", x), ("y", y)) if enabled}
        values = [e.evaluate({auxiliaries.get(n, (n,)): 1}, selected) for n in model.names]
        assert model.feasible(values)
        expected = min(0.15, max(0, base - 0.1 * x - 0.2 * y))
        assert model.profit @ values + model.offset == pytest.approx(expected)
    result = solve(model, "cp-sat")
    assert result.status == "OPTIMAL"
    assert result.objective == pytest.approx(min(base, 0.15))
    assert result.bound == pytest.approx(result.objective)


def test_highs_backend_compiles_piecewise_discount(context):
    r = Region("r", context=context)
    p = province("p", r)
    problem = Construction(context=context)
    b = building(r, "x")
    b.lp_variable = problem.builder.solver.BoolVar("x")
    e = Economy([p])
    terms = e.cap(e.floor_zero({(): 0.3, ("x",): -0.2}), 0.15)
    problem.builder.add_objective_terms(e.compile(terms, problem.builder))
    result = solve(problem.builder.binary_model(), "highs", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective == pytest.approx(0.15)


def test_state_religion_influence_joins_selected_faith_without_double_counting(context):
    from types import SimpleNamespace

    context.instance = SimpleNamespace(religion=SimpleNamespace(value="orthodox"))
    r = Region("r", context=context)
    p = province("p", r)
    building(r, "church", ("religion_conversion_orthodox", "region_to_region_own", 3))
    building(r, "authority", ("religion_conversion_state", "faction_to_region_own", 1))
    building(r, "other_faith", ("religion_conversion_catholic", "region_to_region_own", 5))
    e = Economy([p])
    for metric in ("religion:state", "religion:orthodox"):
        assert e.evaluate(e.metric(metric), set(e.by_id)) == 4
    assert e.evaluate(e.metric("religion:catholic"), set(e.by_id)) == 5


def test_immigration_wealth_bonus_only_boosts_immigration_income(context):
    r = Region("r", context=context)
    p = province("p", r)
    building(r, "industry", ("economy_gdp_industry", "building_to_building_own", 1000))
    building(
        r,
        "immigration_bonus",
        ("economy_gpd_mod_immigration", "province_to_province_own", 30),
    )
    e = Economy([p], scenario={"regions": {"r": {"immigration_wealth": 100}}})
    assert e.evaluate(e.objective(), set(e.by_id)) == 1130


@pytest.mark.parametrize(
    "religion,key",
    [
        ("CHRIST_EAST", "att_bld_eos_religion_east_church_major_1"),
        ("TENGRISM", "att_bld_religion_tengri_major_1"),
    ],
)
def test_religion_aliases_do_not_remove_eligible_buildings(religion, key):
    from games.tw.attila.game import AttilaReligion
    from games.tw.attila.loader import AttilaLoader

    parser = object.__new__(AttilaLoader)
    parser.religion = AttilaReligion[religion]
    assert parser.building_is_of_religion(key)
    assert not parser.building_is_of_religion("att_bld_religion_orthodox_major_1")


def test_economic_and_metric_coverage_is_not_silently_dropped():
    from games.tw.attila.tools.audit_data import audit

    records = {r["effect"]: r for r in audit()["effects"] if r["reach"] != "other"}
    for effect in (
        "att_effect_building_corruption",
        "att_effect_economy_trade_tariff_mod",
        "att_effect_building_construction_cost_mod_sanitation",
    ):
        assert records[effect]["status"] == "scenario_option"
    for effect in (
        "att_effect_region_resource_wood_production",
        "att_effect_province_growth_building",
        "att_effect_technology_research_points",
        "att_effect_religion_conversion_orthodox",
    ):
        assert records[effect]["status"] == "metric_option"


@pytest.mark.parametrize(
    "example,names",
    [
        ("campaign-income", ["Aegyptus"]),
        ("priorities", ["Aegyptus"]),
        ("joint", ["Aegyptus", "Aethiopia"]),
    ],
)
def test_shipped_scenarios_bind_to_real_data(example, names):
    import json

    from games.tw.attila.game import AttilaGame
    from games.tw.attila.model import load_attila

    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
    )
    path = REPO_ROOT / "games/tw/attila/scenarios" / (example + ".json")
    Scenario(json.loads(path.read_text())).bind(
        [p for p in parser.provinces.values() if p.print_name in names]
    )
