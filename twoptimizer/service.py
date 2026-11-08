"""Shared case behavior, independent of foreground or subprocess execution."""

from collections.abc import Callable
from dataclasses import replace
from math import isfinite

from twoptimizer.catalog import NOTES, faction_name
from twoptimizer.constraint_comparison import baseline_config, compare_results, has_requirements
from twoptimizer.engines import solve_attila, solve_rome, solve_shogun
from twoptimizer.errors import ApplicationError, deserialize_error, serialize_error
from twoptimizer.holdings import map_context, province_label
from twoptimizer.models import CaseResult, RunConfig, SolverSummary
from twoptimizer.progress import ModelStats, PhaseTimer, ProgressEvent
from twoptimizer.provenance import source_files
from twoptimizer.requests import make_jobs as make_jobs
from twoptimizer.session import RunSession


def solve_case(
    config: RunConfig,
    progress: Callable[[ProgressEvent], None] | None = None,
    *,
    session: RunSession | None = None,
) -> CaseResult:
    phase = PhaseTimer(progress)
    phase("request_seconds", "Validating request")
    jobs, _ = make_jobs(config)
    if len(jobs) != 1:
        raise ApplicationError("A case must receive exactly one holding, faction and solver.")
    config = jobs[0]
    if config.compare_constraints and has_requirements(config):
        return _solve_comparison(config, progress, session)
    output = _solve_one(config, phase, session)
    if config.compare_constraints:
        output.raw["constraint_comparison"] = {
            "status": "unavailable",
            "reason": "No optional building or influence requirements were selected.",
        }
    return output


def _solve_one(config: RunConfig, phase: PhaseTimer, session: RunSession | None) -> CaseResult:
    phase("load_engine_seconds", "Loading engine and game data")
    adapter = {"rome2": solve_rome, "shogun2": solve_shogun, "attila": solve_attila}[config.game]
    try:
        result = adapter(config, phase, session)
    except (ValueError, TypeError) as error:
        raise ApplicationError(str(error)) from error
    result.raw["model_complexity"] = [stats.to_dict() for stats in phase.models]
    result.raw["map_context"] = map_context(config)
    income = result.income
    solver = SolverSummary.from_dict(result.raw["solver"])
    bound = solver.bound
    gap = (
        100 * max(0, bound - income) / max(1, abs(bound))
        if income is not None and bound is not None and isfinite(bound)
        else None
    )
    if result.objectives:
        gap = result.objectives[0].gap_percent
    output = CaseResult(
        request=config,
        faction=faction_name(config.game, config.faction),
        province=province_label(config),
        solver=solver,
        income=income,
        gap_percent=gap,
        metrics=result.metrics,
        buildings=sorted(result.buildings, key=lambda b: (b.region, b.building)),
        assumptions=NOTES[config.game],
        source_files=source_files(config.game),
        raw=result.raw,
        timings=phase.timings,
        objectives=result.objectives,
    )
    if session is not None:
        session.record(output)
    phase()
    return output


def _solve_comparison(config, progress, session):
    baseline = _comparison_side(baseline_config(config), "Without requirements", progress, session)
    constrained = _comparison_side(
        replace(config, compare_constraints=False), "With requirements", progress, session
    )
    if constrained.solver.status == "ERROR":
        raise deserialize_error(constrained.raw)
    summary = compare_results(baseline, constrained)
    summary["baseline"] = baseline.to_dict()
    summary["constrained_timings"] = constrained.timings.copy()
    summary["scope"] = (
        "Removes only optional required/forbidden buildings and minimum religious influence. "
        "Faith, Nanban contact, campaign rules and other inputs are retained. "
        "Each solve receives the configured time limit; building differences can include ties."
    )
    timings = {
        key: baseline.timings.get(key, 0) + constrained.timings.get(key, 0)
        for key in baseline.timings.keys() | constrained.timings.keys()
    }
    models = [
        {**model, "label": f"{label}: {model['label']}"}
        for label, result in (
            ("Without requirements", baseline),
            ("With requirements", constrained),
        )
        for model in result.raw.get("model_complexity", ())
    ]
    return replace(
        constrained,
        request=config,
        timings=timings,
        raw={**constrained.raw, "constraint_comparison": summary, "model_complexity": models},
    )


def _comparison_side(config, label, progress, session):
    def relay(event):
        if progress is not None:
            progress(
                replace(event, label=f"{label}: {event.label}")
                if isinstance(event, ModelStats)
                else f"{label}: {event}"
            )

    try:
        return solve_case(config, relay, session=session)
    except ApplicationError as error:
        return error_result(config, error)


def error_result(config: RunConfig, error: Exception) -> CaseResult:
    """Retain a failed case in a batch with the same result schema as successes."""
    return CaseResult(
        request=config,
        faction=config.faction,
        province=", ".join(config.holdings),
        solver=SolverSummary(config.algorithm, "ERROR", 0, None, None),
        income=None,
        gap_percent=None,
        metrics={},
        buildings=[],
        assumptions=NOTES.get(config.game, ""),
        source_files={},
        raw=serialize_error(error),
        timings={},
    )
