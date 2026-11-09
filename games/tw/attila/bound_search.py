"""Certified component bounds for the original compact Attila income model.

Component assignments become hints only after satisfying every original native
constraint, including relaxed cross-province rows. All objective values here are
native integers; the owning optimizer applies the compact model's income unit.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from math import ceil
from time import perf_counter

from ortools.sat.python import cp_model

from games.optimization.bounds import BoundSearchResult
from games.optimization.budget import Budget
from games.optimization.cancellation import Cancelled
from games.optimization.exact import integer_upper_bound
from games.optimization.native_model import (
    UnsupportedNativeModel,
    extract,
    feasible,
    objective_terms,
    objective_upper_bound,
    objective_value,
)
from games.optimization.search_progress import solve_with_progress
from games.tw.attila.partition import UnsupportedPartition, partition
from games.tw.attila.projection import ProjectionRows


@dataclass(frozen=True)
class _ComponentResult:
    bound: int
    domain_bound: int
    values: dict[int, int] | None = None
    status: str = "NOT_RUN"
    projected_rows: int = 0


class _InfeasibleRelaxation(Exception):
    pass


def _domain_bound(model, indices, coefficients):
    total = 0
    for index in indices:
        coefficient = coefficients.get(index, 0)
        domain = model.proto.variables[index].domain
        total += coefficient * domain[len(domain) - 1 if coefficient > 0 else 0]
    return total


def _stopped(budget, cancellation):
    return budget.remaining <= 0 or (cancellation is not None and cancellation.requested)


def _values(model, original_indices, solver, status, bound):
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        return None
    local = {
        index: solver.value(model.get_int_var_from_proto_index(index))
        for index in range(len(original_indices))
    }
    if not feasible(model, local):
        raise RuntimeError("Component incumbent failed independent native constraint validation")
    if objective_value(model, local) > bound:
        raise RuntimeError("Component upper bound is below a validated incumbent")
    return {original: local[index] for index, original in enumerate(original_indices)}


def _solve_component(
    model, original_indices, fallback, budget, remaining_count, parallelism, seed, cancellation
):
    error = model.validate()
    if error:
        raise ValueError(error)
    allowance = min(1.0, budget.remaining / ceil(remaining_count / parallelism))
    if allowance <= 0 or (cancellation is not None and cancellation.requested):
        return _ComponentResult(fallback, fallback)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = allowance
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.linearization_level = 2
    bounds = [fallback]

    def observe(objective, bound, elapsed):
        if bound is not None and (upper := integer_upper_bound(bound)) is not None:
            bounds[:] = [min(bounds[0], upper)]

    try:
        status = solve_with_progress(solver, model, on_search=observe, cancellation=cancellation)
    except Cancelled:
        return _ComponentResult(bounds[0], fallback)
    if status == cp_model.INFEASIBLE:
        raise _InfeasibleRelaxation("A connected province relaxation is infeasible")
    if status == cp_model.MODEL_INVALID:
        raise ValueError("CP-SAT rejected a connected province relaxation")
    values = _values(model, original_indices, solver, status, bounds[0])
    return _ComponentResult(bounds[0], fallback, values, solver.status_name(status))


def _component(
    original,
    part,
    fixed,
    coefficients,
    projections,
    budget,
    remaining_count,
    seed,
    parallelism,
    cancellation,
):
    fallback = _domain_bound(original, part.indices, coefficients)
    if _stopped(budget, cancellation):
        return _ComponentResult(fallback, fallback)
    local_coefficients = {
        index: coefficients[index] for index in part.indices if index in coefficients
    }
    model, original_indices = extract(original, part.indices, part.rows, fixed, local_coefficients)
    if objective_upper_bound(model) != fallback:
        raise AssertionError("Extracted component objective does not match its original domains")
    projected = projections.apply(model, original_indices, part.indices)
    result = _solve_component(
        model, original_indices, fallback, budget, remaining_count, parallelism, seed, cancellation
    )
    return replace(result, projected_rows=projected)


def _hint(original, decomposition, results):
    if any(result.values is None for result in results):
        return None
    values = dict(decomposition.fixed)
    for result in results:
        assert result.values is not None
        values.update(result.values)
    return values if feasible(original, values) else None


def _cuts(model, parts, results, coefficients):
    count = 0
    for part, result in zip(parts, results, strict=True):
        if result.bound >= result.domain_bound:
            continue
        expression = sum(
            coefficient * model.get_int_var_from_proto_index(index)
            for index in part.indices
            if (coefficient := coefficients.get(index, 0))
        )
        model.add(expression <= result.bound)
        count += 1
    return count


def _run_parts(
    original,
    decomposition,
    coefficients,
    projections,
    budget,
    seed,
    workers,
    cancellation,
    on_phase,
):
    parts = decomposition.parts
    parallelism = min(workers, len(parts))

    def work(number, part):
        return _component(
            original,
            part,
            decomposition.fixed,
            coefficients,
            projections,
            budget,
            len(parts) - number + 1,
            seed,
            parallelism,
            cancellation,
        )

    def phase(number):
        if on_phase is not None and not _stopped(budget, cancellation):
            on_phase(f"Bounding connected province group {number}/{len(parts)}")

    if parallelism == 1:
        results = []
        for number, part in enumerate(parts, 1):
            phase(number)
            results.append(work(number, part))
        return results
    with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix="attila-bound") as pool:
        futures = []
        try:
            for number, part in enumerate(parts, 1):
                futures.append(pool.submit(work, number, part))
            completed = {}
            for number, future in enumerate(as_completed(futures), 1):
                phase(number)
                completed[future] = future.result()
            return [completed[future] for future in futures]
        except BaseException:
            for future in futures:
                future.cancel()
            raise


def _search(builder, budget, seed, workers, cancellation, on_phase):
    if _stopped(budget, cancellation):
        return BoundSearchResult(
            None, None, {"status": "skipped", "reason": "No preparation allowance remaining"}
        )
    if on_phase is not None:
        on_phase("Preparing connected province groups for income bounds")
    original = builder.model.clone()
    decomposition = partition(builder)
    coefficients, _ = objective_terms(original)
    parts = decomposition.parts
    if len(parts) < 4:
        return BoundSearchResult(
            None, None, {"status": "skipped", "reason": "Fewer than four connected groups"}
        )
    projections = ProjectionRows(original, decomposition.fixed, decomposition.relaxed_rows)
    results = _run_parts(
        original,
        decomposition,
        coefficients,
        projections,
        budget,
        seed,
        workers,
        cancellation,
        on_phase,
    )
    upper = min(
        decomposition.constant + sum(result.bound for result in results),
        objective_upper_bound(original),
    )
    hint = _hint(original, decomposition, results)
    income = None if hint is None else objective_value(original, hint)
    if income is not None and income > upper:
        raise RuntimeError("Joint component bound is below a validated full-model incumbent")
    cuts = _cuts(builder.model, parts, results, coefficients)
    return BoundSearchResult(
        upper,
        hint,
        {
            "status": "completed"
            if all(result.status != "NOT_RUN" for result in results)
            else "partial",
            "components": len(parts),
            "components_solved": sum(result.status != "NOT_RUN" for result in results),
            "parallelism": min(workers, len(parts)),
            "component_workers": 1,
            "component_statuses": dict(Counter(result.status for result in results)),
            "cuts": cuts,
            "projected_rows": sum(result.projected_rows for result in results),
            "relaxed_rows": len(decomposition.relaxed_rows),
            "relaxed_reference_rows": list(decomposition.relaxed_reference_rows),
            "upper_bound": upper,
            "hint_objective": income,
        },
    )


def strengthen(builder, seconds, seed, workers, *, cancellation=None, on_phase=None):
    """Bound relaxed groups within forty seconds and retain only original-model hints."""
    budget = Budget(40.0 if seconds is None else seconds, clock=perf_counter)
    budget.limit = min(40.0, budget.limit)
    try:
        result = _search(builder, budget, seed, workers, cancellation, on_phase)
    except (UnsupportedNativeModel, UnsupportedPartition) as error:
        result = BoundSearchResult(None, None, {"status": "skipped", "reason": str(error)})
    except _InfeasibleRelaxation as error:
        builder.model.add(False)
        result = BoundSearchResult(
            None, None, {"status": "infeasible_relaxation", "reason": str(error)}
        )
    result.report.update(seconds=budget.elapsed, objective_unit="native integer")
    return result
