"""Exhaustive arithmetic checks for necessary cross-province row projections."""

from itertools import product

import pytest
from ortools.sat.python import cp_model

from games.tw.attila.native_parts import SAFE_INTEGER, UnsupportedNativeModel, extract, feasible
from games.tw.attila.projection import ProjectionRows, project


def local_model(original, indices, fixed=None):
    return extract(original, indices, (), fixed or {}, {index: 1 for index in indices})


def test_public_order_projection_preserves_maximum_possible_external_bonus():
    original = cp_model.CpModel()
    bonus = original.new_int_var(0, 2, "external_bonus")
    cost = original.new_int_var(0, 10, "local_order_cost")
    row = original.add(-cost + 2 * bonus >= 0).index
    original.maximize(cost)
    model, indices = local_model(original, (cost.index,))
    before = str(original.proto)
    assert project(original, model, indices, (cost.index,), {}, (row,)) == 1
    assert [value for value in range(11) if feasible(model, {0: value})] == list(range(5))
    for amount, external in product(range(11), range(3)):
        if feasible(original, {cost.index: amount, bonus.index: external}):
            assert feasible(model, {0: amount})
    assert str(original.proto) == before


@pytest.mark.parametrize("lower,upper", [(-3, 8), (None, 4), (2, None)])
@pytest.mark.parametrize("local_coefficient,external_coefficient", [(2, -3), (-2, 3), (-2, -3)])
def test_all_original_assignments_survive_signed_two_sided_projection(
    lower, upper, local_coefficient, external_coefficient
):
    original = cp_model.CpModel()
    local = original.new_int_var(-2, 3, "local")
    external = original.new_int_var_from_domain(
        cp_model.Domain.from_intervals([[-3, -1], [2, 4]]), "external"
    )
    fixed = original.new_int_var(-2, 2, "fixed")
    row = original.add_linear_constraint(
        local_coefficient * local + external_coefficient * external + 5 * fixed,
        cp_model.INT_MIN if lower is None else lower,
        cp_model.INT_MAX if upper is None else upper,
    ).index
    original.add(fixed == 1)
    original.maximize(local)
    model, indices = local_model(original, (local.index,), {fixed.index: 1})
    project(original, model, indices, (local.index,), {fixed.index: 1}, (row,))
    for own, other in product(range(-2, 4), (-3, -2, -1, 2, 3, 4)):
        if feasible(original, {local.index: own, external.index: other, fixed.index: 1}):
            assert feasible(model, {0: own})


def test_fixed_external_value_is_used_instead_of_its_unrestricted_domain():
    original = cp_model.CpModel()
    local = original.new_int_var(0, 10, "local")
    fixed = original.new_int_var(0, 10, "fixed")
    row = original.add(local + fixed <= 5).index
    original.add(fixed == 2)
    original.maximize(local)
    model, indices = local_model(original, (local.index,), {fixed.index: 2})
    assert project(original, model, indices, (local.index,), {fixed.index: 2}, (row,)) == 1
    assert [own for own in range(11) if feasible(model, {0: own})] == [0, 1, 2, 3]


def test_two_tight_sides_are_added_once_and_duplicate_rows_are_ignored():
    original = cp_model.CpModel()
    local = original.new_int_var(0, 10, "local")
    external = original.new_int_var(0, 0, "external")
    row = original.add_linear_constraint(2 * local + external, 4, 12).index
    original.maximize(local)
    model, indices = local_model(original, (local.index,), {external.index: 0})
    assert project(original, model, indices, (local.index,), {external.index: 0}, (row, row)) == 1
    assert [own for own in range(11) if feasible(model, {0: own})] == [2, 3, 4, 5, 6]


def test_domain_implied_and_unrelated_rows_add_no_redundant_constraints():
    original = cp_model.CpModel()
    local = original.new_int_var(0, 10, "local")
    external = original.new_int_var(0, 10, "external")
    rows = (original.add(local + external >= 0).index, original.add(external >= 0).index)
    original.maximize(local)
    model, indices = local_model(original, (local.index,))
    before = str(model.proto)
    assert ProjectionRows(original, {}, rows).apply(model, indices, (local.index,)) == 0
    assert str(model.proto) == before


def test_globally_impossible_domain_projection_marks_component_infeasible():
    original = cp_model.CpModel()
    local = original.new_int_var(0, 2, "local")
    external = original.new_int_var(0, 2, "external")
    row = original.add(local + external >= 10).index
    original.maximize(local)
    model, indices = local_model(original, (local.index,))
    assert project(original, model, indices, (local.index,), {}, (row,)) == 1
    assert not any(feasible(model, {0: value}) for value in range(3))


def test_large_integer_external_extrema_are_never_rounded_through_float():
    original = cp_model.CpModel()
    local = original.new_int_var(0, 2**56, "local")
    external = original.new_int_var(0, 2**56, "external")
    row = original.add(local + external >= 2**56 + 1).index
    original.maximize(local)
    model, indices = local_model(original, (local.index,))
    assert project(original, model, indices, (local.index,), {}, (row,)) == 1
    assert not feasible(model, {0: 0})
    assert feasible(model, {0: 1})


@pytest.mark.parametrize("kind", ["reified", "product", "holes", "unsafe_activity"])
def test_unsupported_projection_rows_fail_before_modifying_component(kind):
    original = cp_model.CpModel()
    local = original.new_int_var(0, 2, "local")
    external = original.new_int_var(0, 2, "external")
    valid = original.add(local + external <= 1).index
    if kind == "reified":
        flag = original.new_bool_var("flag")
        rejected = original.add(local + external >= 1).only_enforce_if(flag).index
    elif kind == "product":
        rejected = original.add_multiplication_equality(local, [external, external]).index
    elif kind == "holes":
        rejected = original.add(local + external >= 0).index
        domain = original.proto.constraints[rejected].linear.domain
        domain.clear()
        domain.extend((0, 1, 3, 4))
    else:
        rejected = original.add((SAFE_INTEGER // 2) * local + external >= 0).index
    original.maximize(local)
    model, indices = local_model(original, (local.index,))
    before = str(model.proto)
    with pytest.raises(UnsupportedNativeModel):
        project(original, model, indices, (local.index,), {}, (valid, rejected))
    assert str(model.proto) == before


@pytest.mark.parametrize("value", [-1, 3, True])
def test_unproved_out_of_domain_fixed_values_are_rejected(value):
    original = cp_model.CpModel()
    local = original.new_int_var(0, 2, "local")
    external = original.new_int_var(0, 2, "external")
    row = original.add(local + external <= 1).index
    original.maximize(local)
    model, indices = local_model(original, (local.index,))
    with pytest.raises(UnsupportedNativeModel, match="fixed value"):
        project(original, model, indices, (local.index,), {external.index: value}, (row,))
