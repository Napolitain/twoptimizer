"""Competing algorithms over a single snapshot of the engine's binary model."""

from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from math import gcd, isfinite, lcm
from random import Random
from time import perf_counter

import numpy as np
from ortools.linear_solver import linear_solver_pb2, pywraplp
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


def linear_solve(model, backend, seconds, workers=None):
    start = perf_counter()
    deadline = None if seconds is None else perf_counter() + seconds
    relaxation = backend == "glop"
    solver = pywraplp.Solver.CreateSolver(backend.upper())
    if solver is None:
        return Result(backend, "UNAVAILABLE", relaxation=relaxation)
    effective_workers = 1
    # The bundled CBC accepts SetNumThreads but prints "No match for threads".
    # SCIP's MPSolver interface supports parallel search; other backends stay serial.
    if backend == "scip":
        requested = resolve_workers(workers)
        if solver.SetNumThreads(requested):
            effective_workers = requested
    variables = [
        (solver.NumVar(0, 1, name) if relaxation else solver.BoolVar(name)) for name in model.names
    ]
    for (indices, coefficients), lo, hi in zip(
        model.row_entries(), model.lower, model.upper, strict=True
    ):
        constraint = solver.RowConstraint(float(lo), float(hi), "")
        for i, value in zip(indices, coefficients, strict=True):
            constraint.SetCoefficient(variables[i], float(value))
    objective = solver.Objective()
    objective.SetMaximization()
    objective.SetOffset(model.offset)
    for variable, profit in zip(variables, model.profit, strict=False):
        objective.SetCoefficient(variable, float(profit))
    if deadline is not None:
        solver.SetTimeLimit(max(1, int((deadline - perf_counter()) * 1000)))
    search_start = perf_counter()
    if relaxation:
        status = solver.Solve()
    else:
        parameters = pywraplp.MPSolverParameters()
        parameters.SetDoubleParam(parameters.RELATIVE_MIP_GAP, 0.0)
        status = solver.Solve(parameters)
    search_seconds = perf_counter() - search_start
    label = {
        solver.OPTIMAL: "OPTIMAL",
        solver.FEASIBLE: "FEASIBLE",
        solver.INFEASIBLE: "INFEASIBLE",
        solver.UNBOUNDED: "UNBOUNDED",
        solver.NOT_SOLVED: "UNKNOWN",
        solver.ABNORMAL: "ABNORMAL",
        solver.MODEL_INVALID: "MODEL_INVALID",
    }.get(status, "UNKNOWN")
    result = Result(
        backend,
        label,
        relaxation=relaxation,
        timings={
            "model_conversion_seconds": search_start - start,
            "search_seconds": search_seconds,
        },
        workers=effective_workers,
    )
    if status in (solver.OPTIMAL, solver.FEASIBLE):
        result.values = [v.solution_value() for v in variables]
        # Only an optimal LP objective is a certified upper bound.
        result.bound = (
            objective.Value()
            if relaxation and status == solver.OPTIMAL
            else None
            if relaxation
            else objective.BestBound()
        )
    return result


def sat_solve(model, seconds, seed, workers=None):
    workers = resolve_workers(workers)
    start = perf_counter()
    deadline = None if seconds is None else perf_counter() + seconds
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
    )
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result.values = [solver.value(v) for v in variables]
        nonzero = np.flatnonzero(coefficients)
        scale = float(model.profit[nonzero[0]] / coefficients[nonzero[0]]) if len(nonzero) else 1
        result.bound = solver.best_objective_bound * scale + model.offset
    return result


def beam_search(model, width, deadline, order):
    """Rank partial layouts by GDP and unmet resource requirements.

    Remaining-variable interval bounds safely prune impossible branches. Beam
    truncation is heuristic: an empty beam does not establish infeasibility.
    """
    matrix = model.matrix[:, order]
    remaining_min = np.minimum(matrix, 0).sum(axis=1)
    remaining_max = np.maximum(matrix, 0).sum(axis=1)
    row_scale = np.maximum(np.max(np.abs(matrix), axis=1, initial=0), 1)
    penalty = 4 * max(1, np.max(np.abs(model.profit), initial=0))
    totals = np.zeros((1, len(model.lower)))
    choices = np.zeros((1, len(order)), dtype=np.int8)
    scores = np.zeros(1)
    for depth, index in enumerate(order):
        if perf_counter() >= deadline:
            return None
        column = matrix[:, depth]
        remaining_min -= np.minimum(column, 0)
        remaining_max -= np.maximum(column, 0)
        candidates = np.concatenate((totals, totals + column))
        candidate_choices = np.concatenate((choices, choices.copy()))
        candidate_choices[len(choices) :, index] = 1
        candidate_scores = np.concatenate((scores, scores + model.profit[index]))
        possible = np.all(candidates + remaining_max >= model.lower - 1e-6, axis=1) & np.all(
            candidates + remaining_min <= model.upper + 1e-6, axis=1
        )
        keep = np.flatnonzero(possible)
        if not len(keep):
            return None
        # Reserve capacity for food, sanitation and mandatory buildings rather
        # than filling every slot with income before those needs are considered.
        shortage = np.maximum(model.lower - candidates[keep], 0)
        excess = np.maximum(candidates[keep] - model.upper, 0)
        pressure = ((shortage + excess) / row_scale).sum(axis=1)
        ranking = candidate_scores[keep] - penalty * pressure
        keep = keep[np.argsort(-ranking, kind="stable")[:width]]
        totals, choices, scores = (
            candidates[keep],
            candidate_choices[keep],
            candidate_scores[keep],
        )
    return choices[0].astype(float)


