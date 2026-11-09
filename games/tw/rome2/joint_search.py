"""CP-SAT search with optional certified bounds from a relaxed joint food model."""

from math import ceil, isfinite
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.cancellation import Cancelled
from games.tw.search_progress import solve_with_progress


def _strengthen(problem, proto, seconds, workers, started, cancellation, on_phase):
    from games.tw.rome2.bound_search import strengthen

    row = next(
        (i for i, constraint in enumerate(proto.constraint) if constraint.name == "__realm_food"),
        None,
    )
    remaining = None if seconds is None else seconds - (perf_counter() - started)
    # Full-world preparation measured about 23 seconds. Keep short configured
    # runs on the direct search path instead of spending most of their allowance
    # on an unfinished set of component searches.
    if row is None or (remaining is not None and remaining < 45):
        return None
    allowance = 40 if remaining is None else min(40, remaining * 2 / 3)
    return strengthen(
        problem,
        proto,
        row,
        allowance,
        workers,
        cancellation=cancellation,
        on_phase=on_phase,
    )


def _install_seed(problem, bounds, incumbent_income):
    if bounds is None or bounds.hint_values is None:
        return
    income = bounds.report["hint_income"] / 10000
    if incumbent_income is not None and incumbent_income >= income:
        return
    problem.model.clear_hints()
    for index, value in bounds.hint_values.items():
        problem.model.add_hint(problem.variables[index], value)


def _observer(on_search, bounds, observed, incumbent_income=None):
    known = None if bounds is None else bounds.upper_bound
    seed = None if bounds is None else bounds.report.get("hint_income")

    def observe(objective, bound, elapsed):
        if bound is not None and isfinite(bound) and abs(bound) < 2**53:
            observed[:] = [min([ceil(bound), *observed])]
        incomes = [value / 10000 for value in (objective, seed) if value is not None]
        if incumbent_income is not None:
            incomes.append(incumbent_income)
        upper = [value / 10000 for value in (bound, known) if value is not None]
        if on_search is not None:
            on_search(max(incomes, default=None), min(upper, default=None), elapsed)

    return observe


def _native_solve(solver, problem, observer, bounds, cancellation, incumbent_income):
    try:
        return solve_with_progress(
            solver,
            problem.model,
            on_search=observer,
            scale=1,
            cancellation=cancellation,
        )
    except Cancelled:
        # A complete provincial seed has passed the original joint matrix. Keep
        # it for ordinary independent economic validation if search never starts.
        if incumbent_income is None and (bounds is None or bounds.hint_values is None):
            raise
        return cp_model.UNKNOWN


def _selection(solver, problem, proto, status, bounds, observed):
    values, objective, bound = None, None, None
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        values = [solver.value(variable) for variable in problem.variables]
        objective = solver.objective_value
        bound = solver.best_objective_bound
    upper = [value for value in (bound, *observed) if value is not None]
    if bounds is not None and bounds.upper_bound is not None:
        upper.append(bounds.upper_bound)
    bound = min(upper, default=None)
    if bounds is not None:
        values, objective, status = _retain_seed(
            values, objective, status, bounds, len(problem.variables)
        )
    if objective is not None and bound is not None and bound < objective - 1e-5:
        raise AssertionError("Joint upper bound is below a validated candidate")
    if status == cp_model.INFEASIBLE:
        bound = None
    return values, objective, bound, status


def _retain_seed(values, objective, status, bounds, count):
    if bounds.hint_values is None:
        return values, objective, status
    seed = bounds.report["hint_income"]
    if status == cp_model.INFEASIBLE or (status == cp_model.OPTIMAL and seed > objective + 1e-5):
        raise AssertionError("Native proof contradicts the validated provincial seed")
    if status not in (cp_model.UNKNOWN, cp_model.FEASIBLE, cp_model.OPTIMAL):
        return values, objective, status
    if objective is None or seed > objective:
        return [bounds.hint_values[i] for i in range(count)], seed, cp_model.FEASIBLE
    return values, objective, status


def solve(
    problem,
    proto,
    *,
    seconds,
    workers,
    started,
    incumbent_income=None,
    on_search=None,
    on_model=None,
    on_phase=None,
    cancellation=None,
    preparation=None,
    formulation="linearized_income",
):
    """Strengthen the original model, then preserve its best verified assignment."""
    bound_start = perf_counter()
    prepare = _strengthen if preparation is None else preparation
    bounds = prepare(problem, proto, seconds, workers, started, cancellation, on_phase)
    bound_seconds = perf_counter() - bound_start
    _install_seed(problem, bounds, incumbent_income)
    error = problem.model.validate()
    if error:
        raise ValueError(error)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 0
    solver.parameters.linearization_level = 2
    if seconds is not None:
        solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - started))
    stats = {
        "formulation": formulation,
        "variables": len(problem.model.proto.variables),
        "constraints": len(problem.model.proto.constraints),
    }
    observed = []
    observer = _observer(on_search, bounds, observed, incumbent_income)
    if on_phase is not None:
        on_phase(
            "Searching the complete joint model" if bounds is not None else "Solving and validating"
        )
    if on_model is not None:
        on_model(stats)
    search_start = perf_counter()
    native_status = _native_solve(solver, problem, observer, bounds, cancellation, incumbent_income)
    search_seconds = perf_counter() - search_start
    values, objective, bound, status = _selection(
        solver, problem, proto, native_status, bounds, observed
    )
    report = {
        "algorithm": "cp-sat",
        "status": solver.status_name(status),
        "seconds": perf_counter() - started,
        "objective": None if objective is None else objective / 10000,
        "bound": None if bound is None else bound / 10000,
        **stats,
        "workers": workers,
        "timings": {
            "model_conversion_seconds": search_start - started - bound_seconds,
            "bound_strengthening_seconds": bound_seconds,
            "search_seconds": search_seconds,
        },
    }
    if bounds is not None:
        report["joint_bound_search"] = bounds.report
    if native_status != status:
        report["native_status"] = solver.status_name(native_status)
    return report, values
