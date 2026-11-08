"""HiGHS via OR-Tools MathOpt, with verified linear solutions and CPU limits.

The two wheels' independently bundled HiGHS libraries share a SONAME but differ
in ABI, so this module uses only OR-Tools' bundled implementation. Its public C
API resets the global thread scheduler; MathOpt owns models and native solves.
"""

import ctypes
from datetime import timedelta
from functools import cache
from importlib.resources import files
from math import isfinite, isnan
from pathlib import Path
from threading import Lock
from time import perf_counter

from ortools.linear_solver import linear_solver_pb2
from ortools.math_opt import model_pb2
from ortools.math_opt.python import mathopt

from games.tw.cancellation import Cancellation
from games.tw.resources import resolve_workers

_SCHEDULER = Lock()
_TOLERANCE = 1e-6
_PRICE_MAX_SECONDS = 10.0


@cache
def _native_library():
    root = Path(str(files("ortools")))
    candidates = sorted(
        path
        for directory in (root / ".libs", root.parent / "ortools.libs")
        if directory.is_dir()
        for path in directory.iterdir()
        if "highs" in path.name.lower()
        and any(marker in path.name.lower() for marker in (".so", ".dylib", ".dll"))
    )
    if len(candidates) != 1:
        raise RuntimeError("Cannot identify the unique HiGHS library bundled with OR-Tools")
    library = ctypes.CDLL(str(candidates[0]))
    # OR-Tools 9.15's Linux, macOS and Windows wheels use 32-bit HighsInt.
    # The C API takes HighsInt blocking, and returns void; wait for all workers.
    library.Highs_resetGlobalScheduler.argtypes = [ctypes.c_int]
    library.Highs_resetGlobalScheduler.restype = None
    library.Highs_version.argtypes = []
    library.Highs_version.restype = ctypes.c_char_p
    return library


def native_version() -> str:
    """Read the bundled solver's C API; MPSolver's version label is incorrect."""
    return _native_library().Highs_version().decode("ascii")


def _validate_model(proto):
    if proto.general_constraint or proto.HasField("quadratic_objective"):
        raise ValueError("HiGHS supports linear constraints and objectives only")
    if not isfinite(proto.objective_offset):
        raise ValueError("Objective offset must be finite")
    for variable in proto.variable:
        if not isfinite(variable.objective_coefficient):
            raise ValueError("Objective coefficients must be finite")
        _validate_bounds(variable.lower_bound, variable.upper_bound)
    for row in proto.constraint:
        _validate_bounds(row.lower_bound, row.upper_bound)
        if len(row.var_index) != len(row.coefficient):
            raise ValueError("Constraint indices and coefficients must have equal length")
        if any(index < 0 or index >= len(proto.variable) for index in row.var_index):
            raise ValueError("Constraint references an unknown variable")
        if any(not isfinite(value) for value in row.coefficient):
            raise ValueError("Constraint coefficients must be finite")


def _validate_bounds(lower, upper):
    if isnan(lower) or isnan(upper) or lower > upper:
        raise ValueError("Variable and row bounds must be ordered and not NaN")


def _native_model(proto):
    native = model_pb2.ModelProto(name=proto.name)
    native.variables.ids.extend(range(len(proto.variable)))
    native.variables.lower_bounds.extend(variable.lower_bound for variable in proto.variable)
    native.variables.upper_bounds.extend(variable.upper_bound for variable in proto.variable)
    native.variables.integers.extend(variable.is_integer for variable in proto.variable)
    native.variables.names.extend(variable.name for variable in proto.variable)
    native.objective.maximize = proto.maximize
    native.objective.offset = proto.objective_offset
    for index, variable in enumerate(proto.variable):
        if variable.objective_coefficient:
            native.objective.linear_coefficients.ids.append(index)
            native.objective.linear_coefficients.values.append(variable.objective_coefficient)
    for row_id, row in enumerate(proto.constraint):
        native.linear_constraints.ids.append(row_id)
        native.linear_constraints.lower_bounds.append(row.lower_bound)
        native.linear_constraints.upper_bounds.append(row.upper_bound)
        native.linear_constraints.names.append(row.name)
        _matrix_row(native.linear_constraint_matrix, row_id, row)
    return mathopt.Model.from_model_proto(native)


