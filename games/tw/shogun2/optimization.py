"""Execute native search while retaining independently checked starting layouts."""

from dataclasses import asdict
from math import isfinite
from time import perf_counter

from games.tw.cancellation import Cancelled
from games.tw.competition import ALGORITHMS, Result, solve
from games.tw.shogun2.preparation import prepare


def layout_values(economy, layout):
    """Reconstruct every Boolean product and validate the original binary model."""
    economics = economy.evaluate(layout)
    selected = {
        name: int(building in layout[province])
        for name, (province, building) in economy.decision_names.items()
    }
    selected.update(
        {
            name: selected[left] * selected[right]
            for name, (left, right) in economy.product_factors.items()
        }
    )
    values = [selected[name] for name in economy.binary.names]
    if not economy.binary.feasible(values):
        raise ValueError("Initial Shogun layout violates the compiled model")
    income = float(economy.binary.profit @ values) + economy.binary.offset
    if abs(income - economics["domestic_tax_income"]) > 1e-5:
        raise AssertionError("Initial Shogun layout income differs from the compiled objective")
    return values, economics


def _previous(economy, incumbent):
    if incumbent is None:
        return None, None
    layout = {key: row["buildings"] for key, row in incumbent["provinces"].items()}
    # Trust neither the supplied objective nor any certificate; recalculate the layout.
    return layout_values(economy, layout)


def _starting_layout(economy, incumbent, seconds, cancellation, on_phase):
    if incumbent is not None:
        return incumbent, {"status": "cached", "seconds": 0.0}
    return prepare(economy, seconds, cancellation, on_phase)


def _previous_bound(incumbent, fingerprint):
    if incumbent is None or incumbent.get("model_fingerprint") != fingerprint:
        return None
    value = incumbent.get("solver", {}).get("bound")
    return value if type(value) in {int, float} and isfinite(value) else None


def _merge_bound(solver, previous_bound):
    bounds = [value for value in (solver["bound"], previous_bound) if value is not None]
    solver["bound"] = min(bounds, default=None)
    if (
        solver["bound"] is not None
        and solver["objective"] is not None
        and solver["bound"] < solver["objective"] - 1e-5
    ):
        raise AssertionError("Stored Shogun bound contradicts a validated native layout")


def _observer(callback, previous, bound, prepared):
    if callback is None or previous is None:
        return callback
    income = previous["domestic_tax_income"]
    callback(income, bound, prepared)

    def progress(objective, upper, elapsed):
        retained = max(income, objective) if objective is not None else income
        bounds = [value for value in (bound, upper) if value is not None]
        callback(retained, min(bounds, default=None), prepared + elapsed)

    return progress


def _evaluated_result(economy, result):
    if result.values is None:
        return None
    layout = {p: [] for p in economy.provinces}
    for name, value in zip(economy.binary.names, result.values, strict=True):
        if value > 0.5 and name in economy.decision_names:
            province, building = economy.decision_names[name]
            layout[province].append(building)
    economics = economy.evaluate(layout)
    if abs(economics["domestic_tax_income"] - result.objective) > 1e-5:
        raise AssertionError("Independent tax evaluation disagrees with solver")
    return economics


def _retain(solver, economics, previous):
    if previous is None:
        return economics
    income = previous["domestic_tax_income"]
    if solver["status"] == "INFEASIBLE" or (
        solver["bound"] is not None and solver["bound"] < income - 1e-5
    ):
        raise AssertionError("Native proof contradicts the validated previous Shogun layout")
    objective = solver["objective"]
    if solver["status"] == "OPTIMAL" and (objective is None or objective < income - 1e-5):
        raise AssertionError("Native optimum is below the validated previous Shogun layout")
    if solver["status"] in {"UNKNOWN", "FEASIBLE"} and (objective is None or income > objective):
        solver.update(
            native_status=solver["status"],
            status="FEASIBLE",
            objective=income,
            incumbent_retained=True,
        )
        return previous
    return economics


def _validate_options(algorithm, seconds, native_products):
    if algorithm not in ALGORITHMS:
        raise ValueError("Choose cp-sat or highs")
    if seconds is not None and (seconds <= 0 or not isfinite(seconds)):
        raise ValueError("Time limit must be positive and finite")
    if not isinstance(native_products, bool) or (native_products and algorithm != "cp-sat"):
        raise ValueError("Native products require a boolean CP-SAT selection")


def optimize(
    economy,
    algorithm,
    seconds,
    workers,
    *,
    on_search=None,
    on_model=None,
    cancellation=None,
    incumbent=None,
    on_phase=None,
    native_products=False,
):
    _validate_options(algorithm, seconds, native_products)
    if cancellation is not None and incumbent is None:
        cancellation.checkpoint()
    started = perf_counter()
    binary = economy.compile()
    if native_products:
        from games.tw.shogun2.native_products import NativeProducts

        binary.cp_sat_plan = NativeProducts.from_economy(economy)
    fingerprint = binary.fingerprint()
    remaining = None if seconds is None else max(0.001, seconds - (perf_counter() - started))
    incumbent, preparation = _starting_layout(economy, incumbent, remaining, cancellation, on_phase)
    values, previous = _previous(economy, incumbent)
    previous_bound = _previous_bound(incumbent, fingerprint)
    if on_phase is not None and previous is not None:
        on_phase("Using a validated Shogun starting layout before joint search")
    prepared = perf_counter()
    try:
        result = solve(
            binary,
            algorithm,
            seconds=None if seconds is None else max(0.001, seconds - (prepared - started)),
            workers=workers,
            on_search=_observer(on_search, previous, previous_bound, prepared - started),
            on_model=on_model,
            cancellation=cancellation,
            hint_values=values,
        )
    except Cancelled:
        if previous is None:
            raise
        result = Result(algorithm, "UNKNOWN", detail="Cancelled after validating a previous layout")
    economics = _evaluated_result(economy, result)
    solver = {key: value for key, value in asdict(result).items() if key != "values"}
    _merge_bound(solver, previous_bound)
    economics = _retain(solver, economics, previous)
    solver["seconds"] = perf_counter() - started
    solver["timings"]["preparation_seconds"] = prepared - started
    solver["warm_start"] = {"validated": previous is not None}
    solver["joint_preparation"] = preparation
    report = {
        "scenario": economy.scenario.to_dict(),
        "solver": solver,
        "model_fingerprint": fingerprint,
    }
    if economics is not None:
        report.update(economics)
    return report
