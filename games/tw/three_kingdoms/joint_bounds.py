"""Certified component upper bounds after explicitly relaxing shared requirements."""

from collections import Counter, defaultdict
from math import ceil, isfinite
from time import perf_counter

from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.tw.cancellation import Cancelled
from games.tw.highs_backend import estimate_lower_bound_price
from games.tw.rome2.decomposition import (
    InfeasibleRelaxation,
    UnsupportedDecomposition,
    decompose,
    objective_upper_bound,
)
from games.tw.search_progress import solve_with_progress


class Budget:
    def __init__(self, seconds):
        self.started = perf_counter()
        self.seconds = seconds
        self.price_report = {"status": "NOT_RUN", "price": None}

    @property
    def remaining(self):
        return max(0.0, self.seconds - (perf_counter() - self.started))


def _stopped(budget, cancellation):
    return budget.remaining <= 0 or (cancellation is not None and cancellation.requested)


def _price(proto, food_row, budget, workers, cancellation):
    if food_row is None or _stopped(budget, cancellation):
        return 0
    report = estimate_lower_bound_price(
        proto, food_row, min(3.0, budget.remaining / 3), workers, cancellation=cancellation
    )
    budget.price_report = report
    price = report.get("price")
    if type(price) is int and price >= 0:
        report["price_source"] = "continuous_relaxation"
        return price
    price = _fallback_price(proto, food_row)
    report.update(price_source="objective_food_domain_ratio", fallback_price=price)
    return price


def _fallback_price(proto, food_row):
    """Choose a unit-aware heuristic if the LP has no completed price estimate.

    Objective and food domain widths provide a positive scale without assuming
    a particular game's income per food. This value is not a certificate: only
    the later exact component bounds establish an upper bound at that price.
    """
    objective_width = sum(
        abs(int(v.objective_coefficient)) * (int(v.upper_bound) - int(v.lower_bound))
        for v in proto.variable
    )
    row = proto.constraint[food_row]
    food_width = sum(
        abs(int(c)) * (int(proto.variable[i].upper_bound) - int(proto.variable[i].lower_bound))
        for i, c in zip(row.var_index, row.coefficient, strict=True)
    )
    if not objective_width or not food_width:
        return 0
    return max(1, objective_width // food_width)


def _food(proto, food_row):
    terms = defaultdict(int)
    required = 0
    if food_row is not None:
        row = proto.constraint[food_row]
        if not isfinite(row.lower_bound) or row.upper_bound != float("inf"):
            raise UnsupportedDecomposition("Expected a lower-bound-only food constraint")
        required = int(row.lower_bound)
        for index, value in zip(row.var_index, row.coefficient, strict=True):
            if not isfinite(value) or int(value) != value:
                raise UnsupportedDecomposition("Food pricing requires integer coefficients")
            terms[index] += int(value)
    return terms, required


def _weighted(part, food, price):
    proto = linear_solver_pb2.MPModelProto()
    proto.CopyFrom(part.proto)
    for index, variable in zip(part.indices, proto.variable, strict=True):
        value = int(variable.objective_coefficient) + price * food[index]
        if abs(value) >= 2**53:
            raise UnsupportedDecomposition("Priced coefficient exceeds exact double range")
        variable.objective_coefficient = value
    objective_upper_bound(proto)
    return proto


def _solve(proto, budget, cancellation):
    from games.tw.three_kingdoms.optimization import native_model

    bounds = [objective_upper_bound(proto)]
    if _stopped(budget, cancellation):
        return bounds[0], "NOT_RUN"
    model, _ = native_model(proto)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.linearization_level = 2
    solver.parameters.max_time_in_seconds = min(0.5, max(0.001, budget.remaining))

    def observe(objective, bound, elapsed):
        if bound is not None and isfinite(bound) and abs(bound) < 2**53:
            bounds.append(ceil(bound))

    status = solve_with_progress(solver, model, on_search=observe, cancellation=cancellation)
    if status == cp_model.INFEASIBLE:
        raise InfeasibleRelaxation("A component relaxation is infeasible")
    if status == cp_model.MODEL_INVALID:
        raise UnsupportedDecomposition("CP-SAT rejected a component relaxation")
    return min(bounds), solver.status_name(status)


def _cut(target, part, weighted, bound):
    row = target.constraint.add(
        name=f"__component_bound:{len(target.constraint)}", upper_bound=bound
    )
    row.lower_bound = float("-inf")
    for index, variable in zip(part.indices, weighted.variable, strict=True):
        if variable.objective_coefficient:
            row.var_index.append(index)
            row.coefficient.append(variable.objective_coefficient)


def _objective_cut(target, bound):
    if abs(bound) >= 2**53 or abs(bound - target.objective_offset) >= 2**53:
        raise UnsupportedDecomposition("Combined bound exceeds exact double range")
    row = target.constraint.add(
        name="__joint_income_bound", upper_bound=bound - target.objective_offset
    )
    row.lower_bound = float("-inf")
    for index, variable in enumerate(target.variable):
        if variable.objective_coefficient:
            row.var_index.append(index)
            row.coefficient.append(variable.objective_coefficient)


def strengthen(proto, seconds, workers, *, cancellation=None, on_phase=None):
    """Return a strengthened copy; no original shared constraint is removed."""
    budget = Budget(seconds)
    target = linear_solver_pb2.MPModelProto()
    target.CopyFrom(proto)
    rows = tuple(
        i
        for i, row in enumerate(proto.constraint)
        if row.name == "__realm_food" or row.name.startswith("__resource:")
    )
    report = {"status": "skipped", "relaxed_rows": len(rows)}
    if not rows or _stopped(budget, cancellation):
        return target, None, report
    try:
        return _strengthen(proto, target, rows, budget, workers, cancellation, on_phase)
    except (UnsupportedDecomposition, InfeasibleRelaxation, Cancelled) as error:
        # Valid cuts already appended remain valid. An unsupported or interrupted
        # relaxation never fabricates a final-model proof or a zero upper bound.
        return target, None, {**report, "reason": str(error)}


def _strengthen(proto, target, rows, budget, workers, cancellation, on_phase):
    split = decompose(proto, relaxed_rows=rows)
    food_row = next((i for i in rows if proto.constraint[i].name == "__realm_food"), None)
    food, required = _food(proto, food_row)
    price = _price(proto, food_row, budget, workers, cancellation)
    total = split.constant + price * (sum(food[i] * v for i, v in split.fixed.items()) - required)
    statuses = Counter()
    for number, part in enumerate(split.parts, 1):
        if on_phase is not None:
            on_phase(f"Bounding connected commandery group {number}/{len(split.parts)}")
        weighted = _weighted(part, food, price)
        bound, status = _solve(weighted, budget, cancellation)
        _cut(target, part, weighted, bound)
        total += bound
        statuses[status] += 1
    report = {
        "status": "completed" if not statuses["NOT_RUN"] else "partial",
        "components": len(split.parts),
        "largest_component_variables": max((len(p.indices) for p in split.parts), default=0),
        "relaxed_rows": len(rows),
        "food_price": price,
        "price_estimation": budget.price_report,
        "component_statuses": dict(statuses),
        "upper_bound": total,
    }
    _objective_cut(target, total)
    return target, total, report