def _matrix_row(matrix, row_id, row):
    amounts = {}
    for index, value in zip(row.var_index, row.coefficient, strict=True):
        amounts[index] = amounts.get(index, 0.0) + value
    for index, value in sorted(amounts.items()):
        if value:
            matrix.row_ids.append(row_id)
            matrix.column_ids.append(index)
            matrix.coefficients.append(value)


def _hint(model, proto, incumbent):
    params = mathopt.ModelSolveParameters()
    if not incumbent:
        return params
    lookup = {variable.name: index for index, variable in enumerate(proto.variable)}
    if len(lookup) != len(proto.variable):
        raise ValueError("HiGHS hints require unique variable names")
    if set(incumbent) - lookup.keys():
        raise ValueError("HiGHS hint references an unknown variable")
    if any(not isfinite(value) for value in incumbent.values()):
        raise ValueError("HiGHS hint values must be finite")
    params.solution_hints.append(
        mathopt.SolutionHint(
            variable_values={
                model.get_variable(lookup[name]): value for name, value in incumbent.items()
            }
        )
    )
    return params


def _feasible(proto, values):
    if len(values) != len(proto.variable) or any(not isfinite(value) for value in values):
        return False
    for variable, value in zip(proto.variable, values, strict=True):
        if value < variable.lower_bound - _TOLERANCE or value > variable.upper_bound + _TOLERANCE:
            return False
        if variable.is_integer and abs(value - round(value)) > _TOLERANCE:
            return False
    return all(
        row.lower_bound - _TOLERANCE
        <= sum(
            values[index] * amount
            for index, amount in zip(row.var_index, row.coefficient, strict=True)
        )
        <= row.upper_bound + _TOLERANCE
        for row in proto.constraint
    )


def _status(reason, has_solution):
    fixed = {
        mathopt.TerminationReason.OPTIMAL: "OPTIMAL",
        mathopt.TerminationReason.INFEASIBLE: "INFEASIBLE",
        mathopt.TerminationReason.UNBOUNDED: "UNBOUNDED",
        mathopt.TerminationReason.INFEASIBLE_OR_UNBOUNDED: "UNKNOWN",
        mathopt.TerminationReason.NUMERICAL_ERROR: "ABNORMAL",
        mathopt.TerminationReason.OTHER_ERROR: "ABNORMAL",
    }
    return fixed.get(reason, "FEASIBLE" if has_solution else "UNKNOWN")


def _bound(proto, result, objective, status):
    if status == "OPTIMAL":
        return objective
    value = result.best_objective_bound()
    if not isfinite(value):
        return None
    if objective is None:
        return value
    if proto.maximize:
        return max(value, objective) if value >= objective - _TOLERANCE else None
    return min(value, objective) if value <= objective + _TOLERANCE else None


def _solution(result, model, proto, report):
    values = None
    if result.has_primal_feasible_solution():
        solution = result.variable_values()
        candidate = [solution[model.get_variable(index)] for index in range(len(proto.variable))]
        if _feasible(proto, candidate):
            canonical = [
                float(round(value)) if variable.is_integer else value
                for variable, value in zip(proto.variable, candidate, strict=True)
            ]
            if _feasible(proto, canonical):
                values = canonical
    status = _status(result.termination.reason, values is not None)
    report.update(status=status, detail=result.termination.detail)
    if status == "OPTIMAL" and values is None:
        return {
            **report,
            "status": "ABNORMAL",
            "detail": "HiGHS returned an invalid optimal solution",
        }
    if values is not None and status in {"OPTIMAL", "FEASIBLE"}:
        report.update(
            values=values,
            objective=proto.objective_offset
            + sum(
                variable.objective_coefficient * value
                for variable, value in zip(proto.variable, values, strict=True)
            ),
        )
        if not isfinite(report["objective"]):
            return {
                **report,
                "status": "ABNORMAL",
                "values": None,
                "objective": None,
                "detail": "HiGHS solution objective is not finite",
            }
    if status in {"OPTIMAL", "FEASIBLE", "UNKNOWN"}:
        report["bound"] = _bound(proto, result, report["objective"], status)
    return report


