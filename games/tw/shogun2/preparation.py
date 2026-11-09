"""Bounded conservative local layouts used only as hints for the original holding."""

from dataclasses import replace
from time import perf_counter

from games.tw.shogun2.effects import unique_key


def _allowance(economy, seconds):
    if len(economy.provinces) < 4:
        return 0, "Fewer than four provinces"
    if economy.scenario.required_buildings:
        return 0, "Global building requirements need complete-model search"
    if seconds is not None and seconds < 8:
        return 0, "Short remaining search allowance"
    return min(5.0, seconds * 0.2) if seconds is not None else 5.0, None


def _local(economy, province):
    from games.tw.shogun2.model import Economy

    forbidden = set(economy.scenario.forbidden_buildings) | {
        key for key, building in economy.catalog["buildings"].items() if unique_key(building)
    }
    scenario = replace(
        economy.scenario,
        provinces=(province,),
        forbidden_buildings=tuple(sorted(forbidden)),
    )
    local = Economy(scenario, economy.catalog, economy.rules)
    # Independent cases must not each spend the same positive faction food credit.
    # This deliberately strengthens the preparatory model; the final model is unchanged.
    local.arts["food"] = min(0, local.arts["food"])
    return local


def prepare(economy, seconds, cancellation=None, on_phase=None):
    allowance, reason = _allowance(economy, seconds)
    if not allowance:
        return None, {"status": "skipped", "reason": reason}
    started = perf_counter()
    deadline = started + allowance
    layout = {}
    report = {
        "status": "unfinished",
        "provinces": len(economy.provinces),
        "completed": 0,
        "allowance_seconds": allowance,
        "unique_buildings": "reserved for joint search",
        "positive_arts_food_credit": 0,
    }
    for number, province in enumerate(economy.scenario.provinces):
        if cancellation is not None:
            cancellation.checkpoint()
        remaining = deadline - perf_counter()
        if remaining <= 0:
            break
        if on_phase is not None:
            on_phase(f"Preparing compatible Shogun layout {number + 1}/{len(economy.provinces)}")
        local = _local(economy, province)
        result = local.optimize(
            "cp-sat",
            seconds=min(0.25, remaining / (len(economy.provinces) - number)),
            workers=1,
            cancellation=cancellation,
        )
        if "provinces" not in result:
            report["reason"] = "A conservative local search returned no layout"
            break
        layout[province.id] = result["provinces"][province.id]["buildings"]
        report["completed"] += 1
    report["seconds"] = perf_counter() - started
    if len(layout) != len(economy.provinces):
        return None, report
    try:
        economics = economy.evaluate(layout)
    except ValueError as error:
        report.update(status="rejected", reason=str(error))
        return None, report
    report.update(status="validated", income=economics["domestic_tax_income"])
    return {"scenario": economy.scenario.to_dict(), **economics}, report
