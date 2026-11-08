"""Prepare and evaluate Attila cases independently of interface and execution."""

from __future__ import annotations

from dataclasses import fields
from math import isfinite
from typing import TYPE_CHECKING, Any

from games.tw.comparison import ComparisonOptions, report_results
from games.tw.competition import Result
from games.tw.immutable import thaw
from twoptimizer.attila_session import AttilaSession
from twoptimizer.models import BuildingSelection, CaseResult, EngineResult, RunConfig
from twoptimizer.progress import PhaseTimer

if TYPE_CHECKING:
    from twoptimizer.session import RunSession


def solve_attila(
    config: RunConfig, phase: PhaseTimer, session: RunSession | None = None
) -> EngineResult:
    state = session.attila if session is not None else AttilaSession()
    phase("build_model_seconds", "Building income model")
    prepared = state.prepare(config)
    snapshot = prepared.snapshot
    economy = snapshot.economy
    assert economy is not None
    phase("solve_and_check_seconds", "Solving and validating")
    result, fingerprint, reused = state.solve(config, prepared)
    row = report_results(
        snapshot.model, [result], ComparisonOptions(algorithms=(config.algorithm,)), economy
    )["results"][0]
    phase("prepare_result_seconds", "Preparing result")
    raw = {
        **row,
        "build_seconds": snapshot.build_seconds,
        "omitted_effects": thaw(sorted(set(economy.omitted))),
        "signature": fingerprint,
        "proof_reused": reused,
        "province_ids": list(prepared.province_ids),
        "province_names": list(prepared.province_names),
        "adjacency": thaw(economy.adjacency),
        "solver": {
            key: row[key]
            for key in (
                "algorithm",
                "status",
                "seconds",
                "objective",
                "bound",
                "timings",
                "workers",
                "model_stats",
                "relaxation",
                "detail",
            )
        },
        "model_size": {
            "variables": len(snapshot.model.names),
            "constraints": snapshot.model.matrix.shape[0],
            "constraint_storage_bytes": snapshot.model.matrix.nbytes,
            "cp_sat": result.model_stats,
        },
    }
    buildings = [
        BuildingSelection(building.region.print_name, building.print_name, building.name)
        for key in row.get("selected") or []
        for building in (economy.by_id[key],)
    ]
    layout = row.get("layout") or {}
    metrics = {
        "food_surplus": sum(layout.get("province_food", {}).values()) if layout else None,
        "public_order": min(layout.get("public_order", {}).values(), default=None),
    }
    income = layout["finances"]["total"]["net_income"] if layout else None
    return EngineResult(raw, income, buildings, metrics)


def comparison_report(cases: list[CaseResult], *, joint: bool) -> dict[str, Any]:
    """Serialize the established Attila comparison schema from shared results."""
    first = cases[0]
    rows = [_comparison_row(case.raw) for case in cases]
    feasible = [r["objective"] for r in rows if not r["relaxation"] and r["objective"] is not None]
    best = max(feasible, default=None)
    bounds = [r["bound"] for r in rows if r["bound"] is not None and isfinite(r["bound"])]
    upper = min(bounds, default=None)
    if upper is not None and best is not None and upper < best - 1e-5:
        raise RuntimeError("Reported upper bound is below a validated feasible solution")
    for row in rows:
        row["gap_to_best_percent"] = _gap(row, best)
        row["gap_to_bound_percent"] = _gap(row, upper)
    return {
        "province": "joint" if joint else first.raw["province_ids"][0],
        "province_name": ", ".join(first.raw["province_names"]),
        "fertility": first.request.fertility,
        "variables": first.raw["model_size"]["variables"],
        "constraints": first.raw["model_size"]["constraints"],
        "build_seconds": first.raw["build_seconds"],
        "omitted_effects": first.raw["omitted_effects"],
        "best_feasible": best,
        "upper_bound": upper,
        "results": rows,
    }


def _comparison_row(raw: dict[str, Any]) -> dict[str, Any]:
    keys = {field.name for field in fields(Result)} - {"values"}
    keys |= {
        "selected",
        "fractional_values",
        "gap_to_best_percent",
        "gap_to_bound_percent",
        "layout",
    }
    return {key: value for key, value in raw.items() if key in keys}


def _gap(row, target):
    if target is None or row["objective"] is None or row["relaxation"]:
        return None
    return 100 * max(0, target - row["objective"]) / max(1, abs(target))


def faction_report(case: CaseResult) -> dict[str, Any]:
    """Serialize the established faction comparison row."""
    return {
        "province": ", ".join(case.raw["province_names"]),
        "signature": case.raw["signature"],
        "status": case.solver.status,
        "income": case.income,
        "bound": case.solver.bound,
        "proof_reused": case.raw["proof_reused"],
        "solve_seconds": case.solver.seconds,
        "build_seconds": case.raw["build_seconds"],
        "selected": sorted(case.raw["selected"]) if case.raw["selected"] is not None else None,
        "layout": case.raw.get("layout"),
        "omitted_effects": case.raw["omitted_effects"],
    }
