"""Exhaustive integer assignments validate partitioning without a native solve."""

from itertools import product
from math import inf

import pytest
from hypothesis import given
from hypothesis import strategies as st
from ortools.linear_solver import linear_solver_pb2

from games.optimization.linear_components import (
    SAFE_INTEGER,
    InfeasibleRelaxation,
    UnsupportedDecomposition,
    decompose,
    objective_upper_bound,
)


def model(profits, domains=None, *, offset=0, maximize=True):
    proto = linear_solver_pb2.MPModelProto(maximize=maximize, objective_offset=offset)
    for index, coefficient in enumerate(profits):
        lower, upper = (0, 1) if domains is None else domains[index]
        proto.variable.add(
            name=f"v{index}",
            lower_bound=lower,
            upper_bound=upper,
            objective_coefficient=coefficient,
            is_integer=True,
        )
    return proto


def row(proto, coefficients, lower=-inf, upper=inf, *, name=""):
    constraint = proto.constraint.add(lower_bound=lower, upper_bound=upper, name=name)
    for index, amount in coefficients:
        constraint.var_index.append(index)
        constraint.coefficient.append(amount)
    return constraint


def satisfies(proto, values, *, ignored=()):
    return all(
        variable.lower_bound <= value <= variable.upper_bound
        for variable, value in zip(proto.variable, values, strict=True)
    ) and all(
        constraint.lower_bound
        <= sum(
            amount * values[index]
            for index, amount in zip(constraint.var_index, constraint.coefficient, strict=True)
        )
        <= constraint.upper_bound
        for number, constraint in enumerate(proto.constraint)
        if number not in ignored
    )


def objective(proto, values):
    return proto.objective_offset + sum(
        variable.objective_coefficient * value
        for variable, value in zip(proto.variable, values, strict=True)
    )


def test_only_explicit_food_row_is_relaxed_and_every_other_cross_link_remains():
    proto = model([10, 0, 20, 0, 0, 0])
    row(proto, [(0, 1), (1, 1)], upper=1)
    row(proto, [(2, 1), (3, 1)], upper=1)
    row(proto, [(0, 1), (4, 1)], lower=1, name="global requirement")
    food = len(proto.constraint)
    row(proto, [(0, -2), (2, -3), (5, 8)], lower=0, name="food")
    partition = decompose(proto, relaxed_rows=(food,))
    assert [part.indices for part in partition.parts] == [(0, 1, 4), (2, 3), (5,)]
    assert partition.fixed == {} and partition.constant == 0
    assert partition.parts[-1].proto.variable[0].objective_coefficient == 0
    assert partition.parts[-1].proto.constraint == []
    assert [part.indices for part in decompose(proto).parts] == [(0, 1, 2, 3, 4, 5)]
    assert all(part.proto.objective_offset == 0 for part in partition.parts)


@pytest.mark.parametrize("fixed_party", [False, True])
def test_shared_party_is_kept_once_and_only_proved_fixed_choices_are_substituted(fixed_party):
    proto = model([10, 20, 7])
    row(proto, [(0, 1), (2, 1)], lower=1)
    row(proto, [(1, 1), (2, 1)], lower=1)
    if fixed_party:
        row(proto, [(2, 1)], lower=1, upper=1)
    partition = decompose(proto)
    if fixed_party:
        assert partition.fixed == {2: 1} and partition.constant == 7
        assert [part.indices for part in partition.parts] == [(0,), (1,)]
    else:
        assert partition.fixed == {} and partition.constant == 0
        assert [part.indices for part in partition.parts] == [(0, 1, 2)]


def test_fixed_objective_offset_and_signed_singleton_cascade_are_exact():
    proto = model([4, -3, 2], [(1, 1), (-3, 3), (-4, 4)], offset=-8)
    row(proto, [(0, 2), (1, -3)], lower=-4, upper=-4)
    row(proto, [(1, 1), (2, 2)], lower=-2, upper=-2)
    partition = decompose(proto)
    assert partition.fixed == {0: 1, 1: 2, 2: -2}
    assert partition.constant == -14 and partition.parts == ()


@pytest.mark.parametrize(
    "coefficient, lower, upper, expected",
    [
        (2, -5, -1, (-2, -1)),
        (-2, 1, 5, (-2, -1)),
        (3, 4, inf, (2, 5)),
        (-3, -inf, -4, (2, 5)),
        (2, -inf, -3, (-5, -2)),
        (-2, 3, inf, (-5, -2)),
    ],
)
def test_signed_singleton_inequalities_use_integer_ceil_and_floor(
    coefficient, lower, upper, expected
):
    proto = model([1], [(-5, 5)])
    row(proto, [(0, coefficient)], lower, upper)
    partition = decompose(proto)
    variable = partition.parts[0].proto.variable[0]
    assert (variable.lower_bound, variable.upper_bound) == expected
    assert partition.parts[0].proto.constraint[0].coefficient == [coefficient]


def test_zero_and_duplicate_coefficients_do_not_create_false_connections():
    proto = model([3, -2, 0], offset=5, maximize=False)
    row(proto, [(0, 1), (1, 2), (1, -2), (2, 0)], upper=1, name="duplicates")
    partition = decompose(proto)
    assert [part.indices for part in partition.parts] == [(0,), (1,), (2,)]
    assert all(not part.proto.maximize for part in partition.parts)
    assert partition.parts[0].proto.constraint[0].coefficient == [1]
    assert partition.parts[0].proto.constraint[0].name == "duplicates"
    assert partition.constant == 5


