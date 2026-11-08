"""Check the factored income formulation against every small original layout."""

from dataclasses import replace
from fractions import Fraction
from itertools import product

import pytest
from ortools.sat.python import cp_model

from games.tw.attila.compact import LIMIT, Builder, UnsupportedCompact, checked, common_unit
from games.tw.competition import solve
from games.tw.enums import NameType, ProblemState
from games.tw.problem import Problem
from games.tw.region import Region
from games.tw.solver_ortools import SolverOrTools
from tests.support.attila import building, province


@pytest.mark.parametrize(
    "values, unit",
    [
        ([Fraction(1, 6), Fraction(1, 10)], Fraction(1, 30)),
        ([Fraction(2, 3), Fraction(8, 3)], Fraction(2, 3)),
        ([Fraction(0), Fraction(1, 4), Fraction(-3, 10)], Fraction(1, 20)),
        ([Fraction(0), Fraction(0)], Fraction(1)),
    ],
)
def test_exact_common_units_preserve_the_greatest_integer_lattice(values, unit):
    assert common_unit(values) == unit
    assert all((value / unit).denominator == 1 for value in values)


@pytest.mark.parametrize("value", [LIMIT, -LIMIT, LIMIT + 1, -LIMIT - 1])
def test_integer_scaling_boundary_rejects_unsafe_domains(value):
    checked(-LIMIT + 1, 0, LIMIT - 1)
    with pytest.raises(UnsupportedCompact, match=r"^Compact integer domain exceeds safe scaling$"):
        checked(0, value)


@pytest.mark.parametrize("names", [NameType.NAME, NameType.PRINT_NAME])
def test_every_layout_matches_reference_with_scopes_clamps_and_other_income(names, context):
    context.name_type = names
    a, b = Region("a", context=context), Region("b", context=context)
    scenario = {
        "regions": {"a": {"minimum_sanitation": 0}, "b": {"minimum_sanitation": 0}},
        "provinces": {
            "one": {"corruption_percent": 50},
            "two": {"tax_percent": 80},
        },
        "base_tariffs": 17,
        "resource_prices": {"wood": 2},
        "resource_demand": {"wood": 6},
        "weights": [{"metric": "research_percent", "scope": "faction", "value": 3}],
        "projects": [{"region": "a", "base_cost": 100, "sanitation": True}],
        "project_budget": 75,
    }
    problem = Problem(objective="income", scenario=scenario, context=context)
    assert isinstance(problem.problem, SolverOrTools)
    for p in (province("one", a), province("two", b)):
        problem.add_province(p)
    candidates = [
        building(a, "factory", ("economy_gdp_industry", "building_to_building_own", 100)),
        building(a, "tax", ("province_tax_rate", "province_to_province_own", -150), upkeep=5),
        building(
            a,
            "reducer",
            ("building_corruption", "building_to_province_own", -120),
            (
                "building_construction_cost_mod_sanitation",
                "province_to_region_own",
                -60,
            ),
        ),
        building(b, "workshop", ("economy_gdp_industry", "building_to_building_own", 70)),
        building(b, "bonus", ("economy_gdp_mod_industry", "faction_to_region_own", 25)),
        building(
            b,
            "exporter",
            ("region_resource_wood_production", "building_to_building_own", 10),
            ("technology_research_points", "faction_to_faction_own", 6),
            upkeep=4,
        ),
    ]
    for candidate in candidates:
        candidate.lp_variable = problem.problem.solver.BoolVar(candidate.get_name())
    problem.problem.solver.Add(candidates[0].lp_variable == 1)
    problem.problem.solver.Add(sum(c.lp_variable for c in candidates[:3]) <= 2)
    problem.problem.solver.Add(sum(c.lp_variable for c in candidates[3:]) <= 2)
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    reference = problem.problem.binary_model()
    economy = problem.economy
    assert economy is not None
    assert reference.cp_sat_plan is not None
    builder = Builder(reference.cp_sat_plan, reference)
    compact, unit = builder.build()
    assert compact.validate() == ""
    auxiliaries = {variable.name(): terms for terms, variable in economy.products.items()}
    by_name = {name: index for index, name in enumerate(reference.names)}
    feasible_incomes = []
    for bits in product((0, 1), repeat=len(candidates)):
        selected = {c.get_name() for c, bit in zip(candidates, bits, strict=True) if bit}
        values = [
            economy.evaluate({auxiliaries.get(name, (name,)): 1}, selected)
            for name in reference.names
        ]
        expected = economy.evaluate_layout(selected)["objective"]
        assert reference.profit @ values + reference.offset == pytest.approx(expected)
        pinned = compact.clone()
        for candidate, bit in zip(candidates, bits, strict=True):
            variable = builder.variables[by_name[candidate.lp_variable.name()]]
            pinned.add(pinned.get_int_var_from_proto_index(variable.index) == bit)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        status = solver.solve(pinned)
        feasible = reference.feasible(values)
        assert (status == cp_model.OPTIMAL) == feasible
        if feasible:
            assert solver.objective_value * float(unit) == pytest.approx(expected)
            feasible_incomes.append(expected)
        else:
            assert status == cp_model.INFEASIBLE
    assert feasible_incomes
    compact_result = solve(reference, "cp-sat", workers=1)
    expanded_result = solve(replace(reference, cp_sat_plan=None), "cp-sat", workers=1)
    for result in (compact_result, expanded_result):
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(max(feasible_incomes))
        assert result.bound == pytest.approx(result.objective)
    assert compact_result.model_stats["formulation"] == "factored_income"


def test_unsupported_compact_scaling_falls_back_to_reference(monkeypatch, context):
    r = Region("r", context=context)
    problem = Problem(
        objective="income", scenario={"regions": {"r": {"minimum_sanitation": 0}}}, context=context
    )
    assert isinstance(problem.problem, SolverOrTools)
    problem.add_province(province("p", r))
    factory = building(r, "factory", ("economy_gdp_industry", "building_to_building_own", 100))
    factory.lp_variable = problem.problem.solver.BoolVar(factory.get_name())
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    model = problem.problem.binary_model()

    def unsupported(*args):
        raise UnsupportedCompact("test scaling limit")

    monkeypatch.setattr(model.cp_sat_plan, "solve", unsupported)
    result = solve(model, "cp-sat", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective == 100
    assert result.model_stats["fallback_reason"] == "test scaling limit"


def test_quadratic_income_keeps_the_expanded_formulation(context):
    r = Region("r", context=context)
    problem = Problem(
        objective="income", scenario={"regions": {"r": {"minimum_sanitation": 0}}}, context=context
    )
    assert isinstance(problem.problem, SolverOrTools)
    problem.add_province(province("p", r))
    candidates = [
        building(r, "factory", ("economy_gdp_industry", "building_to_building_own", 100)),
        building(r, "tax", ("province_tax_rate", "province_to_province_own", 20)),
    ]
    for candidate in candidates:
        candidate.lp_variable = problem.problem.solver.BoolVar(candidate.get_name())
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    result = solve(problem.problem.binary_model(), "cp-sat", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective == result.bound == 120
    assert result.model_stats["formulation"] == "expanded_boolean"
    assert "no cubic" in result.model_stats["fallback_reason"]
