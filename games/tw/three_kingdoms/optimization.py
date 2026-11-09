"""Exact CP-SAT/HiGHS execution with independent economic verification."""

from math import ceil, isfinite
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.cancellation import Cancelled
from games.tw.highs_backend import solve_highs
from games.tw.resources import resolve_workers
from games.tw.search_progress import solve_with_progress
from games.tw.three_kingdoms import incumbent as starting_layout

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


def _observer(on_search, seed_income, known_bound, observed):
    def observe(objective, bound, elapsed):
        if bound is not None and isfinite(bound) and abs(bound) < 2**53:
            observed[:] = [min([ceil(bound), *observed])]
        if on_search is not None:
            best = max((v for v in (objective, seed_income) if v is not None), default=None)
            upper = min((v for v in (*observed, known_bound) if v is not None), default=None)
            on_search(
                None if best is None else best / SCALE,
                None if upper is None else upper / SCALE,
                elapsed,
            )

    return observe


def _solve_native(solver, model, observer, cancellation, seed_income):
    try:
        return solve_with_progress(solver, model, on_search=observer, cancellation=cancellation)
    except Cancelled:
        if seed_income is None:
            raise
        return cp_model.UNKNOWN


def _cp_problem(proto, products):
    if products is not None:
        from games.tw.three_kingdoms.native_products import lower

        problem = lower(proto, products)
        return problem.model, problem.variables, problem
    model, variables = native_model(proto)
    return model, variables, None


def _hints(model, variables, proto, incumbent, products):
    if products is not None:
        products.add_hints(incumbent or {})
        return
    for variable, source in zip(variables, proto.variable, strict=True):
        if incumbent is not None and source.name in incumbent:
            model.add_hint(variable, incumbent[source.name])


def cpsat(
    proto,
    seconds,
    workers,
    *,
    on_search=None,
    on_model=None,
    cancellation=None,
    incumbent=None,
    seed_income=None,
    known_bound=None,
    products=None,
):
    converted = perf_counter()
    model, variables, lowered = _cp_problem(proto, products)
    if error := model.validate():
        raise ValueError(error)
    _hints(model, variables, proto, incumbent, lowered)
    stats = (
        lowered.stats
        if lowered is not None
        else {
            "formulation": "linearized_income",
            "variables": len(model.proto.variables),
            "constraints": len(model.proto.constraints),
        }
    )
    if on_model is not None:
        on_model(stats)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = workers
    if seconds is not None:
        solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - converted))
    started = perf_counter()
    observed = []
    observer = _observer(on_search, seed_income, known_bound, observed)
    status = _solve_native(solver, model, observer, cancellation, seed_income)
    feasible = status in {cp_model.FEASIBLE, cp_model.OPTIMAL}
    bound = min([*observed, *([solver.best_objective_bound] if feasible else [])], default=None)
    values = None
    if feasible:
        values = (
            lowered.values(solver) if lowered is not None else [solver.value(v) for v in variables]
        )
    return {
        "algorithm": "cp-sat",
        "status": solver.status_name(status),
        "objective": solver.objective_value if feasible else None,
        "bound": bound,
        "values": values,
        "detail": "Search stopped without a native candidate"
        if status == cp_model.UNKNOWN
        else solver.solution_info(),
        "model_stats": stats,
        "timings": {
            "model_conversion_seconds": started - converted,
            "search_seconds": perf_counter() - started,
        },
    }


def _empty_result(algorithm):
    return {
        "algorithm": algorithm,
        "status": "UNKNOWN",
        "objective": None,
        "bound": None,
        "values": None,
        "timings": {},
    }


def _native(proto, algorithm, seconds, workers, seed, options):
    if algorithm == "cp-sat":
        return cpsat(proto, seconds, workers, **options)
    if options["on_model"] is not None:
        options["on_model"](
            {
                "formulation": "linearized_income",
                "variables": len(proto.variable),
                "constraints": len(proto.constraint),
            }
        )
    try:
        return solve_highs(
            proto,
            seconds=seconds,
            workers=workers,
            incumbent=options["incumbent"],
            cancellation=options["cancellation"],
        )
    except Cancelled:
        if seed is None:
            raise
        return _empty_result(algorithm)


