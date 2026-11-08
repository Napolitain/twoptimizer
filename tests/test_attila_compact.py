"""Check the factored income formulation against every small original layout."""

from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.tw.attila.compact import LIMIT, Builder, UnsupportedCompact, Value, checked, common_unit
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


def _income_builder(extras, *, joint_bounds=True):
    names = ("a", "b", "c")
    reference = BinaryModel(
        names=names,
        profit=np.zeros(3),
        matrix=np.empty((0, 3)),
        lower=np.array([]),
        upper=np.array([]),
    )
    economy = SimpleNamespace(
        regions=tuple(SimpleNamespace(name=name) for name in names),
        owner={"a": "one", "b": "one", "c": "two"},
        wealth=lambda region: {(region.name,): 100},
        tax_factor=lambda region: {(): 1},
        corruption=lambda region: {},
        non_tax_income=lambda: extras,
    )
    plan = SimpleNamespace(definitions={}, definition_rows=(), aliases={}, economy=economy)
    return Builder(plan, reference, joint_bounds=joint_bounds)


def test_equal_tax_factors_and_upkeep_do_not_link_separate_provinces():
    builder = _income_builder({("a",): -3, ("b",): -5, ("c",): -7})
    model, _ = builder.build()
    assert model.validate() == ""
    assert builder.income_groups == 2
    names = {variable.name: index for index, variable in enumerate(model.proto.variables)}
    assert "__other_income" not in names
    first = {names[name] for name in ("a", "b", "__wealth_0")}
    second = {names[name] for name in ("c", "__wealth_1")}
    supports = [set(row.linear.vars) for row in model.proto.constraints]
    assert first in supports and second in supports
    assert all(support <= first or support <= second for support in supports)


@pytest.mark.parametrize(
    "extras",
    [
        {},
        {(): Fraction(5, 7)},
        {("a",): Fraction(-7, 2), ("c",): Fraction(11, 3), (): Fraction(-5, 7)},
        {("a", "c"): Fraction(-11, 3), ("b", "c"): Fraction(5, 2)},
    ],
)
@pytest.mark.parametrize("joint_bounds", [False, True])
def test_direct_other_income_preserves_signed_constants_and_cross_province_products(
    extras, joint_bounds
):
    builder = _income_builder(extras, joint_bounds=joint_bounds)
    model, unit = builder.build()
    assert model.validate() == ""
    for bits in product((0, 1), repeat=3):
        pinned = model.clone()
        for index, bit in enumerate(bits):
            pinned.add(pinned.get_int_var_from_proto_index(builder.variables[index].index) == bit)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        assert solver.solve(pinned) == cp_model.OPTIMAL
        values = dict(zip(builder.reference.names, bits, strict=True))
        extra_income = sum(
            coefficient
            for term, coefficient in extras.items()
            if all(values[name] for name in term)
        )
        assert solver.objective_value * float(unit) == pytest.approx(
            float(100 * sum(bits) + extra_income)
        )


def test_small_holdings_retain_the_original_native_formulation():
    builder = _income_builder(
        {(): Fraction(1, 2), ("a",): -3, ("b",): -5, ("c",): -7}, joint_bounds=False
    )
    builder.plan.economy.tax_factor = lambda region: {(): 1, ("b",): Fraction(1, 5)}
    builder.plan.economy.corruption = lambda region: {("c",): Fraction(1, 3)}
    model, unit = builder.build()
    assert model.validate() == ""
    assert unit == Fraction(1, 6)
    # Golden proto generated by the pre-joint-bound Builder in commit 0bbea61.
    # Preserve variables, constraints, order and objective, since an equivalent
    # formulation was measured to slow the small production case substantially.
    assert (
        sha256(str(model.proto).encode()).hexdigest()
        == "3d150c2779245c7f119eb5bb55c41c404cc18322e12fffb6535d356bcbd0a18d"
    )


