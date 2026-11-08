"""Small native graphs certify relaxation boundaries without native solving."""

from itertools import product
from types import SimpleNamespace

import pytest
from ortools.sat.python import cp_model

from games.tw.attila.compact import Builder
from games.tw.attila.native_parts import (
    UnsupportedNativeModel,
    extract,
    feasible,
    objective_value,
)
from games.tw.attila.partition import UnsupportedPartition, partition
from games.tw.enums import ProblemState
from games.tw.problem import Problem
from games.tw.region import Region
from tests.support.attila import building, province


def builder(owners=("one", "two"), *, profits=None):
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f"decision_{i}") for i in range(len(owners))]
    names = tuple(variable.name for variable in variables)
    buildings = {
        f"building_{i}": SimpleNamespace(region=SimpleNamespace(name=f"region_{i}"))
        for i in range(len(owners))
    }
    economy = SimpleNamespace(
        by_id=buildings,
        owner={f"region_{i}": owner for i, owner in enumerate(owners)},
        logic={},
    )
    profits = profits if profits is not None else list(range(1, len(owners) + 1))
    model.maximize(
        sum(amount * variable for amount, variable in zip(profits, variables, strict=True))
    )
    return SimpleNamespace(
        model=model,
        reference=SimpleNamespace(names=names, lower=[]),
        indices={name: i for i, name in enumerate(names)},
        variables=dict(enumerate(variables)),
        fixed={},
        products={},
        row_constraints={},
        row_supports={},
        plan=SimpleNamespace(
            economy=economy,
            aliases={f"building_{i}": name for i, name in enumerate(names)},
            definition_rows=frozenset(),
        ),
    )


def reference_row(compiled, supports, constraint):
    original = len(compiled.reference.lower)
    compiled.reference.lower.append(0)
    compiled.row_constraints[original] = (constraint.index,)
    compiled.row_supports[original] = tuple(supports)
    return constraint.index


def auxiliary(compiled, name):
    variable = compiled.model.new_bool_var(name)
    index = len(compiled.reference.names)
    compiled.reference.names = (*compiled.reference.names, name)
    compiled.indices[name] = index
    compiled.variables[index] = variable
    return index, variable


def test_only_original_cross_province_rows_are_relaxed():
    compiled = builder(("one", "one", "two", "two"))
    x, u, y, v = compiled.variables.values()
    local_one = reference_row(compiled, (0, 1), compiled.model.add(x + u <= 1))
    local_two = reference_row(compiled, (2, 3), compiled.model.add(y + v <= 1))
    global_row = reference_row(compiled, (0, 2), compiled.model.add(x + y >= 1))
    result = partition(compiled)
    assert [part.indices for part in result.parts] == [(0, 1), (2, 3)]
    assert [part.rows for part in result.parts] == [(local_one,), (local_two,)]
    assert result.relaxed_rows == (global_row,)
    assert result.relaxed_reference_rows == (2,)
    assert result.fixed == {} and result.constant == 0
    assert len(compiled.model.proto.constraints) == 3


@pytest.mark.parametrize("kind", ["linear", "product", "bool_and", "bool_or", "enforcement"])
def test_economic_and_logical_definitions_keep_cross_province_links(kind):
    compiled = builder()
    x, y = compiled.variables.values()
    reference_row(compiled, (0, 1), compiled.model.add(x + y >= 1))
    z = compiled.model.new_bool_var("derived")
    if kind == "linear":
        compiled.model.add(z == x + y)
    elif kind == "product":
        compiled.model.add_multiplication_equality(z, (x, y))
    elif kind == "bool_and":
        compiled.model.add_bool_and((x, y.Not())).only_enforce_if(z)
    elif kind == "bool_or":
        compiled.model.add_bool_or((x.Not(), y, z))
    else:
        compiled.model.add(z == x).only_enforce_if(y.Not())
    result = partition(compiled)
    assert [part.indices for part in result.parts] == [(0, 1, 2)]
    assert result.parts[0].rows == (1,)


def test_products_use_original_building_aliases_for_ownership():
    compiled = builder()
    x, y = compiled.variables.values()
    product_index, conjunction = auxiliary(compiled, "__and")
    compiled.products[product_index] = (0, 1)
    compiled.model.add_multiplication_equality(conjunction, (x, y))
    source = reference_row(compiled, (product_index,), compiled.model.add(conjunction >= 1))
    result = partition(compiled)
    assert result.relaxed_rows == (source,)
    # The original product definition still connects both province decisions.
    assert result.parts[0].indices == (0, 1, product_index)


