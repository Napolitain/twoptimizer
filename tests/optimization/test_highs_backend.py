"""Native HiGHS proofs, bounds, integer validation and repeated CPU settings."""

import json
import math
import subprocess
import sys
from types import SimpleNamespace

import pytest
from ortools.linear_solver import linear_solver_pb2
from ortools.math_opt.python import mathopt
from ortools.sat.python import cp_model

from games.optimization import highs_backend


def model(*, maximize=True, offset=0):
    return linear_solver_pb2.MPModelProto(maximize=maximize, objective_offset=offset)


def variable(proto, name, lower, upper, cost, *, integer=True):
    proto.variable.add(
        name=name,
        lower_bound=lower,
        upper_bound=upper,
        objective_coefficient=cost,
        is_integer=integer,
    )


def row(proto, indices, coefficients, lower=-math.inf, upper=math.inf):
    proto.constraint.add(
        var_index=indices, coefficient=coefficients, lower_bound=lower, upper_bound=upper
    )


def binary_model():
    proto = model(offset=0.125)
    variable(proto, "x", 0, 1, 0.2)
    variable(proto, "y", 0, 1, 0.35)
    row(proto, [0, 1], [1, 1], upper=1)
    return proto


def test_binary_decimal_income_matches_cpsat_and_keeps_offset():
    result = highs_backend.solve_highs(binary_model(), workers=1)
    cp = cp_model.CpModel()
    x, y = cp.new_bool_var("x"), cp.new_bool_var("y")
    cp.add(x + y <= 1)
    cp.maximize(20 * x + 35 * y)
    solver = cp_model.CpSolver()
    assert solver.solve(cp) == cp_model.OPTIMAL
    assert result["status"] == "OPTIMAL"
    assert result["values"] == [0, 1]
    assert result["objective"] == result["bound"] == solver.objective_value / 100 + 0.125
    assert result["native_version"] == highs_backend.native_version()
    assert set(result["timings"]) == {"model_conversion_seconds", "search_seconds"}


def test_mixed_general_integer_and_continuous_domains():
    proto = model(offset=-1)
    variable(proto, "integer", -2, 4, 3)
    variable(proto, "continuous", 0, 2, 0.5, integer=False)
    row(proto, [0, 1], [1, 1], upper=2.5)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == "OPTIMAL" and result["values"] == [2, 0.5]
    assert result["objective"] == result["bound"] == 5.25


def test_continuous_minimization_for_hoi4():
    proto = model(maximize=False, offset=2.75)
    variable(proto, "x", 0, 1, 0.2, integer=False)
    variable(proto, "y", 0, 1, 0.3, integer=False)
    row(proto, [0, 1], [2, 1], lower=1)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == "OPTIMAL" and result["values"] == [0.5, 0]
    assert result["objective"] == result["bound"] == pytest.approx(2.85)


def test_sparse_duplicate_entries_are_combined_before_native_conversion():
    proto = model()
    variable(proto, "x", 0, 2, 1)
    row(proto, [0, 0], [1, 2], upper=3)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == "OPTIMAL" and result["values"] == [1]


@pytest.mark.parametrize("feasible", [True, False])
def test_zero_column_constant_models_and_offset(feasible):
    proto = model(offset=12.5)
    row(proto, [], [], lower=0 if feasible else 1)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == ("OPTIMAL" if feasible else "INFEASIBLE")
    assert result["values"] == ([] if feasible else None)
    assert result["objective"] == result["bound"] == (12.5 if feasible else None)


def test_native_infeasibility_does_not_invent_a_layout():
    proto = binary_model()
    row(proto, [0, 1], [1, 1], lower=2)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == "INFEASIBLE"
    assert result["values"] is result["objective"] is result["bound"] is None


def test_native_unbounded_continuous_model():
    proto = model()
    variable(proto, "unbounded", 0, math.inf, 1, integer=False)
    result = highs_backend.solve_highs(proto, workers=1)
    assert result["status"] == "UNBOUNDED"
    assert result["values"] is result["objective"] is result["bound"] is None


def test_worker_changes_partial_hints_and_zero_gap_options(monkeypatch):
    actual_solve = mathopt.solve
    observed = []

    def capture(model, solver, *, params, model_params):
        observed.append(params)
        return actual_solve(model, solver, params=params, model_params=model_params)

    monkeypatch.setattr(mathopt, "solve", capture)
    for count in (1, 2, 1):
        result = highs_backend.solve_highs(binary_model(), workers=count, incumbent={"x": 0})
        assert result["status"] == "OPTIMAL" and result["workers"] == count
    assert [params.highs.int_options["threads"] for params in observed] == [1, 2, 1]
    assert all(params.threads is None for params in observed)
    assert all(
        params.relative_gap_tolerance == params.absolute_gap_tolerance == 0 for params in observed
    )


