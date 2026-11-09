"""Bound the full income model with integer, food-priced component relaxations.

The original shared-food row remains in the final model. Component incumbents
are never joint incumbents: only a complete assignment satisfying every original
row and variable domain is eligible as a hint. All reported objective amounts
use the original integer units (one ten-thousandth of income).
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import isfinite
from time import perf_counter

from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.optimization.bounds import BoundSearchResult
from games.optimization.budget import Budget
from games.optimization.cp_backend import NativeCP
from games.optimization.exact import integer_upper_bound
from games.optimization.highs_backend import estimate_lower_bound_price
from games.optimization.linear_components import (
    InfeasibleRelaxation,
    UnsupportedDecomposition,
    decompose,
    objective_upper_bound,
)
from games.optimization.search_progress import solve_with_progress


@dataclass(frozen=True)
class _ComponentResult:
    bound: int
    values: dict[int, int] | None = None
    status: str = "NOT_RUN"


def _integer(value):
    if not isfinite(value) or int(value) != value:
        raise UnsupportedDecomposition("Bound preparation requires exact integer coefficients")
    return int(value)


def _food_terms(proto, row_index):
    if not proto.maximize or not 0 <= row_index < len(proto.constraint):
        raise UnsupportedDecomposition("Expected a maximizing model and its shared-food row")
    row = proto.constraint[row_index]
    if not isfinite(row.lower_bound) or row.upper_bound != float("inf"):
        raise UnsupportedDecomposition("Shared food must be a lower-bound-only constraint")
    coefficients = defaultdict(int)
    for index, coefficient in zip(row.var_index, row.coefficient, strict=True):
        coefficients[index] += _integer(coefficient)
    return coefficients, _integer(row.lower_bound)


def _weighted_proto(part, food, price):
    proto = linear_solver_pb2.MPModelProto()
    proto.CopyFrom(part.proto)
    activity = 0
    for index, variable in zip(part.indices, proto.variable, strict=True):
        amount = _integer(variable.objective_coefficient) + price * food[index]
        # Protobuf stores doubles; never silently round a priced coefficient.
        if abs(amount) >= 2**60 or float(amount) != amount:
            raise UnsupportedDecomposition("Priced coefficients exceed safe exact scaling")
        activity += abs(amount) * max(
            abs(_integer(variable.lower_bound)), abs(_integer(variable.upper_bound))
        )
        variable.objective_coefficient = amount
    if activity >= 2**60:
        raise UnsupportedDecomposition("Priced objective exceeds safe CP-SAT activity")
    return proto


def _feasible(proto, values):
    if set(values) != set(range(len(proto.variable))):
        return False
    for index, variable in enumerate(proto.variable):
        value = values[index]
        if not isinstance(value, int) or not variable.lower_bound <= value <= variable.upper_bound:
            return False
    for row in proto.constraint:
        total = sum(
            _integer(amount) * values[index]
            for index, amount in zip(row.var_index, row.coefficient, strict=True)
        )
        if not row.lower_bound <= total <= row.upper_bound:
            return False
    return True


def _objective(proto, values):
    return _integer(proto.objective_offset) + sum(
        _integer(variable.objective_coefficient) * values[index]
        for index, variable in enumerate(proto.variable)
    )


def _component_values(proto, problem, solver, status, bound):
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    values = {index: solver.value(variable) for index, variable in enumerate(problem.variables)}
    if not _feasible(proto, values):
        raise RuntimeError("Component incumbent failed independent constraint validation")
    if _objective(proto, values) > bound:
        raise RuntimeError("Component upper bound is below a validated incumbent")
    return values


def _solve_component(proto, budget, workers, cancellation):
    fallback = objective_upper_bound(proto)
    if budget.remaining <= 0:
        return _ComponentResult(fallback)
    problem = NativeCP.from_linear(proto)
    error = problem.model.validate()
    if error:
        raise ValueError(error)
    allowance = min(1.0, budget.remaining)
    if allowance <= 0:
        return _ComponentResult(fallback)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = allowance
    solver.parameters.num_search_workers = workers
    solver.parameters.linearization_level = 2
    solver.parameters.random_seed = 0
    bounds = [fallback]

    def observe(objective, bound, elapsed):
        if bound is not None and (upper := integer_upper_bound(bound)) is not None:
            bounds.append(upper)

    status = solve_with_progress(
        solver, problem.model, cancellation=cancellation, on_search=observe
    )
    if status == cp_model.INFEASIBLE:
        raise InfeasibleRelaxation("A component relaxation is infeasible")
    if status == cp_model.MODEL_INVALID:
        raise ValueError("CP-SAT rejected a component relaxation")
    values = _component_values(proto, problem, solver, status, min(bounds))
    return _ComponentResult(min(bounds), values, solver.status_name(status))


def _phase(callback, message):
    if callback is not None:
        callback(message)


def _checkpoint(cancellation):
    if cancellation is not None:
        cancellation.checkpoint()


def _price(proto, food_row, workers, budget, cancellation, on_phase):
    if budget.remaining <= 0:
        return 0, {"status": "NOT_RUN", "price": None}
    _phase(on_phase, "Estimating the shared-food price for province bounds")
    allowance = min(10.0, budget.remaining / 3)
    if allowance <= 0:
        return 0, {"status": "NOT_RUN", "price": None}
    report = estimate_lower_bound_price(
        proto,
        food_row,
        allowance,
        workers,
        cancellation=cancellation,
    )
    price = report.get("price")
    if isinstance(price, bool) or not isinstance(price, int) or price < 0:
        price = 0
    return price, report


def _add_cut(problem, part, proto, bound):
    expression = sum(
        _integer(variable.objective_coefficient) * problem.variables[index]
        for index, variable in zip(part.indices, proto.variable, strict=True)
    )
    problem.Add(expression <= bound)


def _assemble(proto, parts, fixed, results):
    if any(result.values is None for result in results):
        return None
    values = dict(fixed)
    for part, result in zip(parts, results, strict=True):
        assert result.values is not None
        values.update({index: result.values[local] for local, index in enumerate(part.indices)})
    return values if _feasible(proto, values) else None


def _search(problem, proto, food_row, workers, budget, cancellation, on_phase):
    _checkpoint(cancellation)
    if budget.remaining <= 0:
        return BoundSearchResult(None, None, {"status": "skipped", "reason": "No time remaining"})
    _phase(on_phase, "Preparing connected province groups for income bounds")
    food, required = _food_terms(proto, food_row)
    decomposition = decompose(proto, relaxed_rows=(food_row,))
    parts = decomposition.parts
    if len(parts) < 4:
        return BoundSearchResult(
            None, None, {"status": "skipped", "reason": "Fewer than four connected groups"}
        )
    _checkpoint(cancellation)
    price, price_report = _price(proto, food_row, workers, budget, cancellation, on_phase)
    weighted = [_weighted_proto(part, food, price) for part in parts]
    results = []
    for number, (part, local) in enumerate(zip(parts, weighted, strict=True), 1):
        _checkpoint(cancellation)
        _phase(on_phase, f"Bounding connected province group {number}/{len(parts)}")
        result = _solve_component(local, budget, workers, cancellation)
        results.append(result)
        _add_cut(problem, part, local, result.bound)
    fixed_food = sum(food[index] * value for index, value in decomposition.fixed.items())
    upper = decomposition.constant + price * (fixed_food - required)
    upper += sum(result.bound for result in results)
    upper = min(upper, objective_upper_bound(proto))
    hint = _assemble(proto, parts, decomposition.fixed, results)
    return BoundSearchResult(
        upper,
        hint,
        {
            "status": "completed" if all(r.status != "NOT_RUN" for r in results) else "partial",
            "components": len(parts),
            "components_solved": sum(result.status != "NOT_RUN" for result in results),
            "component_statuses": dict(Counter(result.status for result in results)),
            "cuts": len(results),
            "food_price": price,
            "price_solver": price_report,
            "upper_bound": upper,
            "hint_income": _objective(proto, hint) if hint is not None else None,
        },
    )


def strengthen(
    problem: NativeCP,
    proto,
    food_row: int,
    seconds: float | None,
    workers: int,
    *,
    cancellation=None,
    on_phase=None,
) -> BoundSearchResult:
    """Add safe component cuts, returning a bound and an optional full-model hint.

    ``seconds`` is the entire preparatory allowance, including decomposition,
    LP pricing and conversion. None means forty seconds. The LP price only
    chooses a nonnegative integer Lagrange multiplier; its objective/bound is
    never treated as an exact income certificate.
    """
    budget = Budget(40.0 if seconds is None else seconds, clock=perf_counter)
    try:
        result = _search(problem, proto, food_row, workers, budget, cancellation, on_phase)
    except UnsupportedDecomposition as error:
        result = BoundSearchResult(None, None, {"status": "skipped", "reason": str(error)})
    except InfeasibleRelaxation as error:
        problem.Add(False)
        result = BoundSearchResult(
            None, None, {"status": "infeasible_relaxation", "reason": str(error)}
        )
    result.report.update(seconds=budget.elapsed, objective_unit="1/10000 income")
    return result