def test_logic_ownership_is_expanded_inside_a_reference_product():
    compiled = builder()
    x, y = compiled.variables.values()
    gate_index, gate = auxiliary(compiled, "__gate")
    compiled.plan.economy.logic[gate.name] = SimpleNamespace(expression={("building_1",): 1})
    outer_index, outer = auxiliary(compiled, "__outer")
    compiled.plan.economy.logic[outer.name] = SimpleNamespace(expression={("__gate",): 1})
    product_index, conjunction = auxiliary(compiled, "__and")
    compiled.products[product_index] = (0, outer_index)
    compiled.model.add_multiplication_equality(conjunction, (x, outer))
    reference_row(compiled, (1, gate_index), compiled.model.add(y == gate))
    reference_row(compiled, (gate_index, outer_index), compiled.model.add(gate == outer))
    source = reference_row(compiled, (product_index,), compiled.model.add(conjunction >= 1))
    result = partition(compiled)
    assert result.relaxed_rows == (source,)
    assert result.parts[0].indices == (0, 1, gate_index, outer_index, product_index)


def test_original_indicator_definitions_and_requirements_are_kept():
    compiled = builder()
    x, y = compiled.variables.values()
    gate_index, gate = auxiliary(compiled, "__gate")
    compiled.plan.economy.logic[gate.name] = SimpleNamespace(
        expression={("building_1",): 1, ("building_0",): -1, (): 1}
    )
    outer_index, outer = auxiliary(compiled, "__outer")
    compiled.plan.economy.logic[outer.name] = SimpleNamespace(expression={("__gate",): 1})
    reference_row(compiled, (0, 1, gate_index), compiled.model.add(x + y - gate >= 0))
    reference_row(compiled, (gate_index, outer_index), compiled.model.add(gate == outer))
    reference_row(compiled, (outer_index,), compiled.model.add(outer >= 1))
    result = partition(compiled)
    assert result.relaxed_rows == ()
    assert result.parts[0].indices == (0, 1, gate_index, outer_index)
    assert result.parts[0].rows == (0, 1, 2)


@pytest.mark.parametrize("unknown", ["decision", "logic source", "logic cycle", "owner"])
def test_unknown_or_cyclic_ownership_keeps_original_rows(unknown):
    compiled = builder()
    x, y = compiled.variables.values()
    index, gate = auxiliary(compiled, "__unresolved")
    if unknown == "logic source":
        compiled.plan.economy.logic[gate.name] = SimpleNamespace(expression={("absent",): 1})
    elif unknown == "logic cycle":
        compiled.plan.economy.logic[gate.name] = SimpleNamespace(expression={(gate.name,): 1})
    elif unknown == "owner":
        del compiled.plan.economy.owner["region_1"]
        index, gate = 1, y
    row = reference_row(compiled, (0, 1, index), compiled.model.add(x + y + gate >= 1))
    result = partition(compiled)
    assert result.relaxed_rows == ()
    assert row in result.parts[0].rows
    assert 0 in result.parts[0].indices and 1 in result.parts[0].indices


def test_fixed_variables_do_not_join_parts_and_objective_constant_is_counted_once():
    compiled = builder(("one", "two", "three"), profits=(4, 7, 9))
    x, y, fixed = compiled.variables.values()
    fixed_row = reference_row(compiled, (2,), compiled.model.add(fixed == 1))
    compiled.fixed[2] = 1
    left = reference_row(compiled, (0, 2), compiled.model.add(x + fixed >= 1))
    right = reference_row(compiled, (1, 2), compiled.model.add(y + fixed >= 1))
    constant = compiled.model.new_int_var(2, 2, "constant")
    compiled.model.maximize(4 * x + 7 * y + 9 * fixed + 3 * constant - 5)
    result = partition(compiled)
    assert result.fixed == {2: 1, 3: 2}
    assert result.constant == 10
    assert result.constant_rows == (fixed_row,)
    assert result.relaxed_rows == ()
    assert result.parts[0].rows == (fixed_row, left)
    assert result.parts[1].rows == (right,)
    assert [part.indices for part in result.parts] == [(0,), (1,)]


def test_fixed_only_false_constraint_is_preserved_even_without_free_variables():
    compiled = builder(("one",))
    x = compiled.variables[0]
    compiled.fixed[0] = 1
    row = reference_row(compiled, (0,), compiled.model.add(x == 0))
    result = partition(compiled)
    assert result.parts[0].indices == ()
    assert result.parts[0].rows == (row,)
    part_model, indices = extract(compiled.model, (), (row,), result.fixed, {})
    assert indices == (0,)
    assert not feasible(part_model, {0: 1})