def _empty_model(proto, report):
    feasible = all(row.lower_bound <= 0 <= row.upper_bound for row in proto.constraint)
    return {
        **report,
        "status": "OPTIMAL" if feasible else "INFEASIBLE",
        "values": [] if feasible else None,
        "objective": proto.objective_offset if feasible else None,
        "bound": proto.objective_offset if feasible else None,
        "detail": "Constant linear model evaluated directly",
    }


def solve_highs(
    proto,
    seconds=None,
    workers=None,
    incumbent=None,
    seed=0,
    *,
    cancellation: Cancellation | None = None,
):
    """Return validated values and a native bound in the linear model's units.

    ``bound`` is an upper bound when maximizing and a lower bound when minimizing.
    A configured allowance includes conversion. Partial hints remain optional.
    Cancellation checkpoints stop preparation; the bundled MathOpt HiGHS backend
    does not support interruption of an active native search.
    """
    started = perf_counter()
    if cancellation is not None:
        cancellation.checkpoint()
    workers = resolve_workers(workers)
    if seconds is not None and (not isfinite(seconds) or seconds <= 0):
        raise ValueError("HiGHS seconds must be positive and finite, or None")
    _validate_model(proto)
    report = {
        "algorithm": "highs",
        "status": "UNKNOWN",
        "seconds": 0.0,
        "objective": None,
        "bound": None,
        "values": None,
        "workers": workers,
        "timings": {"model_conversion_seconds": 0.0, "search_seconds": 0.0},
        "native_version": native_version(),
        "model_stats": {
            "formulation": "linear_mip",
            "variables": len(proto.variable),
            "constraints": len(proto.constraint),
        },
    }
    if not proto.variable:
        report = _empty_model(proto, report)
    else:
        with _SCHEDULER:
            if cancellation is not None:
                cancellation.checkpoint()
            _native_library().Highs_resetGlobalScheduler(1)
            report = _run(proto, report, started, seconds, incumbent, seed, cancellation)
    report["seconds"] = perf_counter() - started
    return report


def _run(proto, report, started, seconds, incumbent, seed, cancellation):
    model = _native_model(proto)
    hint = _hint(model, proto, incumbent)
    params = mathopt.SolveParameters(
        random_seed=seed, absolute_gap_tolerance=0.0, relative_gap_tolerance=0.0
    )
    params.highs.int_options["threads"] = report["workers"]
    params.highs.string_options["parallel"] = "on"
    if seconds is not None:
        params.time_limit = timedelta(seconds=max(0.0, seconds - (perf_counter() - started)))
    if cancellation is not None:
        cancellation.checkpoint()
    search_started = perf_counter()
    # OR-Tools 9.15's HighsSolver::Solve accepts but ignores SolveInterrupter:
    # https://github.com/google/or-tools/blob/v9.15/ortools/math_opt/solvers/highs_solver.cc#L912
    # Preserve any returned candidate even if cancellation arrives during search.
    result = mathopt.solve(model, mathopt.SolverType.HIGHS, params=params, model_params=hint)
    report["timings"] = {
        "model_conversion_seconds": search_started - started,
        "search_seconds": perf_counter() - search_started,
    }
    return _solution(result, model, proto, report)