def test_imports_and_solves_after_ortools_in_fresh_process():
    code = """
import json
from ortools.linear_solver import pywraplp, linear_solver_pb2
from ortools.sat.python import cp_model
from games.optimization.highs_backend import solve_highs
p = linear_solver_pb2.MPModelProto(maximize=True)
p.variable.add(name='x', lower_bound=0, upper_bound=1.5, is_integer=True, objective_coefficient=1)
print(json.dumps([solve_highs(p, workers=n)['objective'] for n in (1, 2, 1)]))
"""
    output = subprocess.check_output([sys.executable, "-c", code], text=True)
    assert json.loads(output) == [1, 1, 1]


def fake_result(reason, values=None, bound=math.inf):
    return SimpleNamespace(
        termination=SimpleNamespace(reason=reason, detail="Synthetic native termination"),
        has_primal_feasible_solution=lambda: values is not None,
        variable_values=lambda: values,
        best_objective_bound=lambda: bound,
    )


def convert_result(proto, reason, values, bound=math.inf):
    native = highs_backend._native_model(proto)
    mapping = None if values is None else dict(zip(native.variables(), values, strict=True))
    return highs_backend._solution(
        fake_result(reason, mapping, bound),
        native,
        proto,
        {"objective": None, "bound": None, "values": None},
    )


def test_capped_incumbent_keeps_finite_upper_bound_without_claiming_optimum():
    result = convert_result(binary_model(), mathopt.TerminationReason.FEASIBLE, [1, 0], 0.475)
    assert result["status"] == "FEASIBLE"
    assert result["objective"] == 0.325 and result["bound"] == 0.475


def test_capped_without_incumbent_keeps_native_bound_but_no_income():
    result = convert_result(binary_model(), mathopt.TerminationReason.NO_SOLUTION_FOUND, None, 0.6)
    assert result["status"] == "UNKNOWN" and result["bound"] == 0.6
    assert result["objective"] is result["values"] is None


@pytest.mark.parametrize("values", [[0.5, 0], [1, 1], [math.nan, 0], [2, 0]])
def test_invalid_native_optima_cannot_become_proofs(values):
    result = convert_result(binary_model(), mathopt.TerminationReason.OPTIMAL, values)
    assert result["status"] == "ABNORMAL"
    assert result["values"] is result["objective"] is result["bound"] is None


def test_integer_noise_is_canonicalized_then_revalidated():
    result = convert_result(binary_model(), mathopt.TerminationReason.OPTIMAL, [0, 1 - 1e-8])
    assert result["status"] == "OPTIMAL" and result["values"] == [0, 1]
    assert result["objective"] == result["bound"] == 0.475


def test_rounding_cannot_hide_a_constraint_violation():
    proto = model()
    variable(proto, "x", 0, 1, 1)
    row(proto, [0], [1e9], upper=999999999.5)
    result = convert_result(proto, mathopt.TerminationReason.OPTIMAL, [1 - 1e-9])
    assert result["status"] == "ABNORMAL"
    assert result["objective"] is result["bound"] is result["values"] is None


def test_minimization_bound_is_a_lower_bound():
    proto = binary_model()
    proto.maximize = False
    result = convert_result(proto, mathopt.TerminationReason.FEASIBLE, [1, 0], 0.125)
    assert result["objective"] == 0.325 and result["bound"] == 0.125
    bad_bound = convert_result(proto, mathopt.TerminationReason.FEASIBLE, [1, 0], 0.5)
    assert bad_bound["status"] == "FEASIBLE" and bad_bound["bound"] is None


def test_recomputed_overflow_is_not_an_optimal_income():
    proto = model()
    variable(proto, "x", 0, 10, 1e308)
    result = convert_result(proto, mathopt.TerminationReason.OPTIMAL, [10])
    assert result["status"] == "ABNORMAL" and result["objective"] is result["values"] is None


@pytest.mark.parametrize("seconds", [0, -1, math.nan, math.inf])
def test_invalid_time_limits_are_rejected(seconds):
    with pytest.raises(ValueError, match="positive and finite"):
        highs_backend.solve_highs(binary_model(), seconds=seconds)


def test_unknown_hint_and_nonfinite_model_are_rejected():
    with pytest.raises(ValueError, match="unknown variable"):
        highs_backend.solve_highs(binary_model(), incumbent={"missing": 1}, workers=1)
    proto = binary_model()
    proto.variable[0].objective_coefficient = math.inf
    with pytest.raises(ValueError, match="finite"):
        highs_backend.solve_highs(proto, workers=1)