def test_domain_bound_is_valid_without_a_solver_and_recomputes_repriced_coefficients():
    proto = model([-4, 2, 0], [(-3, -1), (-2, 3), (0, 10)], offset=-10)
    assert objective_upper_bound(proto) == 8
    partition = decompose(proto)
    assert partition.constant + sum(objective_upper_bound(p.proto) for p in partition.parts) == 8
    partition.parts[0].proto.variable[0].objective_coefficient = 5
    assert objective_upper_bound(partition.parts[0].proto) == -5
    assert proto.variable[0].objective_coefficient == -4


@pytest.mark.parametrize("kind", ["domain", "constant", "fractional", "after substitution"])
def test_proved_infeasibility_is_distinct_from_unsupported_input(kind):
    proto = model([1], [(0, 2)])
    if kind == "domain":
        proto.variable[0].lower_bound = 3
    elif kind == "constant":
        row(proto, [], lower=1)
    elif kind == "fractional":
        row(proto, [(0, 2)], lower=3, upper=3)
    else:
        row(proto, [(0, 1)], lower=1, upper=1)
        row(proto, [(0, 1)], lower=2)
    with pytest.raises(InfeasibleRelaxation):
        decompose(proto)


def test_relaxing_a_contradictory_food_row_does_not_claim_the_original_is_feasible():
    proto = model([1], [(0, 0)])
    row(proto, [(0, 1)], lower=1)
    relaxed = decompose(proto, relaxed_rows=(0,))
    assert relaxed.parts == () and relaxed.fixed == {0: 0}
    assert not satisfies(proto, [0])


@pytest.mark.parametrize(
    "field, value",
    [
        ("lower_bound", 0.5),
        ("upper_bound", inf),
        ("objective_coefficient", 0.5),
        ("objective_coefficient", SAFE_INTEGER),
        ("is_integer", False),
    ],
)
def test_unsupported_variable_domains_or_objectives_are_rejected(field, value):
    proto = model([1])
    setattr(proto.variable[0], field, value)
    with pytest.raises(UnsupportedDecomposition):
        decompose(proto)


@pytest.mark.parametrize("kind", ["quadratic", "general", "bad index", "length", "nan", "fraction"])
def test_generalized_or_malformed_constraints_are_never_silently_discarded(kind):
    proto = model([1])
    constraint = row(proto, [(0, 1)], lower=0)
    if kind == "quadratic":
        proto.quadratic_objective.SetInParent()
    elif kind == "general":
        proto.general_constraint.add()
    elif kind == "bad index":
        constraint.var_index[0] = 2
    elif kind == "length":
        constraint.coefficient.append(1)
    elif kind == "nan":
        constraint.lower_bound = float("nan")
    else:
        constraint.coefficient[0] = 0.5
    with pytest.raises(UnsupportedDecomposition):
        decompose(proto, relaxed_rows=(0,))


@pytest.mark.parametrize("kind", ["objective", "constraint", "shifted bound"])
def test_unsafe_derived_integer_activity_is_rejected_before_float_serialization(kind):
    proto = model([1], [(0, 4)])
    if kind == "objective":
        proto.variable[0].objective_coefficient = 2**52
    elif kind == "constraint":
        row(proto, [(0, 2**52)], upper=1)
    else:
        proto.variable[0].lower_bound = 4
        row(proto, [(0, -1)], upper=SAFE_INTEGER - 1)
    with pytest.raises(UnsupportedDecomposition):
        decompose(proto)


@pytest.mark.parametrize("relaxed", [(-1,), (1,), (True,), (0.0,)])
def test_relaxation_must_explicitly_name_existing_integer_row_indices(relaxed):
    proto = model([1])
    row(proto, [(0, 1)], upper=1)
    with pytest.raises(UnsupportedDecomposition):
        decompose(proto, relaxed_rows=relaxed)


@given(
    profits=st.lists(st.integers(-5, 5), min_size=4, max_size=4),
    offset=st.integers(-10, 10),
    constraints=st.lists(
        st.tuples(st.lists(st.integers(-2, 2), min_size=4, max_size=4), st.integers(-4, 4)),
        max_size=5,
    ),
)
def test_every_relaxed_integer_assignment_preserves_feasibility_and_objective(
    profits, offset, constraints
):
    proto = model(profits, [(0, 2)] * 4, offset=offset)
    for coefficients, bound in constraints:
        row(proto, list(enumerate(coefficients)), upper=bound)
    relaxed = (0,) if constraints else ()
    original = proto.SerializeToString()
    assignments = list(product(range(3), repeat=4))
    try:
        partition = decompose(proto, relaxed_rows=relaxed)
    except InfeasibleRelaxation:
        assert not any(satisfies(proto, values, ignored=relaxed) for values in assignments)
        return
    assert proto.SerializeToString() == original
    coverage = [index for part in partition.parts for index in part.indices] + list(partition.fixed)
    assert sorted(coverage) == list(range(4))
    for values in assignments:
        local_values = [tuple(values[index] for index in part.indices) for part in partition.parts]
        reduced = all(values[index] == value for index, value in partition.fixed.items()) and all(
            satisfies(part.proto, local)
            for part, local in zip(partition.parts, local_values, strict=True)
        )
        assert reduced == satisfies(proto, values, ignored=relaxed)
        if reduced:
            assert objective(proto, values) == partition.constant + sum(
                objective(part.proto, local)
                for part, local in zip(partition.parts, local_values, strict=True)
            )
            assert objective(proto, values) <= partition.constant + sum(
                objective_upper_bound(part.proto) for part in partition.parts
            )