def _validate_price_request(proto, row_index, seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise ValueError("Price estimation seconds must be positive and finite")
    if not isfinite(seconds) or seconds <= 0:
        raise ValueError("Price estimation seconds must be positive and finite")
    if not proto.maximize:
        raise ValueError("Price estimation requires a maximization objective")
    if isinstance(row_index, bool) or not isinstance(row_index, int):
        raise ValueError("Price estimation row index must be an integer")
    if not 0 <= row_index < len(proto.constraint):
        raise ValueError("Price estimation row index is outside the model")
    row = proto.constraint[row_index]
    if not isfinite(row.lower_bound) or row.upper_bound != float("inf"):
        raise ValueError("Price estimation requires a finite lower bound and no upper bound")


def estimate_lower_bound_price(
    proto,
    row_index: int,
    seconds: float,
    workers=None,
    *,
    cancellation: Cancellation | None = None,
) -> dict:
    """Estimate a nonnegative integer penalty from a continuous relaxation.

    The selected row must have only a finite lower bound in a maximization
    model. An optimal LP's negative row dual estimates the income opportunity
    cost of one row unit. Rounding this price is heuristic; this function returns
    no objective or bound certificate. A later exact solver must independently
    establish any Lagrangian bound using the returned nonnegative price.

    The allowance includes conversion and scheduler waiting and is capped at
    ten seconds. Cancellation is checked around preparation and native search;
    the bundled MathOpt HiGHS backend cannot interrupt an active native search.
    """
    started = perf_counter()
    if cancellation is not None:
        cancellation.checkpoint()
    _validate_price_request(proto, row_index, seconds)
    _validate_model(proto)
    workers = resolve_workers(workers)
    relaxed = linear_solver_pb2.MPModelProto()
    relaxed.CopyFrom(proto)
    for variable in relaxed.variable:
        variable.is_integer = False
    model = _native_model(relaxed)
    if cancellation is not None:
        cancellation.checkpoint()
    report = {
        "status": "UNKNOWN",
        "price": None,
        "seconds": 0.0,
        "workers": workers,
        "detail": "Price estimation allowance exhausted before native search",
        "timings": {
            "model_conversion_seconds": perf_counter() - started,
            "scheduler_wait_seconds": 0.0,
            "search_seconds": 0.0,
        },
    }
    allowance = min(seconds, _PRICE_MAX_SECONDS)
    remaining = allowance - (perf_counter() - started)
    if remaining > 0:
        _estimate_price_under_lock(
            model, row_index, report, started, allowance, remaining, cancellation
        )
    report["seconds"] = perf_counter() - started
    return report


def _estimate_price_under_lock(
    model, row_index, report, started, allowance, remaining, cancellation
):
    waiting = perf_counter()
    acquired = _SCHEDULER.acquire(timeout=remaining)
    report["timings"]["scheduler_wait_seconds"] = perf_counter() - waiting
    if not acquired:
        return
    try:
        if cancellation is not None:
            cancellation.checkpoint()
        _native_library().Highs_resetGlobalScheduler(1)
        params = mathopt.SolveParameters()
        params.highs.int_options["threads"] = report["workers"]
        params.highs.string_options["parallel"] = "on"
        remaining = allowance - (perf_counter() - started)
        if remaining <= 0:
            return
        params.time_limit = timedelta(seconds=remaining)
        if cancellation is not None:
            cancellation.checkpoint()
        search_started = perf_counter()
        # OR-Tools 9.15 ignores SolveInterrupter in HighsSolver::Solve; the
        # finite allowance bounds this optional prepass before its next checkpoint.
        result = mathopt.solve(model, mathopt.SolverType.HIGHS, params=params)
        report["timings"]["search_seconds"] = perf_counter() - search_started
        if cancellation is not None:
            cancellation.checkpoint()
        report.update(
            status=_status(result.termination.reason, result.has_primal_feasible_solution()),
            detail=result.termination.detail,
        )
        _price_from_dual(model, row_index, result, report)
    finally:
        _SCHEDULER.release()


def _price_from_dual(model, row_index, result, report):
    if result.termination.reason != mathopt.TerminationReason.OPTIMAL:
        return
    if not result.has_dual_feasible_solution():
        report["detail"] += "; no feasible dual solution available for price estimation"
        return
    dual = result.dual_values(model.get_linear_constraint(row_index))
    if not isfinite(dual):
        report["detail"] += "; selected row dual is not finite"
        return
    report["price"] = max(0, round(-dual))
