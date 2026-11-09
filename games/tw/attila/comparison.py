"""Comparison orchestration with named search settings and stable report output."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import TYPE_CHECKING, Any

from games.optimization.competition import BinaryModel, Result, solve

if TYPE_CHECKING:
    from games.tw.attila.economy import Economy


@dataclass(frozen=True, slots=True, kw_only=True)
class ComparisonOptions:
    algorithms: tuple[str, ...] = ("cp-sat",)
    seconds: float | None = None
    seed: int = 0
    objective: str = "income"
    workers: int | None = None


def compare_model(
    model: BinaryModel,
    options: ComparisonOptions,
    economy: Economy | None = None,
) -> dict[str, Any]:
    results = [
        solve(
            model,
            name,
            options.seconds,
            options.seed,
            workers=options.workers,
        )
        for name in options.algorithms
    ]
    return report_results(model, results, options, economy)


def report_results(
    model: BinaryModel,
    results: list[Result],
    options: ComparisonOptions,
    economy: Economy | None = None,
) -> dict[str, Any]:
    """Independently evaluate fresh or revalidated cached solver results."""
    feasible = [r.objective for r in results if not r.relaxation and r.objective is not None]
    best = max(feasible, default=None)
    bounds = [r.bound for r in results if r.bound is not None and isfinite(r.bound)]
    upper = min(bounds, default=None)
    if upper is not None and best is not None and upper < best - 1e-5:
        raise RuntimeError("Reported upper bound is below a validated feasible solution")
    rows = []
    for result in results:
        row = asdict(result)
        values = row.pop("values")
        row["selected"] = (
            [
                model.names[i]
                for i, value in enumerate(values)
                if value > 0.5 and not model.names[i].startswith("__")
            ]
            if values is not None and not result.relaxation
            else None
        )
        row["fractional_values"] = (
            dict(zip(model.names, values, strict=False))
            if values is not None and result.relaxation
            else None
        )
        row["gap_to_best_percent"] = (
            100 * max(0, best - result.objective) / max(1, abs(best))
            if best is not None and result.objective is not None and not result.relaxation
            else None
        )
        row["gap_to_bound_percent"] = (
            100 * max(0, upper - result.objective) / max(1, abs(upper))
            if upper is not None and result.objective is not None and not result.relaxation
            else None
        )
        if economy is not None and row["selected"] is not None:
            row["layout"] = economy.evaluate_layout(set(row["selected"]), options.objective)
            assert result.objective is not None
            if abs(row["layout"]["objective"] - result.objective) > 1e-5:
                raise RuntimeError("Layout evaluator disagrees with the compiled objective")
        rows.append(row)
    return {"best_feasible": best, "upper_bound": upper, "results": rows}
