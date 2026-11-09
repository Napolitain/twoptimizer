"""Exact compact-model extraction, objective scaling and constraint evaluation."""

from itertools import product
from typing import cast

import pytest
from ortools.sat.python import cp_model

from games.optimization.native_model import (
    SAFE_INTEGER,
    UnsupportedNativeModel,
    constraint_variables,
    extract,
    feasible,
    objective_terms,
    objective_upper_bound,
    objective_value,
)


def compact_example(anchor_value=0):
    model = cp_model.CpModel()
    unrelated = model.new_bool_var("unrelated")
    choice = model.new_bool_var("choice")
    anchor = model.new_bool_var("fixed_anchor")
    amount = model.new_int_var_from_domain(cp_model.Domain.from_values([-2, 0, 3]), "amount")
    multiplied = model.new_int_var(-15, 15, "product")
    model.add(anchor == anchor_value)
    model.add(2 * choice + amount >= -1).only_enforce_if(~anchor)
    model.add_multiplication_equality(multiplied, [~choice, amount + 2])
    model.add_bool_or([~choice, ~anchor])
    model.add_bool_and([~choice]).only_enforce_if(anchor)
    model.maximize(7 + 11 * anchor + 3 * choice - 2 * amount + 100 * unrelated)
    return model


@pytest.mark.parametrize("anchor", [0, 1])
def test_extraction_preserves_every_supported_constraint_and_negated_literal(anchor):
    model = compact_example(anchor)
    before = str(model.proto)
    coefficients, offset = objective_terms(model)
    assert coefficients == {0: 100, 1: 3, 2: 11, 3: -2} and offset == 7
    submodel, indices = extract(model, (4, 3, 1), range(5), {2: anchor}, coefficients)
    assert indices == (1, 2, 3, 4)
    assert submodel.validate() == ""
    assert objective_terms(submodel) == ({0: 3, 2: -2}, 0)
    assert objective_upper_bound(submodel) == 7
    assert list(submodel.proto.constraints[3].bool_or.literals) == [-1, -2]
    assert list(submodel.proto.constraints[1].enforcement_literal) == [-2]
    accepted = []
    for choice, amount, multiplied in product((0, 1), (-2, 0, 3), range(-15, 16)):
        original = {0: 0, 1: choice, 2: anchor, 3: amount, 4: multiplied}
        local = {0: choice, 1: anchor, 2: amount, 3: multiplied}
        expected = (
            (anchor == 1 or 2 * choice + amount >= -1)
            and multiplied == (1 - choice) * (amount + 2)
            and (choice == 0 or anchor == 0)
            and (anchor == 0 or choice == 0)
        )
        assert feasible(submodel, local) is expected
        assert feasible(model, original) is expected
        assert objective_value(submodel, local) == 3 * choice - 2 * amount
        assert objective_value(model, original) == 7 + 11 * anchor + 3 * choice - 2 * amount
        if expected:
            accepted.append(objective_value(submodel, local))
    assert accepted
    assert str(model.proto) == before


def test_native_extracted_optimum_matches_exhaustive_component_economics():
    model = compact_example()
    submodel, _ = extract(model, (1, 3, 4), range(5), {2: 0}, objective_terms(model)[0])
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.solve(submodel) == cp_model.OPTIMAL
    values = {
        index: solver.value(submodel.get_int_var_from_proto_index(index))
        for index in range(len(submodel.proto.variables))
    }
    assert feasible(submodel, values)
    assert objective_value(submodel, values) == solver.objective_value == 7


def test_all_row_support_includes_fixed_variables_and_enforcement():
    model = compact_example()
    assert constraint_variables(model.proto.constraints[1], 5) == {1, 2, 3}
    assert constraint_variables(model.proto.constraints[2], 5) == {1, 3, 4}
    assert constraint_variables(model.proto.constraints[3], 5) == {1, 2}
    assert constraint_variables(model.proto.constraints[4], 5) == {1, 2}


def test_missing_nonfixed_support_fails_instead_of_relaxing_a_kept_constraint():
    model = compact_example()
    with pytest.raises(UnsupportedNativeModel, match="omitted nonfixed"):
        extract(model, (1,), (2,), {2: 0}, objective_terms(model)[0])


@pytest.mark.parametrize("fixed", [{2: 2}, {2: 0.5}, {2: True}, {5: 0}, {-1: 0}])
def test_invalid_fixed_values_and_references_are_rejected(fixed):
    model = compact_example()
    with pytest.raises(UnsupportedNativeModel):
        extract(model, (1, 3, 4), range(5), fixed, objective_terms(model)[0])


