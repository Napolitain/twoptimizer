"""Independent scoped-economy examples and exact optimization cross-checks."""

from itertools import product

import pytest

from games.tw.attila.economy import Economy
from games.tw.attila.effects import Reach, reach
from games.tw.building import Building
from games.tw.competition import BinaryModel, solve
from games.tw.enums import ProblemState, Scope
from games.tw.problem import Problem
from games.tw.province import Province
from games.tw.region import Region
from games.tw.solver_ortools import SolverOrTools


def building(region, name, *effects, upkeep=0):
    b = Building(name, context=region.context)
    b.region = region
    b.metadata = {"metadata": {"upkeep": upkeep}}
    for key, scope, value in effects:
        b.add_effect("att_effect_" + key, Scope.REGION, value, raw_scope=scope)
    region.buildings.append(b)
    return b


def province(name, *regions):
    p = Province(name, context=regions[0].context)
    for region in regions:
        p.add_region(region)
    return p


def selected(economy):
    return set(economy.by_id)


def test_local_province_category_and_building_bonuses(context):
    r1, r2 = Region("one", context=context), Region("two", context=context)
    building(r1, "factory1", ("economy_gdp_industry", "building_to_building_own", 100))
    building(r2, "factory2", ("economy_gdp_industry", "building_to_building_own", 100))
    building(r1, "farm", ("economy_gdp_agriculture_farming", "building_to_building_own", 50))
    building(r1, "local", ("economy_gdp_mod_industry", "building_to_region_own", 10))
    building(r1, "provincial", ("economy_gdp_mod_industry", "province_to_region_own", 20))
    # A building-only bonus boosts its own 100 wealth, not either other factory.
    building(
        r1,
        "self",
        ("economy_gdp_industry", "building_to_building_own", 100),
        ("economy_gdp_mod_industry", "building_to_building_own", 50),
    )
    economy = Economy([province("p", r1, r2)])
    report = economy.evaluate_layout(selected(economy))
    assert report["regions"]["one"]["wealth"] == 130 + 50 + 180
    assert report["regions"]["two"]["wealth"] == 120
    assert report["objective"] == 480


def test_sanitation_fertility_food_and_order_are_not_double_counted(context):
    r1, r2 = Region("one", context=context), Region("two", context=context)
    r1.fertility, r2.fertility = 2, 5
    building(
        r1,
        "health",
        ("sanitation_buildings", "region_to_region_own", 3),
        ("sanitation_buildings_region", "province_to_region_own", 2),
        ("public_order_base", "province_to_province_own", 4),
        ("public_order_immigration", "province_to_province_own", -20),
    )
    for i, region in enumerate((r1, r2)):
        building(
            region,
            f"farm{i}",
            ("food_production_fertility", "region_to_region_own", 10),
            ("food_consumption", "region_to_region_own", 5),
            ("economy_gdp_fertility_agriculture", "building_to_building_own", 100),
        )
    building(r1, "fertilizer", ("province_fertility_buildings", "building_to_region_own", 1))
    economy = Economy([province("p", r1, r2)])
    report = economy.evaluate_layout(selected(economy))
    assert report["regions"]["one"] == {
        "wealth": 300,
        "food": 25,
        "sanitation": 5,
        "fertility": 3,
    }
    assert report["regions"]["two"] == {
        "wealth": 500,
        "food": 45,
        "sanitation": 2,
        "fertility": 5,
    }
    assert report["public_order"] == {"p": 4}
    assert any("immigration" in row[2] for row in economy.omitted)


def test_faction_and_adjacent_bonuses_have_distinct_targets(context):
    regions = [Region(str(i), context=context) for i in range(3)]
    provinces = [province(f"p{i}", r) for i, r in enumerate(regions)]
    for i, region in enumerate(regions):
        building(
            region,
            f"factory{i}",
            ("economy_gdp_industry", "building_to_building_own", 100),
        )
    building(regions[0], "global", ("economy_gdp_mod_industry", "faction_to_region_own", 10))
    building(
        regions[0],
        "adjacent",
        (
            "economy_gdp_mod_industry",
            "province_to_regions_own_in_adjacent_province",
            20,
        ),
    )
    economy = Economy(provinces, {"p0": ["p1"]})
    assert [economy.evaluate(economy.wealth(r), selected(economy)) for r in regions] == [
        110,
        130,
        110,
    ]
    assert reach("force_to_force_own_factionwide") == Reach.OTHER
    assert reach("province_to_region_own_factionwide") == Reach.FACTION


