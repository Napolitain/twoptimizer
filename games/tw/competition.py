"""Competing algorithms over a single snapshot of the engine's binary model."""

from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from math import gcd, isfinite, lcm
from time import perf_counter

import numpy as np
from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.tw.resources import resolve_workers
from games.tw.sparse import SparseConstraints


@dataclass
class BinaryModel:
    names: tuple[str, ...]
    profit: np.ndarray
    matrix: np.ndarray | SparseConstraints
    lower: np.ndarray
    upper: np.ndarray
    offset: float = 0
    cp_sat_plan: object | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_solver(cls, solver):
        """Snapshot after filtering and objective creation, before any solve."""
        proto = linear_solver_pb2.MPModelProto()
        solver.ExportModelToProto(proto)
        if not proto.maximize:
            raise ValueError("Expected a maximization model")
        if any(
            not v.is_integer or v.lower_bound != 0 or v.upper_bound != 1 for v in proto.variable
        ):
            raise ValueError("All decisions must be binary")
        matrix = SparseConstraints(
            ((c.var_index, c.coefficient) for c in proto.constraint),
            len(proto.variable),
        )
        return cls(
            tuple(v.name for v in proto.variable),
            np.array([v.objective_coefficient for v in proto.variable]),
            matrix,
            np.array([c.lower_bound for c in proto.constraint]),
            np.array([c.upper_bound for c in proto.constraint]),
            proto.objective_offset,
        )

    def row_entries(self):
        if isinstance(self.matrix, SparseConstraints):
            yield from self.matrix.rows()
        else:
            for row in self.matrix:
                indices = np.flatnonzero(row)
                yield indices, row[indices]

    def feasible(self, values, integral=True, tolerance=1e-6):
        x = np.asarray(values, dtype=float)
        if x.shape != self.profit.shape or not np.all(np.isfinite(x)):
            return False
        if np.any(x < -tolerance) or np.any(x > 1 + tolerance):
            return False
        if integral and np.any(np.abs(x - np.rint(x)) > tolerance):
            return False
        totals = self.matrix @ x
        return bool(
            np.all(totals >= self.lower - tolerance) and np.all(totals <= self.upper + tolerance)
        )


@dataclass
class Result:
    algorithm: str
    status: str
    seconds: float = 0
    objective: float | None = None
    bound: float | None = None
    values: list[float] | None = None
    relaxation: bool = False
    detail: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    workers: int | None = None
    model_stats: dict = field(default_factory=dict)


def integer_row(values):
    """Scale decimal coefficients exactly; reject unsafe CP-SAT magnitudes."""
    fractions = [Fraction(str(float(v))) for v in values]
    scale = lcm(*(f.denominator for f in fractions))
    integers = [f.numerator * (scale // f.denominator) for f in fractions]
    divisor = reduce(gcd, integers, 0) or 1
    integers = [v // divisor for v in integers]
    if sum(abs(v) for v in integers) >= 2**60:
        raise ValueError("Exact decimal scaling exceeds the safe CP-SAT integer range")
    return integers


def highs_solve(model, seconds, seed, workers=None):
    """Export sparse binary coefficients to the shared general HiGHS adapter."""
    from games.tw.highs_backend import solve_highs

    start = perf_counter()
    proto = linear_solver_pb2.MPModelProto(maximize=True, objective_offset=model.offset)
    for name, profit in zip(model.names, model.profit, strict=True):
        proto.variable.add(
            name=name,
            lower_bound=0,
            upper_bound=1,
            is_integer=True,
            objective_coefficient=float(profit),
        )
    for (indices, coefficients), lo, hi in zip(
        model.row_entries(), model.lower, model.upper, strict=True
    ):
        proto.constraint.add(
            lower_bound=float(lo),
            upper_bound=float(hi),
            var_index=indices,
            coefficient=coefficients,
        )
    exported = perf_counter() - start
    remaining = None if seconds is None else max(0.001, seconds - exported)
    report = solve_highs(proto, seconds=remaining, workers=workers, seed=seed)
    result = Result(
        **{key: value for key, value in report.items() if key in Result.__dataclass_fields__}
    )
    result.timings["model_conversion_seconds"] = (
        result.timings.get("model_conversion_seconds", 0) + exported
    )
    return result


def sat_solve(model, seconds, seed, workers=None):
    workers = resolve_workers(workers)
    start = perf_counter()
    deadline = None if seconds is None else perf_counter() + seconds
    fallback_reason = None
    if model.cp_sat_plan is not None:
        from games.tw.attila.compact import UnsupportedCompact

        try:
            return model.cp_sat_plan.solve(model, seconds, seed, workers)
        except UnsupportedCompact as error:
            fallback_reason = str(error)
    problem = cp_model.CpModel()
    variables = [problem.new_bool_var(name) for name in model.names]
    for (indices, coefficients), lo, hi in zip(
        model.row_entries(), model.lower, model.upper, strict=True
    ):
        bounds = [v for v in (lo, hi) if isfinite(v)]
        integers = integer_row([*coefficients, *bounds])
        expression = sum(value * variables[i] for i, value in zip(indices, integers, strict=False))
        offset = len(indices)
        if isfinite(lo):
            problem.add(expression >= integers[offset])
            offset += 1
        if isfinite(hi):
            problem.add(expression <= integers[offset])
    coefficients = integer_row(model.profit)
    problem.maximize(sum(c * x for c, x in zip(coefficients, variables, strict=False)))
    solver = cp_model.CpSolver()
    if deadline is not None:
        solver.parameters.max_time_in_seconds = max(0.001, deadline - perf_counter())
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    search_start = perf_counter()
    status = solver.solve(problem)
    result = Result(
        "cp-sat",
        solver.status_name(status),
        timings={
            "model_conversion_seconds": search_start - start,
            "search_seconds": perf_counter() - search_start,
        },
        workers=workers,
        model_stats={
            "formulation": "expanded_boolean",
            "variables": len(problem.proto.variables),
            "constraints": len(problem.proto.constraints),
        },
    )
    if fallback_reason is not None:
        result.model_stats["fallback_reason"] = fallback_reason
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result.values = [solver.value(v) for v in variables]
        nonzero = np.flatnonzero(coefficients)
        scale = float(model.profit[nonzero[0]] / coefficients[nonzero[0]]) if len(nonzero) else 1
        result.bound = solver.best_objective_bound * scale + model.offset
    return result


ALGORITHMS = ("cp-sat", "highs")


def solve(model, algorithm, seconds=None, seed=0, workers=None):
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}; choose cp-sat or highs")
    if seconds is not None and (seconds <= 0 or not isfinite(seconds)):
        raise ValueError("Time limit must be positive and finite")
    workers = resolve_workers(workers)
    start = perf_counter()
    try:
        result = (
            sat_solve(model, seconds, seed, workers)
            if algorithm == "cp-sat"
            else highs_solve(model, seconds, seed, workers)
        )
    except ValueError as exc:
        result = Result(algorithm, "MODEL_INVALID", detail=str(exc))
    validation_start = perf_counter()
    if result.values is not None:
        if not model.feasible(result.values):
            result.status, result.detail = (
                "INVALID_SOLUTION",
                "Failed independent constraint validation",
            )
            result.values, result.bound, result.objective = None, None, None
        else:
            result.objective = float(model.profit @ result.values) + model.offset
    result.timings["validation_seconds"] = perf_counter() - validation_start
    result.seconds = perf_counter() - start
    return result