@pytest.mark.parametrize("where", ["linear", "product", "objective"])
def test_negative_numeric_references_are_not_treated_as_boolean_negation(where):
    model = compact_example()
    if where == "linear":
        model.proto.constraints[1].linear.vars[0] = -1
    elif where == "product":
        model.proto.constraints[2].int_prod.exprs[0].vars[0] = -1
    else:
        model.proto.objective.vars[0] = -1
    with pytest.raises(UnsupportedNativeModel, match="numeric variable reference"):
        feasible(model, {0: 0, 1: 1, 2: 0, 3: 0, 4: 0})


def test_nonboolean_enforcement_domain_is_rejected_even_when_inactive():
    model = compact_example()
    model.proto.variables[2].domain[1] = 2
    with pytest.raises(UnsupportedNativeModel, match="non-Boolean"):
        feasible(model, {0: 0, 1: 1, 2: 0, 3: 0, 4: 0})


def test_unknown_constraint_types_fail_closed_even_when_inactive():
    model = cp_model.CpModel()
    x, y = model.new_bool_var("x"), model.new_bool_var("y")
    model.add_exactly_one(x, y).only_enforce_if(x)
    model.maximize(x + y)
    with pytest.raises(UnsupportedNativeModel, match="constraint type"):
        feasible(model, {0: 0, 1: 0})
    with pytest.raises(UnsupportedNativeModel, match="constraint type"):
        extract(model, (0, 1), (0,), {}, {0: 1, 1: 1})


@pytest.mark.parametrize("constant", [-7, 0, 7])
def test_constant_maximize_objective_uses_positive_scaling_but_remains_exact(constant):
    model = cp_model.CpModel()
    model.maximize(constant)
    assert objective_terms(model) == ({}, constant)
    assert objective_upper_bound(model) == objective_value(model, {}) == constant


def test_maximizing_a_negated_boolean_preserves_its_offset():
    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    model.maximize(~x)
    assert objective_terms(model) == ({0: -1}, 1)
    assert objective_value(model, {0: 0}) == objective_upper_bound(model) == 1
    assert objective_value(model, {0: 1}) == 0


@pytest.mark.parametrize("kind", ["minimize", "float", "scale", "offset", "objective_domain"])
def test_unsupported_objective_shapes_and_scaling_fail_closed(kind):
    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    model.maximize(x)
    if kind == "minimize":
        model.minimize(x)
    elif kind == "float":
        model.maximize(0.5 * x)
    elif kind == "scale":
        model.proto.objective.scaling_factor = -0.5
    elif kind == "offset":
        model.proto.objective.offset = 0.5
    else:
        model.proto.objective.domain.extend((-1, 0))
    with pytest.raises(UnsupportedNativeModel):
        objective_terms(model)


def test_unsafe_native_objective_activity_is_rejected_before_bound_or_extraction():
    model = cp_model.CpModel()
    x = model.new_int_var(0, 2, "x")
    model.maximize((SAFE_INTEGER // 2) * x)
    with pytest.raises(UnsupportedNativeModel, match="activity"):
        objective_upper_bound(model)
    with pytest.raises(UnsupportedNativeModel, match="activity"):
        extract(model, (0,), (), {}, {0: SAFE_INTEGER // 2})


def test_domain_holes_and_assignment_completeness_are_enforced():
    model = cp_model.CpModel()
    x = model.new_int_var_from_domain(cp_model.Domain.from_values([-2, 0, 3]), "x")
    model.maximize(-3 * x + 1)
    assert feasible(model, {0: -2})
    assert objective_upper_bound(model) == 7
    for values in ({0: 1}, {}, {0: 0, 1: 0}, {0: 0.0}, {0: False}):
        invalid = cast(dict[int, int], values)
        assert not feasible(model, invalid)
        with pytest.raises(ValueError, match="complete integer assignment"):
            objective_value(model, invalid)


def test_linear_domain_holes_and_empty_boolean_rows_are_evaluated_exactly():
    model = cp_model.CpModel()
    x = model.new_int_var(0, 2, "x")
    model.add_linear_expression_in_domain(x, cp_model.Domain.from_values([0, 2]))
    model.add_bool_and([])
    model.maximize(x)
    assert feasible(model, {0: 0}) and feasible(model, {0: 2})
    assert not feasible(model, {0: 1})
    model.add_bool_or([])
    assert not feasible(model, {0: 0})


def test_assumptions_cannot_be_silently_dropped_from_extracted_models():
    model = cp_model.CpModel()
    x = model.new_bool_var("x")
    model.maximize(x)
    model.add_assumption(x)
    with pytest.raises(UnsupportedNativeModel, match="assumptions"):
        extract(model, (0,), (), {}, {0: 1})
