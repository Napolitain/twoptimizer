"""Compare optional requirements without confusing incumbents with proven losses."""

from collections import Counter
from dataclasses import asdict, replace
from math import isfinite

from twoptimizer.models import BuildingSelection, CaseResult, RunConfig

TOLERANCE = 1e-5
SCOPE = (
    "Removes optional required/forbidden buildings and minimum religious influence only; "
    "faith, Nanban contact, advanced campaign inputs and all other settings are preserved. "
    "Rome buildings exposed by requirements remain available in the relaxed baseline."
)


def has_requirements(config: RunConfig) -> bool:
    options = config.constraints
    return bool(
        options.required_buildings
        or options.forbidden_buildings
        or options.minimum_religious_influence is not None
    )


def baseline_config(config: RunConfig) -> RunConfig:
    candidates = config.comparison_candidates
    if config.game == "rome2":
        candidates = tuple(sorted(set(candidates) | set(config.constraints.required_buildings)))
    return replace(
        config,
        compare_constraints=False,
        comparison_candidates=candidates,
        constraints=replace(
            config.constraints,
            required_buildings=(),
            forbidden_buildings=(),
            minimum_religious_influence=None,
        ),
    )


def _number(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value):
        return float(value)
    return None


def _income(result: CaseResult) -> float | None:
    if result.solver.status not in {"OPTIMAL", "FEASIBLE"} or result.solver.details.get(
        "relaxation", False
    ):
        return None
    return _number(result.income)


def _upper_bound(result: CaseResult, income: float) -> float | None:
    if result.solver.status == "OPTIMAL":
        return income
    upper = _number(result.solver.bound)
    return None if upper is None else max(income, upper)


def _incompatibility(baseline: CaseResult, constrained: CaseResult) -> str | None:
    if baseline.request != baseline_config(constrained.request):
        return (
            "The baseline does not describe the same scenario with optional requirements removed."
        )
    if (
        baseline.source_files
        and constrained.source_files
        and baseline.source_files != constrained.source_files
    ):
        return "The results use different model or data snapshots."
    for result in (baseline, constrained):
        income, bound = _income(result), _number(result.solver.bound)
        if income is not None and bound is not None and bound < income - TOLERANCE:
            return "A solver upper bound is below its validated income; loss cannot be certified."
    return None


def _added_buildings(
    previous: list[BuildingSelection], current: list[BuildingSelection]
) -> list[dict]:
    remaining = Counter((building.region, building.id) for building in previous)
    added = []
    for building in sorted(current, key=lambda row: (row.region, row.id, row.building)):
        identity = (building.region, building.id)
        if remaining[identity]:
            remaining[identity] -= 1
        else:
            added.append(asdict(building))
    return added


def _report(baseline: CaseResult, constrained: CaseResult) -> dict:
    return {
        "status": "unavailable",
        "scope": SCOPE,
        "reason": None,
        "baseline_status": baseline.solver.status,
        "constrained_status": constrained.solver.status,
        "baseline_income": _income(baseline),
        "constrained_income": _income(constrained),
        "baseline_bound": _number(baseline.solver.bound),
        "constrained_bound": _number(constrained.solver.bound),
        "baseline_gap_percent": _number(baseline.gap_percent),
        "constrained_gap_percent": _number(constrained.gap_percent),
        "observed_income_difference": None,
        "cost_lower": None,
        "cost_upper": None,
        "exact_cost": None,
        "percent": None,
        "added_buildings": [],
        "removed_buildings": [],
    }


def compare_results(baseline: CaseResult, constrained: CaseResult) -> dict:
    """Bound optimum income loss for a nested pair of maximization problems.

    Each validated incumbent is a lower bound. The constrained incumbent also
    bounds the baseline from below, and the baseline upper bound applies to the
    constrained problem. A negative incumbent difference is retained as an
    observation but never becomes a negative certified cost.
    """
    report = _report(baseline, constrained)
    if reason := _incompatibility(baseline, constrained):
        return {**report, "reason": reason}
    base_income, required_income = _income(baseline), _income(constrained)
    if base_income is None or required_income is None:
        return {
            **report,
            "reason": "Both runs need validated feasible layouts to compare income loss.",
        }
    upper_base = _upper_bound(baseline, base_income)
    upper_required = _upper_bound(constrained, required_income)
    if upper_base is not None and required_income > upper_base + TOLERANCE:
        return {
            **report,
            "reason": (
                "Constrained income exceeds the baseline upper bound; results are inconsistent."
            ),
        }
    if upper_base is not None:
        upper_base = max(upper_base, required_income)
    report.update(
        observed_income_difference=base_income - required_income,
        added_buildings=_added_buildings(baseline.buildings, constrained.buildings),
        removed_buildings=_added_buildings(constrained.buildings, baseline.buildings),
    )
    report.update(_loss_bounds(base_income, required_income, upper_base, upper_required))
    if baseline.solver.status == constrained.solver.status == "OPTIMAL":
        exact = max(0.0, base_income - required_income)
        report.update(
            status="exact",
            reason="Both optimal incomes are proved for the stated scenarios.",
            exact_cost=exact,
            cost_lower=exact,
            cost_upper=exact,
            percent=100 * exact / base_income if base_income > 0 else None,
        )
    return report


def _loss_bounds(base_income, required_income, upper_base, upper_required):
    known_upper = [upper for upper in (upper_base, upper_required) if upper is not None]
    required_upper = min(known_upper) if known_upper else None
    return {
        "status": "bounded",
        "reason": "Incumbent income difference is observed; optimal income loss remains unproved.",
        "cost_lower": (
            max(0.0, max(base_income, required_income) - required_upper)
            if required_upper is not None
            else 0.0
        ),
        "cost_upper": max(0.0, upper_base - required_income) if upper_base is not None else None,
    }