def _prepare(economy, proto, seconds, workers, seed, observers):
    from games.tw.three_kingdoms.preparation import prepare

    return prepare(economy, proto, seconds, workers, seed, **observers)


def _validate_options(algorithm, seconds, native_products):
    if algorithm not in {"cp-sat", "highs"}:
        raise ValueError("Choose cp-sat or highs")
    if seconds is not None and (not isfinite(seconds) or seconds <= 0):
        raise ValueError("Time limit must be positive and finite")
    if native_products is not None and (
        not isinstance(native_products, bool) or (native_products and algorithm != "cp-sat")
    ):
        raise ValueError("Native products must be None or a CP-SAT-only boolean option")


def select_native_products(economy, algorithm, requested):
    """Use the measured large-holding path while keeping local preparation linear."""
    if requested is not None:
        return requested
    return algorithm == "cp-sat" and len(economy.scenario.commanderies) >= 8


def optimize(
    economy,
    algorithm,
    seconds,
    workers,
    *,
    on_search=None,
    on_model=None,
    on_phase=None,
    cancellation=None,
    incumbent=None,
    local_incumbents=None,
    native_products=None,
):
    _validate_options(algorithm, seconds, native_products)
    native_products = select_native_products(economy, algorithm, native_products)
    workers = resolve_workers(workers)
    if cancellation is not None and incumbent is None and not local_incumbents:
        cancellation.checkpoint()
    started = perf_counter()
    proto = economy.compile()
    compiled = perf_counter()
    identity = starting_layout.fingerprint(proto)
    seed = starting_layout.validated(economy, incumbent)
    old_bound = starting_layout.trusted_bound(incumbent, identity)
    stats = {
        "formulation": "linearized_income",
        "variables": len(proto.variable),
        "constraints": len(proto.constraint),
    }
    remaining = None if seconds is None else max(0.001, seconds - (compiled - started))
    strengthened, seed, bound, preparation = _prepare(
        economy,
        proto,
        remaining,
        workers,
        seed,
        {
            "cancellation": cancellation,
            "on_phase": on_phase,
            "on_search": on_search,
            "known_bound": old_bound,
            "local_incumbents": local_incumbents,
            "strengthen_bounds": algorithm == "cp-sat",
        },
    )
    bound = min(
        (v for v in (old_bound, None if bound is None else bound / SCALE) if v is not None),
        default=None,
    )
    if on_search is not None and seed is not None:
        on_search(seed["domestic_income"], bound, perf_counter() - started)
    if on_phase is not None:
        on_phase("Searching and validating the complete holding")
    remaining = None if seconds is None else max(0.001, seconds - (perf_counter() - started))
    result = _native(
        strengthened,
        algorithm,
        remaining,
        workers,
        seed,
        {
            "on_search": on_search,
            "on_model": on_model,
            "cancellation": cancellation,
            "incumbent": starting_layout.hints(economy, seed),
            "seed_income": None if seed is None else seed["domestic_income"] * SCALE,
            "known_bound": None if bound is None else bound * SCALE,
            "products": economy.products if native_products else None,
        },
    )
    values = result.pop("values")
    for field in ("objective", "bound"):
        if result[field] is not None:
            result[field] /= SCALE
    result.update(seconds=perf_counter() - started, workers=workers)
    result["seed_reused"] = incumbent is not None
    result.setdefault("model_stats", stats)
    result["timings"]["preparation_seconds"] = compiled - started
    result["timings"]["joint_preparation_seconds"] = preparation.get("seconds", 0.0)
    if len(economy.provinces) >= 4 or preparation.get("cached_local_cases"):
        result["joint_bound_search"] = preparation
    economics = (
        verified_economics(economy, proto, values, result["objective"])
        if values is not None
        else None
    )
    economics = starting_layout.retain(result, economics, seed, bound)
    report = {
        "scenario": economy.scenario.to_dict(),
        "solver": result,
        "exclusions": dict(economy.exclusions),
        "limitations": list(economy.limitations),
        "model_fingerprint": identity,
    }
    if economics is not None:
        report.update(economics)
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
