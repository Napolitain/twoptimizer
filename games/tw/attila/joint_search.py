"""Search the complete Attila model after optional provincial bound preparation."""

from math import ceil, isfinite
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.cancellation import Cancelled
from games.tw.competition import Result
from games.tw.search_progress import solve_with_progress


def _strengthen(builder, seconds, seed, workers, started, cancellation, on_phase):
    from games.tw.attila.bound_search import strengthen

    remaining = None if seconds is None else seconds - (perf_counter() - started)
    if len(builder.plan.economy.provinces) < 4 or (remaining is not None and remaining < 45):
        return None
    allowance = 40 if remaining is None else min(40, remaining * 2 / 3)
    return strengthen(
        builder, allowance, seed, workers, cancellation=cancellation, on_phase=on_phase
    )


def _observe(on_search, bounds, observed, unit, incumbent_income=None):
    known = None if bounds is None else bounds.upper_bound
    seed = None if bounds is None else bounds.report.get("hint_objective")

    def observe(objective, bound, elapsed):
        if bound is not None and isfinite(bound) and abs(bound) < 2**53:
            observed[:] = [min([ceil(bound), *observed])]
        incomes = [value * float(unit) for value in (objective, seed) if value is not None]
        if incumbent_income is not None:
            incomes.append(incumbent_income)
        upper = [value * float(unit) for value in (bound, known) if value is not None]
        if on_search is not None:
            on_search(max(incomes, default=None), min(upper, default=None), elapsed)

    return observe


def _install_hint(builder, reference, bounds, hint_values, unit):
    """Prefer the stronger validated hint, mapping original decisions into compact variables."""
    income = None
    if hint_values is not None:
        if not reference.feasible(hint_values):
            raise ValueError("Previous Attila layout violates the original model")
        income = float(reference.profit @ hint_values) + reference.offset
    prepared = bounds is not None and bounds.hint_values is not None
    model = builder.model
    if prepared and (income is None or bounds.report["hint_objective"] * float(unit) >= income):
        model.clear_hints()
        for index, value in bounds.hint_values.items():
            model.add_hint(model.get_int_var_from_proto_index(index), value)
    elif hint_values is not None:
        model.clear_hints()
        for index, variable in builder.variables.items():
            model.add_hint(variable, round(hint_values[index]))
    return income


def _native_solve(solver, model, observer, bounds, cancellation):
    try:
        return solve_with_progress(solver, model, on_search=observer, cancellation=cancellation)
    except Cancelled:
        if bounds is None or bounds.hint_values is None:
            raise
        return cp_model.UNKNOWN


def _retain_seed(values, objective, status, bounds):
    if bounds is None or bounds.hint_values is None:
        return values, objective, status
    seed = bounds.report["hint_objective"]
    if status == cp_model.INFEASIBLE or (status == cp_model.OPTIMAL and seed > objective + 1e-5):
        raise AssertionError("Native proof contradicts the validated provincial seed")
    if status not in (cp_model.UNKNOWN, cp_model.FEASIBLE, cp_model.OPTIMAL):
        return values, objective, status
    if objective is None or seed > objective:
        return bounds.hint_values, seed, cp_model.FEASIBLE
    return values, objective, status


def _selection(solver, model, status, bounds, observed):
    values, objective, bound = None, None, None
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        values = {
            index: solver.value(model.get_int_var_from_proto_index(index))
            for index in range(len(model.proto.variables))
        }
        objective, bound = solver.objective_value, solver.best_objective_bound
    upper = [value for value in (bound, *observed) if value is not None]
    if bounds is not None and bounds.upper_bound is not None:
        upper.append(bounds.upper_bound)
    bound = min(upper, default=None)
    values, objective, status = _retain_seed(values, objective, status, bounds)
    if objective is not None and bound is not None and bound < objective - 1e-5:
        raise AssertionError("Joint upper bound is below a validated candidate")
    return values, objective, None if status == cp_model.INFEASIBLE else bound, status


def _restore(builder, reference, assignment, native_objective, unit):
    values = [0.0] * len(reference.names)
    for index, variable in builder.variables.items():
        values[index] = assignment[variable.index]
    # The expanded matrix is the unchanged independent constraint reference.
    for index, terms in builder.products.items():
        values[index] = int(all(values[i] for i in terms))
    original = float(reference.profit @ values) + reference.offset
    if abs(native_objective * float(unit) - original) > 1e-5:
        raise AssertionError("Compact and reference income objectives disagree")
    if not reference.feasible(values):
        raise AssertionError("Compact assignment fails the original reference constraints")
    return values


def solve(
    builder,
    reference,
    unit,
    *,
    seconds,
    seed,
    workers,
    started,
    on_search=None,
    on_model=None,
    on_phase=None,
    cancellation=None,
    hint_values=None,
):
    """Keep certified native-unit bounds and validated candidates on cancellation."""
    bound_start = perf_counter()
    bounds = _strengthen(builder, seconds, seed, workers, started, cancellation, on_phase)
    bound_seconds = perf_counter() - bound_start
    model = builder.model
    incumbent_income = _install_hint(builder, reference, bounds, hint_values, unit)
    error = model.validate()
    if error:
        raise ValueError(error)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.linearization_level = 2
    if seconds is not None:
        solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - started))
    stats = {
        "formulation": "factored_income",
        "variables": len(model.proto.variables),
        "constraints": len(model.proto.constraints),
        "reference_variables": len(reference.names),
        "reference_constraints": len(reference.lower),
        "income_groups": builder.income_groups,
    }
    if getattr(builder, "native_products", False):
        stats["product_encoding"] = "native"
    if on_phase is not None:
        on_phase(
            "Searching the complete joint model" if bounds is not None else "Solving and validating"
        )
    if on_model is not None:
        on_model(stats)
    observed = []
    observer = _observe(on_search, bounds, observed, unit, incumbent_income)
    search_start = perf_counter()
    native_status = _native_solve(solver, model, observer, bounds, cancellation)
    search_seconds = perf_counter() - search_start
    values, objective, bound, status = _selection(solver, model, native_status, bounds, observed)
    if bounds is not None:
        stats["joint_bound_search"] = bounds.report
    if native_status != status:
        stats["native_status"] = solver.status_name(native_status)
    return Result(
        "cp-sat",
        solver.status_name(status),
        values=None if values is None else _restore(builder, reference, values, objective, unit),
        bound=None if bound is None else bound * float(unit),
        workers=workers,
        model_stats=stats,
        timings={
            "model_conversion_seconds": search_start - started - bound_seconds,
            "bound_strengthening_seconds": bound_seconds,
            "search_seconds": search_seconds,
        },
    )