def test_unconstrained_zero_profit_decisions_remain_in_the_partition():
    compiled = builder(("one", "two", "three"), profits=(5, 0, -3))
    result = partition(compiled)
    assert [part.indices for part in result.parts] == [(0,), (1,), (2,)]
    assert all(part.rows == () for part in result.parts)


def test_every_original_assignment_projects_to_parts_with_the_same_objective():
    compiled = builder(("one", "one", "two", "two"), profits=(4, -3, 7, 2))
    x, u, y, v = compiled.variables.values()
    reference_row(compiled, (0, 1), compiled.model.add(x + u <= 1))
    reference_row(compiled, (2, 3), compiled.model.add(y + v <= 1))
    reference_row(compiled, (0, 2), compiled.model.add(x + y >= 1))
    result = partition(compiled)
    coefficients = {0: 4, 1: -3, 2: 7, 3: 2}
    originals = []
    relaxed = []
    for bits in product((0, 1), repeat=4):
        values = dict(enumerate(bits))
        total = result.constant
        valid = True
        for part in result.parts:
            native, indices = extract(
                compiled.model,
                part.indices,
                part.rows,
                result.fixed,
                {index: coefficients[index] for index in part.indices},
            )
            local = {i: values[original] for i, original in enumerate(indices)}
            valid = valid and feasible(native, local)
            total += objective_value(native, local)
        if feasible(compiled.model, values):
            assert valid
            assert total == objective_value(compiled.model, values)
            originals.append(total)
        if valid:
            relaxed.append(total)
    assert max(relaxed) >= max(originals)


@pytest.mark.parametrize("economic_cross_link", [False, True])
def test_real_builder_partitions_order_but_retains_factionwide_economic_products(
    context, economic_cross_link
):
    regions = [Region(name, context=context) for name in ("a", "b")]
    problem = Problem(objective="income", context=context)
    for name, region in zip(("one", "two"), regions, strict=True):
        problem.add_province(province(name, region))
    effects = [("public_order_politics", "faction_to_province_own", 1)]
    if economic_cross_link:
        effects.append(("economy_gdp_mod_industry", "faction_to_region_own", 25))
    candidates = [
        building(regions[0], "governor", *effects, upkeep=2),
        building(regions[0], "producer", ("economy_gdp_industry", "building_to_building_own", 10)),
        building(
            regions[1],
            "factory",
            ("economy_gdp_industry", "building_to_building_own", 20),
            ("public_order_base", "province_to_province_own", -1),
            upkeep=1,
        ),
    ]
    for candidate in candidates:
        candidate.lp_variable = problem.problem.solver.BoolVar(candidate.get_name())
    problem.problem.solver.Add(candidates[0].lp_variable + candidates[1].lp_variable <= 1)
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    reference = problem.problem.binary_model()
    compiled = Builder(reference.cp_sat_plan, reference)
    compiled.build()
    result = partition(compiled)
    assert len(result.relaxed_reference_rows) == 1
    assert len(result.parts) == (1 if economic_cross_link else 2)


@pytest.mark.parametrize("problem", ["unknown index", "reused row", "definition", "wrong support"])
def test_malformed_reference_row_metadata_is_rejected(problem):
    compiled = builder()
    x, y = compiled.variables.values()
    row = reference_row(compiled, (0, 1), compiled.model.add(x + y >= 1))
    if problem == "unknown index":
        compiled.row_supports[0] = (0, 99)
    elif problem == "reused row":
        compiled.reference.lower.append(0)
        compiled.row_constraints[1] = (row,)
        compiled.row_supports[1] = (0, 1)
    elif problem == "definition":
        compiled.plan.definition_rows = frozenset((0,))
    else:
        compiled.row_supports[0] = (0,)
    with pytest.raises(UnsupportedPartition):
        partition(compiled)


@pytest.mark.parametrize(
    "problem", ["unsupported row", "unknown native", "empty domain", "bad fixed"]
)
def test_malformed_or_unsupported_native_models_fail_closed(problem):
    compiled = builder()
    x, y = compiled.variables.values()
    if problem == "unsupported row":
        compiled.model.add_all_different((x, y))
    elif problem == "unknown native":
        row = compiled.model.add(x + y >= 1)
        row.proto.linear.vars.append(99)
        row.proto.linear.coeffs.append(1)
    elif problem == "empty domain":
        compiled.model.proto.variables[0].domain.clear()
    else:
        compiled.fixed[0] = 2
    with pytest.raises((UnsupportedPartition, UnsupportedNativeModel)):
        partition(compiled)
