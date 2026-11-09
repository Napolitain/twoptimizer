"""Shared mechanisms preserve exact models without depending on game rules."""

from math import inf, nan
from pathlib import Path

import pytest
from ortools.linear_solver import linear_solver_pb2

import games.optimization
from games.optimization.budget import Budget
from games.optimization.cp_backend import NativeCP
from games.optimization.exact import integer_upper_bound
from tests.support.imports import imports


def test_core_cannot_import_game_or_application_policy():
    root = Path(games.optimization.__file__).parent
    dependencies = [(path.name, name) for path in root.rglob("*.py") for name in imports(path)]
    forbidden = [
        (path, name)
        for path, name in dependencies
        if name == "twoptimizer"
        or name.startswith("twoptimizer.")
        or (
            (name == "games" or name.startswith("games."))
            and not (name == "games.optimization" or name.startswith("games.optimization."))
        )
    ]
    assert forbidden == []


def test_budget_uses_one_shared_clock_and_never_grants_time_after_expiry():
    now = [10.0]
    budget = Budget(2.5, clock=lambda: now[0])
    now[0] = 11.0
    assert budget.elapsed == 1.0
    assert budget.remaining == 1.5
    now[0] = 14.0
    assert budget.elapsed == 4.0
    assert budget.remaining == 0.0


@pytest.mark.parametrize("seconds", [-1, inf, -inf, nan])
def test_budget_rejects_invalid_allowance_before_reading_clock(seconds):
    def unexpected():
        pytest.fail("Invalid allowance must not start its clock")

    with pytest.raises(ValueError, match="nonnegative and finite"):
        Budget(seconds, clock=unexpected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (3.1, 4),
        (-3.1, -3),
        (0, 0),
        (2**53 - 1, 2**53 - 1),
        (2**53, None),
        (-(2**53), None),
        (inf, None),
        (nan, None),
    ],
)
def test_integer_certificate_rounding_is_outward_and_respects_double_range(value, expected):
    assert integer_upper_bound(value) == expected


def _linear_model(*, maximize=True):
    proto = linear_solver_pb2.MPModelProto(maximize=maximize, objective_offset=7)
    proto.variable.add(
        name="first", lower_bound=-2, upper_bound=5, is_integer=True, objective_coefficient=3
    )
    proto.variable.add(
        name="second", lower_bound=0, upper_bound=1, is_integer=True, objective_coefficient=-4
    )
    proto.constraint.add(lower_bound=-inf, upper_bound=3, var_index=[0, 1], coefficient=[1, 2])
    return proto


@pytest.mark.parametrize("maximize", [False, True])
def test_linear_import_preserves_variable_indices_domains_and_objective_direction(maximize):
    source = _linear_model(maximize=maximize)
    before = source.SerializeToString()
    compiled = NativeCP.from_linear(source)
    assert source.SerializeToString() == before
    assert compiled.model.validate() == ""
    assert [variable.index for variable in compiled.variables] == [0, 1]
    assert [variable.name for variable in compiled.model.proto.variables] == ["first", "second"]
    assert [list(variable.domain) for variable in compiled.model.proto.variables] == [
        [-2, 5],
        [0, 1],
    ]
    objective = compiled.model.proto.objective
    scale = -1 if maximize else 1
    assert objective.scaling_factor == scale
    assert objective.offset == scale * 7
    assert dict(zip(objective.vars, objective.coeffs, strict=True)) == {0: scale * 3, 1: scale * -4}


@pytest.mark.parametrize("invalid", ["continuous", "fraction", "unbounded", "nonlinear"])
def test_linear_import_refuses_unsupported_or_inexact_models(invalid):
    proto = _linear_model()
    if invalid == "continuous":
        proto.variable[0].is_integer = False
    elif invalid == "fraction":
        proto.constraint[0].coefficient[0] = 0.5
    elif invalid == "unbounded":
        proto.variable[0].upper_bound = inf
    else:
        proto.general_constraint.add(name="unsupported")
    with pytest.raises(ValueError):
        NativeCP.from_linear(proto)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lower_bound", nan),
        ("upper_bound", nan),
        ("lower_bound", inf),
        ("upper_bound", -inf),
        ("lower_bound", 4),
    ],
)
def test_linear_import_does_not_silently_drop_invalid_bounds(field, value):
    proto = _linear_model()
    setattr(proto.constraint[0], field, value)
    with pytest.raises(ValueError, match="Constraint"):
        NativeCP.from_linear(proto)


@pytest.mark.parametrize("index", [-1, 2])
def test_linear_import_rejects_unknown_and_negative_variable_references(index):
    proto = _linear_model()
    proto.constraint[0].var_index[0] = index
    with pytest.raises(ValueError, match="unknown variable"):
        NativeCP.from_linear(proto)