def improve(model, values, deadline):
    """Best improving feasible one-bit flip or one-for-one exchange."""
    x = values.copy()
    while perf_counter() < deadline:
        totals = model.matrix @ x
        best_gain, best_move = 1e-7, None
        for i in range(len(x)):
            if perf_counter() >= deadline:
                break
            delta = 1 - 2 * x[i]
            changed = totals + delta * model.matrix[:, i]
            gain = delta * model.profit[i]
            if (
                gain > best_gain
                and np.all(changed >= model.lower - 1e-6)
                and np.all(changed <= model.upper + 1e-6)
            ):
                best_gain, best_move = gain, (i,)
            if x[i] != 1:
                continue
            best_gain, best_move = _best_exchange(x, model, i, best_gain, changed, best_move)
        if best_move is None:
            break
        for i in best_move:
            x[i] = 1 - x[i]
    return x


def _best_exchange(x, model, i, best_gain, changed, best_move):
    for j in np.flatnonzero(x == 0):
        gain = model.profit[j] - model.profit[i]
        if gain <= best_gain:
            continue
        swapped = changed + model.matrix[:, j]
        if np.all(swapped >= model.lower - 1e-6) and np.all(swapped <= model.upper + 1e-6):
            best_gain, best_move = gain, (i, j)
    return best_gain, best_move


ALGORITHMS = ("cbc", "scip", "cp-sat", "greedy", "beam", "multistart", "glop")


def solve(model, algorithm, seconds=None, seed=0, width=128, restarts=16, workers=None):
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    if (
        (seconds is not None and (seconds <= 0 or not isfinite(seconds)))
        or width < 1
        or restarts < 1
    ):
        raise ValueError("Time limit, beam width and restart count must be positive")
    workers = resolve_workers(workers)
    start = perf_counter()
    deadline = float("inf") if seconds is None else start + seconds

    def remaining():
        return None if seconds is None else max(0.001, deadline - perf_counter())

    if algorithm in ("cbc", "scip", "glop"):
        result = linear_solve(model, algorithm, remaining(), workers)
    elif algorithm == "cp-sat":
        try:
            result = sat_solve(model, remaining(), seed, workers)
        except ValueError as exc:
            result = Result(algorithm, "MODEL_INVALID", detail=str(exc))
    else:
        # The LP supplies a promising construction order, not decisions forced
        # into the integer model. Its cost is included in heuristic timing.
        result = _solve_heuristic(model, deadline, seed, algorithm, restarts, width, remaining)
    validation_start = perf_counter()
    if result.values is not None:
        if not model.feasible(result.values, integral=not result.relaxation):
            result.status, result.detail = (
                "INVALID_SOLUTION",
                "Failed independent constraint validation",
            )
            result.values, result.bound = None, None
        else:
            result.objective = float(model.profit @ result.values) + model.offset
    result.timings["validation_seconds"] = perf_counter() - validation_start
    result.seconds = perf_counter() - start
    return result


def _solve_heuristic(model, deadline, seed, algorithm, restarts, width, remaining):
    guide = linear_solve(model, "glop", remaining())
    preferred = guide.values if guide.values is not None else np.zeros(len(model.names))
    order = sorted(
        range(len(model.names)),
        key=lambda i: (-preferred[i], -model.profit[i], model.names[i]),
    )
    random = Random(seed)
    best = None
    for attempt in range(restarts if algorithm == "multistart" else 1):
        if attempt:
            random.shuffle(order)
        candidate = beam_search(model, 1 if algorithm == "greedy" else width, deadline, order)
        if candidate is not None and (
            best is None or model.profit @ candidate > model.profit @ best
        ):
            best = candidate
    if best is not None and algorithm == "multistart":
        best = improve(model, best, deadline)
    result = Result(
        algorithm,
        "FEASIBLE" if best is not None else "NO_SOLUTION_FOUND",
        values=None if best is None else best.tolist(),
    )
    return result