def test_reference_row_mapping_excludes_product_definitions_created_during_emission():
    builder = _income_builder({})
    reference = BinaryModel(
        names=("a", "b", "c", "ab"),
        profit=np.zeros(4),
        matrix=np.array(
            [
                [1, 0, 0, 0],
                [-1, 0, 0, 1],
                [0, -1, 0, 1],
                [-1, -1, 0, 1],
                [0, 0, 1, 1],
            ]
        ),
        lower=np.array([1, -np.inf, -np.inf, -1, 0]),
        upper=np.array([1, 0, 0, np.inf, 2]),
    )
    builder.plan.definitions = {"ab": ("a", "b")}
    builder.plan.definition_rows = (1, 2, 3)
    builder = Builder(builder.plan, reference)
    model, _ = builder.build()
    assert model.validate() == ""
    assert builder.row_supports == {0: (0,), 4: (2, 3)}
    assert builder.fixed == {0: 1}
    assert builder.variables[0].index == 0
    assert set(builder.row_constraints) == {0, 4}
    mapped = {index for rows in builder.row_constraints.values() for index in rows}
    assert len(mapped) == 4
    assert all(model.proto.constraints[index].has_linear() for index in mapped)
    products = {index for index, row in enumerate(model.proto.constraints) if row.has_int_prod()}
    assert len(products) == 1 and mapped.isdisjoint(products)


def _linear_rows_satisfied(rows, values):
    for row in rows:
        if not all(
            values[literal] if literal >= 0 else 1 - values[-literal - 1]
            for literal in row.enforcement_literal
        ):
            continue
        assert row.has_linear()
        total = sum(
            coefficient * values[index]
            for index, coefficient in zip(row.linear.vars, row.linear.coeffs, strict=True)
        )
        if not row.linear.domain[0] <= total <= row.linear.domain[1]:
            return False
    return True


@pytest.mark.parametrize("bounds", [(-3, -1), (-2, 3), (1, 3), (0, 0)])
@pytest.mark.parametrize("coefficients", [(-3, 2), (-2, -2), (3, 3), (0, 0), (-2,)])
def test_selector_envelopes_preserve_every_signed_integer_assignment(bounds, coefficients):
    builder = _selector_builder()
    lower, upper = bounds
    base = builder.model.new_int_var(lower, upper, "base")
    value = Value(base, Fraction(1), lower, upper)
    group = tuple((index + 2, coefficient) for index, coefficient in enumerate(coefficients))
    target = builder.selector_group(value, group, "target")
    assert builder.model.validate() == ""
    target_bounds = builder.model.proto.variables[target.index].domain
    values = dict.fromkeys(range(len(builder.model.proto.variables)), 0)
    for choices in product((0, 1), repeat=len(group)):
        for (index, _), choice in zip(group, choices, strict=True):
            values[builder.variables[index].index] = choice
        for number in range(lower, upper + 1):
            values[base.index] = number
            expected = number * sum(c * x for c, x in zip(coefficients, choices, strict=True))
            for candidate in range(target_bounds[0], target_bounds[1] + 1):
                values[target.index] = candidate
                assert _linear_rows_satisfied(builder.model.proto.constraints, values) == (
                    sum(choices) <= 1 and candidate == expected
                )


@pytest.mark.parametrize("coefficients, number", [((2, 2), 5), ((-3, -3), 5), ((2, 3), 5)])
def test_selector_hull_cuts_exclude_fractional_points_allowed_by_activity_bounds(
    coefficients, number
):
    builder = _selector_builder()
    base = builder.model.new_int_var(-2, 5, "base")
    group = tuple((index + 2, coefficient) for index, coefficient in enumerate(coefficients))
    before = len(builder.model.proto.constraints)
    target = builder.selector_group(Value(base, Fraction(1), -2, 5), group, "target")
    rows = [
        row
        for index, row in enumerate(builder.model.proto.constraints)
        if index >= before and not row.enforcement_literal
    ]
    values = dict.fromkeys(range(len(builder.model.proto.variables)), Fraction(0))
    values[base.index] = Fraction(number)
    values[builder.variables[2].index] = Fraction(1, 4)
    values[builder.variables[3].index] = Fraction(1, 4)
    values[target.index] = Fraction(0)
    assert _linear_rows_satisfied(rows[:2], values)
    assert not _linear_rows_satisfied(rows, values)
