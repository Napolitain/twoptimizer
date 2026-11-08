"""Check the factored income formulation against every small original layout."""

from dataclasses import replace
from fractions import Fraction
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.tw.attila.compact import LIMIT, Builder, UnsupportedCompact, checked, common_unit
from games.tw.competition import BinaryModel, solve
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
    observations, models = [], []
    compact_result = solve(
        reference,
        "cp-sat",
        workers=1,
        on_search=lambda *row: observations.append(row),
        on_model=models.append,
    )
    expanded_result = solve(replace(reference, cp_sat_plan=None), "cp-sat", workers=1)
    for result in (compact_result, expanded_result):
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(max(feasible_incomes))
        assert result.bound == pytest.approx(result.objective)
    assert compact_result.model_stats["formulation"] == "factored_income"
    assert unit != 1  # This fixture exercises conversion from a nontrivial native income unit.
    assert models == [compact_result.model_stats]
    assert observations[-1][:2] == pytest.approx((max(feasible_incomes), max(feasible_incomes)))
    for objective, bound, _ in observations:
        if objective is not None:
            assert any(objective == pytest.approx(income) for income in feasible_incomes)
        if bound is not None:
            assert bound >= max(feasible_incomes) - 1e-9


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


def _selector_builder(*, capacity=1):
    names = ("wealth_a", "wealth_b", "tax_a", "tax_b", "keep_a", "keep_b")
    reference = BinaryModel(
        names=names,
        profit=np.zeros(6),
        matrix=np.array([[0, 0, 1, 1, 0, 0], [0, 0, 0, 0, 1, 1]]),
        lower=np.array([-np.inf, -np.inf]),
        upper=np.array([capacity, capacity]),
    )
    plan = SimpleNamespace(definitions={}, definition_rows=(), aliases={})
    builder = Builder(plan, reference)
    for index in range(6):
        builder.variable(index)
    builder.model.add(builder.variable(2) + builder.variable(3) <= capacity)
    builder.model.add(builder.variable(4) + builder.variable(5) <= capacity)
    return builder


def _check_selector_layouts(builder, value, expected, capacity=1):
    assert builder.model.validate() == ""
    for bits in product((0, 1), repeat=6):
        pinned = builder.model.clone()
        for index, bit in enumerate(bits):
            variable = builder.variables[index]
            pinned.add(pinned.get_int_var_from_proto_index(variable.index) == bit)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        status = solver.solve(pinned)
        if bits[2] + bits[3] > capacity or bits[4] + bits[5] > capacity:
            assert status == cp_model.INFEASIBLE
        else:
            assert status == cp_model.OPTIMAL
            assert solver.value(value.variable) * value.unit == expected(bits)


def test_exclusive_tax_and_keep_values_use_exact_signed_linear_branches():
    builder = _selector_builder()
    wealth = builder.expression({(): 3, ("wealth_a",): -7, ("wealth_b",): 11}, "wealth")
    tax = builder.expression(
        {(): Fraction(3, 2), ("tax_a",): Fraction(1, 4), ("tax_b",): Fraction(-5, 2)}, "tax"
    )
    keep = builder.expression({(): 1, ("keep_a",): -1, ("keep_b",): 2}, "keep")
    assert wealth.selector is not None and len(wealth.selector.groups) == 2
    assert tax.selector is not None and len(tax.selector.groups) == 1
    assert keep.selector is not None and len(keep.selector.groups) == 1
    income = builder.product([wealth, tax, keep], "income")
    assert not any(row.has_int_prod() for row in builder.model.proto.constraints)
    _check_selector_layouts(
        builder,
        income,
        lambda b: (
            (3 - 7 * b[0] + 11 * b[1])
            * (Fraction(3, 2) + Fraction(1, 4) * b[2] - Fraction(5, 2) * b[3])
            * (1 - b[4] + 2 * b[5])
        ),
    )


def test_nonlinear_factors_retain_generic_product():
    builder = _selector_builder(capacity=2)
    wealth = builder.expression({("wealth_a", "wealth_b"): 2}, "wealth")
    tax = builder.expression({(): 1, ("tax_a", "tax_b"): 3}, "tax")
    assert wealth.selector is tax.selector is None
    builder.product([wealth, tax], "income")
    assert any(row.has_int_prod() for row in builder.model.proto.constraints)


def test_nonexclusive_tax_choices_remain_independent_instead_of_becoming_one_chain():
    builder = _selector_builder(capacity=2)
    wealth = builder.expression({(): 3, ("wealth_a", "wealth_b"): 2}, "wealth")
    tax = builder.expression({(): 1, ("tax_a",): 2, ("tax_b",): -3}, "tax")
    assert tax.selector is not None and len(tax.selector.groups) == 2
    income = builder.product([wealth, tax], "income")
    _check_selector_layouts(
        builder,
        income,
        lambda b: (3 + 2 * b[0] * b[1]) * (1 + 2 * b[2] - 3 * b[3]),
        capacity=2,
    )


def test_indexed_cardinality_pruning_matches_all_original_groups():
    builder = _selector_builder()
    for bits in product((0, 1), repeat=6):
        indices = frozenset(index for index, bit in enumerate(bits) if bit)
        assert builder.violates_groups(indices) == any(
            len(indices & group) > capacity for group, capacity in builder.groups
        )


def test_single_boolean_selector_and_repeated_factor_keep_multiplicity():
    builder = _selector_builder()
    factor = builder.expression({(): -2, ("wealth_a",): 3}, "factor")
    assert factor.selector is not None
    squared = builder.product([factor, factor], "square")
    assert not any(row.has_int_prod() for row in builder.model.proto.constraints)
    _check_selector_layouts(builder, squared, lambda bits: (-2 + 3 * bits[0]) ** 2)
