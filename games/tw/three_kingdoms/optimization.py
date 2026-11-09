"""Exact CP-SAT/HiGHS execution with independent economic verification."""

from math import isfinite
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.highs_backend import solve_highs
from games.tw.resources import resolve_workers
from games.tw.search_progress import solve_with_progress

SCALE = 1_000_000


def exact_integer(value):
    if not isfinite(value) or int(value) != value:
        raise ValueError("Three Kingdoms compilation requires finite integer coefficients")
    return int(value)


def native_model(proto):
    model = cp_model.CpModel()
    variables = []
    for variable in proto.variable:
        if not variable.is_integer:
            raise ValueError("Three Kingdoms compilation requires integer variables")
        variables.append(
            model.new_int_var(
                exact_integer(variable.lower_bound),
                exact_integer(variable.upper_bound),
                variable.name,
            )
        )
    for row in proto.constraint:
        expression = sum(
            exact_integer(c) * variables[i]
            for i, c in zip(row.var_index, row.coefficient, strict=True)
        )
        if isfinite(row.lower_bound):
            model.add(expression >= exact_integer(row.lower_bound))
        if isfinite(row.upper_bound):
            model.add(expression <= exact_integer(row.upper_bound))
    model.maximize(
        exact_integer(proto.objective_offset)
        + sum(
            exact_integer(v.objective_coefficient) * x
            for v, x in zip(proto.variable, variables, strict=True)
        )
    )
    return model, variables


def cpsat(proto, seconds, workers, *, on_search=None, on_model=None, cancellation=None):
    converted = perf_counter()
    model, variables = native_model(proto)
    stats = {
        "formulation": "linearized_income",
        "variables": len(model.proto.variables),
        "constraints": len(model.proto.constraints),
    }
    if on_model is not None:
        on_model(stats)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    if seconds is not None:
        solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - converted))
    started = perf_counter()
    status = solve_with_progress(
        solver, model, on_search=on_search, scale=1 / SCALE, cancellation=cancellation
    )
    feasible = status in {cp_model.FEASIBLE, cp_model.OPTIMAL}
    return {
        "algorithm": "cp-sat",
        "status": solver.status_name(status),
        "objective": solver.objective_value if feasible else None,
        "bound": solver.best_objective_bound if feasible else None,
        "values": [solver.value(v) for v in variables] if feasible else None,
        "detail": solver.solution_info(),
        "model_stats": stats,
        "timings": {
            "model_conversion_seconds": started - converted,
            "search_seconds": perf_counter() - started,
        },
    }


def optimize(
    economy, algorithm, seconds, workers, *, on_search=None, on_model=None, cancellation=None
):
    if algorithm not in {"cp-sat", "highs"}:
        raise ValueError("Choose cp-sat or highs")
    if seconds is not None and (not isfinite(seconds) or seconds <= 0):
        raise ValueError("Time limit must be positive and finite")
    workers = resolve_workers(workers)
    if cancellation is not None:
        cancellation.checkpoint()
    started = perf_counter()
    proto = economy.compile()
    compiled = perf_counter()
    stats = {
        "formulation": "linearized_income",
        "variables": len(proto.variable),
        "constraints": len(proto.constraint),
    }
    remaining = None if seconds is None else max(0.001, seconds - (compiled - started))
    if algorithm == "cp-sat":
        result = cpsat(
            proto,
            remaining,
            workers,
            on_search=on_search,
            on_model=on_model,
            cancellation=cancellation,
        )
    else:
        if on_model is not None:
            on_model(stats)
        result = solve_highs(proto, seconds=remaining, workers=workers, cancellation=cancellation)
    values = result.pop("values")
    for field in ("objective", "bound"):
        if result[field] is not None:
            result[field] /= SCALE
    result.update(seconds=perf_counter() - started, workers=workers)
    result.setdefault("model_stats", stats)
    result["timings"]["preparation_seconds"] = compiled - started
    report = {
        "scenario": economy.scenario.to_dict(),
        "solver": result,
        "exclusions": dict(economy.exclusions),
        "limitations": list(economy.limitations),
    }
    if values is not None:
        report.update(verified_economics(economy, proto, values, result["objective"]))
    return report


def verified_economics(economy, proto, values, objective):
    layout = {county: [] for county in economy.candidates}
    for variable, value in zip(proto.variable, values, strict=True):
        if value > 0.5 and variable.name in economy.decisions:
            county, building = economy.decisions[variable.name]
            layout[county].append(building)
    economics = economy.evaluate(layout)
    if abs(economics["domestic_income"] - objective) > 1e-5:
        raise AssertionError("Independent Three Kingdoms economics disagrees with solver")
    return economics
