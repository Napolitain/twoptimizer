"""Bounded local starting layouts and conservative joint-model strengthening."""

from dataclasses import replace
from time import perf_counter

from games.optimization.budget import Budget
from games.optimization.cancellation import Cancelled
from games.tw.three_kingdoms.incumbent import layout_from, validated
from games.tw.three_kingdoms.joint_bounds import strengthen


def allowance(economy, seconds):
    if len(economy.provinces) < 4 or (seconds is not None and seconds < 20):
        return 0.0
    return 30.0 if seconds is None else min(30.0, seconds * 0.6)


def _cached_reports(economy, reports):
    cached = {}
    for report in reports or ():
        keys = tuple(report.get("commanderies", {}))
        if len(keys) != 1 or keys[0] not in economy.provinces:
            continue
        if report.get("scenario", {}).get("faction") != economy.scenario.faction:
            continue
        old = cached.get(keys[0])
        if old is None or report["domestic_income"] > old["domestic_income"]:
            cached[keys[0]] = report
    return cached


def _cached_seed(economy, cached):
    layout = {}
    for report in cached.values():
        layout.update(layout_from(report))
    try:
        return economy.evaluate(layout)
    except ValueError:
        return None


def _local_result(model, previous, seconds, workers, cancellation):
    if previous is not None:
        try:
            return validated(model, previous)
        except ValueError:
            pass
    return model.optimize(seconds=seconds, workers=workers, cancellation=cancellation)


def _local_seed(economy, budget, cancellation, on_phase, cached=None, workers=1):
    from games.tw.three_kingdoms.model import Economy

    layout = {}
    completed = 0
    provinces = economy.scenario.commanderies
    for number, province in enumerate(provinces, 1):
        if budget.remaining <= 0 or (cancellation is not None and cancellation.requested):
            break
        if on_phase is not None:
            on_phase(f"Preparing a starting layout: commandery {number}/{len(provinces)}")
        local = replace(
            economy.scenario,
            commanderies=(province,),
            adjacency=(),
            required_buildings=(),
            external_food=0,
        )
        model = Economy(local, economy.data)
        seconds = min(1.0, budget.remaining)
        try:
            result = _local_result(
                model, (cached or {}).get(province.id), seconds, workers, cancellation
            )
        except Cancelled:
            break
        if "commanderies" not in result:
            break
        layout.update(layout_from(result))
        completed += 1
    try:
        return economy.evaluate(layout), completed
    except ValueError:
        # Independent optima can duplicate unique buildings or fail a shared
        # requirement. They only become a candidate after joint validation.
        return None, completed


def prepare(
    economy,
    proto,
    seconds,
    workers,
    seed,
    *,
    cancellation=None,
    on_phase=None,
    on_search=None,
    known_bound=None,
    local_incumbents=None,
    strengthen_bounds=True,
):
    started = perf_counter()
    limit = allowance(economy, seconds)
    report = {"status": "skipped", "seed_reused": seed is not None}
    cached = _cached_reports(economy, local_incumbents)
    candidate = _cached_seed(economy, cached) if cached else None
    if candidate is not None and (
        seed is None or candidate["domestic_income"] > seed["domestic_income"]
    ):
        seed = candidate
        report.update(
            cached_local_cases=len(cached), seed_validated=True, seed_income=seed["domestic_income"]
        )
    if seed is not None and on_search is not None:
        on_search(seed["domestic_income"], known_bound, perf_counter() - started)
    if not limit or (cancellation is not None and cancellation.requested):
        return proto, seed, None, report
    if seed is None:
        seed, completed = _local_seed(
            economy, Budget(limit * 0.75), cancellation, on_phase, cached, workers
        )
        report.update(local_cases_completed=completed, seed_validated=seed is not None)
        if seed is not None and on_search is not None:
            on_search(seed["domestic_income"], known_bound, perf_counter() - started)
    report["seed_preparation_seconds"] = perf_counter() - started
    if not strengthen_bounds:
        report.update(status="seed_only", seconds=perf_counter() - started)
        if seed is not None:
            report["seed_income"] = seed["domestic_income"]
        return proto, seed, None, report
    remaining = max(0.0, limit - (perf_counter() - started))
    strengthened, bound, details = strengthen(
        proto, remaining, workers, cancellation=cancellation, on_phase=on_phase
    )
    report.update(details, seconds=perf_counter() - started)
    if seed is not None:
        report["seed_income"] = seed["domestic_income"]
    return strengthened, seed, bound, report