def test_unknown_effects_are_preserved_without_becoming_resources(context):
    r = Region("one", context=context)
    b = building(
        r,
        "unknown",
        ("food_mystery_percentage", "region_to_region_own", 1000),
        ("public_order_mystery", "region_to_region_own", -1000),
        ("economy_gdp_industry", "force_to_force_building", 9000),
    )
    assert len(b.raw_effects) == 3
    assert b.food() == b.public_order() == b.gdp() == 0
    assert len(Economy([province("p", r)]).omitted) == 3


@pytest.mark.parametrize("mode", ["wealth", "income"])
def test_compiled_scoped_model_matches_independent_enumeration(context, mode):
    r = Region("one", context=context)
    p = province("p", r)
    problem = Problem(objective=mode, context=context)
    problem.add_province(p)
    b = [
        building(r, "factory", ("economy_gdp_industry", "building_to_building_own", 100)),
        building(
            r,
            "industry_bonus",
            ("economy_gdp_mod_industry", "province_to_region_own", 50),
            upkeep=40,
        ),
        building(r, "tax", ("province_tax_rate", "province_to_province_own", 20), upkeep=20),
        building(r, "health", ("sanitation_buildings", "region_to_region_own", 1)),
    ]
    for candidate in b:
        assert isinstance(problem.problem, SolverOrTools)
        candidate.lp_variable = problem.problem.solver.BoolVar(candidate.name)
    problem.problem.create_constraint(
        "slots", [v.lp_variable for v in b], constraint_fn=lambda x: x <= 3
    )
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    exported = BinaryModel.from_solver(problem.problem.solver)
    candidates = []
    for factory, bonus, tax, health in product((0, 1), repeat=4):
        if health and factory + bonus + tax + health <= 3:
            wealth = 100 * factory * (1 + 0.5 * bonus)
            income = wealth * (1 + 0.2 * tax) - 40 * bonus - 20 * tax
            candidates.append(wealth if mode == "wealth" else income)
    expected = max(candidates)
    for algorithm in ("cp-sat", "cbc", "scip"):
        result = solve(exported, algorithm, seconds=5)
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(expected)
    problem.solve()
    layout = {v.name() for v in problem.problem.variables() if v.solution_value() > 0.5}
    assert problem.economy is not None
    assert problem.economy.evaluate_layout(layout, mode)["objective"] == pytest.approx(expected)


def test_two_canals_stack_locally_and_across_all_three_regions(context):
    regions = [Region(str(i), context=context) for i in range(3)]
    for i in (0, 1):
        building(
            regions[i],
            f"canal{i}",
            ("sanitation_buildings", "region_to_region_own", 3),
            ("sanitation_buildings_region", "province_to_region_own", 4),
        )
    economy = Economy([province("p", *regions)])
    assert [economy.evaluate(economy.sanitation(r), selected(economy)) for r in regions] == [
        11,
        11,
        8,
    ]


def test_display_tree_does_not_make_distinct_branches_exclusive(context):
    problem = Problem(context=context)
    region = Region("r", context=problem.context)
    candidates = []
    for name in ("r_farm_grain_1", "r_farm_grain_2", "r_farm_cattle_1"):
        candidate = Building(name, context=region.context)
        candidate.metadata = {"metadata": {"source_tree_group": "agriculture"}}
        assert isinstance(problem.problem, SolverOrTools)
        candidate.lp_variable = problem.problem.solver.BoolVar(name)
        region.buildings.append(candidate)
        candidates.append(candidate.lp_variable)
    region.add_chain_constraint()
    assert isinstance(problem.problem, SolverOrTools)
    problem.problem.solver.Maximize(100 * candidates[0] + 200 * candidates[1] + 100 * candidates[2])
    problem.problem.solve()
    assert problem.problem.get_objective() == 300


def test_real_catalogue_eligibility_and_no_technology_scenario():
    from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
    from games.tw.models.game_attila import AttilaGame

    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
    )
    problem = Problem(context=parser.context)
    p = next(p for p in parser.provinces.values() if p.print_name == "Thracia")
    problem.add_province(p)
    try:
        for region in p.regions:
            region.add_buildings()
            region.filter_city_level(4)
            region.filter_building_level(1)
            region.filter_military()
            assert region.buildings
            for candidate in region.buildings:
                assert "_barbmigs_" not in candidate.name and "_nomad_" not in candidate.name
                assert "eastern-roman" in candidate.metadata["requirements_by_culture"]
                if "religion" in candidate.name:
                    assert "orthodox" in candidate.name
    finally:
        p.clean()
    model = compile_scenario([p], SnapshotOptions(fertility=5, technologies=frozenset())).model
    # Level-4 cities require research; no researched technology is infeasible.
    assert solve(model, "cp-sat").status == "INFEASIBLE"
