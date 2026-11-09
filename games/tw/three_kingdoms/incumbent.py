"""Validate reusable layouts separately from native optimization certificates."""

from hashlib import sha256
from math import isfinite


def fingerprint(proto):
    return sha256(proto.SerializeToString(deterministic=True)).hexdigest()


def layout_from(report):
    return {
        county: list(row["buildings"])
        for commandery in report.get("commanderies", {}).values()
        for county, row in commandery["counties"].items()
    }


def validated(economy, report):
    if report is None:
        return None
    layout = layout_from(report)
    economics = economy.evaluate(layout)
    income = report.get("domestic_income")
    if income is None or not isfinite(income):
        raise ValueError("Three Kingdoms incumbent needs finite income")
    if abs(economics["domestic_income"] - income) > 1e-5:
        raise ValueError("Three Kingdoms incumbent disagrees with independent economics")
    return economics


def trusted_bound(report, identity):
    if report is None or report.get("model_fingerprint") != identity:
        return None
    bound = report.get("solver", {}).get("bound")
    return bound if bound is not None and isfinite(bound) else None


def hints(economy, economics):
    if economics is None:
        return {}
    layout = layout_from(economics)
    return {
        name: int(building in layout[county])
        for name, (county, building) in economy.decisions.items()
    }


def retain(result, economics, seed, bound):
    """Keep a validated candidate without promoting an unfinished native proof."""
    native = result["status"]
    income = None if economics is None else economics["domestic_income"]
    if seed is not None:
        if native == "INFEASIBLE" or (
            native == "OPTIMAL" and (income is None or seed["domestic_income"] > income + 1e-5)
        ):
            raise AssertionError("Native proof contradicts the validated starting layout")
        if native in {"OPTIMAL", "FEASIBLE", "UNKNOWN"} and (
            income is None or seed["domestic_income"] > income + 1e-5
        ):
            economics = seed
            result.update(status="FEASIBLE", objective=seed["domestic_income"])
    if result["status"] in {"OPTIMAL", "FEASIBLE", "UNKNOWN"}:
        result["bound"] = min(
            (value for value in (bound, result["bound"]) if value is not None), default=None
        )
    if (
        economics is not None
        and result["bound"] is not None
        and result["bound"] < economics["domestic_income"] - 1e-5
    ):
        raise AssertionError("Upper bound is below independently validated income")
    if result["status"] != native:
        result["native_status"] = native
    return economics
