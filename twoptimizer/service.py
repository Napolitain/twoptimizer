"""Shared case behavior, independent of foreground or subprocess execution."""

from collections.abc import Callable
from dataclasses import replace
from math import isfinite

from games.optimization.cancellation import Cancellation, Cancelled
from twoptimizer.catalog import faction_name
from twoptimizer.constraint_comparison import baseline_config, compare_results, has_requirements
from twoptimizer.errors import ApplicationError, deserialize_error, serialize_error
from twoptimizer.holdings import map_context, province_label
from twoptimizer.models import CaseResult, RunConfig, SolverSummary
from twoptimizer.progress import ModelStats, PhaseTimer, ProgressEvent, SearchStats
from twoptimizer.provenance import source_files
from twoptimizer.registry import game_plugin, solve_adapter
from twoptimizer.requests import make_jobs as make_jobs
from twoptimizer.session import RunSession


def solve_case(
    config: RunConfig,
    progress: Callable[[ProgressEvent], None] | None = None,
    *,
    session: RunSession | None = None,
    cancellation: Cancellation | None = None,
) -> CaseResult:
    phase = PhaseTimer(progress, cancellation=cancellation, collect_search=True)
    phase("request_seconds", "Validating request")
    jobs, _ = make_jobs(config)
    if len(jobs) != 1:
        raise ApplicationError("A case must receive exactly one holding, faction and solver.")
    config = jobs[0]
    try:
        if cancellation is not None:
            cancellation.checkpoint()
        output = (
            _solve_comparison(config, progress, session, cancellation)
            if config.compare_constraints and has_requirements(config)
            else _solve_one(config, phase, session)
        )
    except Cancelled as error:
        phase()
        output = _cancelled_result(config, phase, str(error))
    if config.compare_constraints and not has_requirements(config):
        output.raw["constraint_comparison"] = {
            "status": "unavailable",
            "reason": "No optional building or influence requirements were selected.",
        }
    if cancellation is not None and cancellation.requested:
        output.raw["cancellation"] = {
            **output.raw.get("cancellation", {}),
            "requested": True,
            "incumbent_retained": output.income is not None,
        }
    return output


def _cancelled_result(config: RunConfig, phase: PhaseTimer, reason: str) -> CaseResult:
    return CaseResult(
        request=config,
        faction=faction_name(config.game, config.faction),
        province=province_label(config),
        solver=SolverSummary(config.algorithm, "UNKNOWN", 0, None, None),
        income=None,
        gap_percent=None,
        metrics={},
        buildings=[],
        assumptions=game_plugin(config.game).notes,
        source_files={},
        raw={
            "cancellation": {"reason": reason},
            "model_complexity": [stats.to_dict() for stats in phase.models],
            "search_measurements": phase.search_report(
                {"status": "UNKNOWN", "income": None, "bound": None, "validated_layout": False}
            ),
        },
        timings=phase.timings,
    )


def _solve_one(config: RunConfig, phase: PhaseTimer, session: RunSession | None) -> CaseResult:
    phase("load_engine_seconds", "Loading engine and game data")
    adapter = solve_adapter(config.game)
    if session is not None:
        session.prepare(config.game)
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
    result.raw["search_measurements"] = phase.search_report(
        {
            "status": solver.status,
            "income": income,
            "bound": bound,
            "gap_percent": gap,
            "validated_layout": income is not None,
        }
    )
    output = CaseResult(
        request=config,
        faction=faction_name(config.game, config.faction),
        province=province_label(config),
        solver=solver,
        income=income,
        gap_percent=gap,
        metrics=result.metrics,
        buildings=sorted(result.buildings, key=lambda b: (b.region, b.building)),
        assumptions=game_plugin(config.game).notes,
        source_files=source_files(config.game),
        raw=result.raw,
        timings=phase.timings,
        objectives=result.objectives,
    )
    if session is not None:
        session.record(output)
    phase()
    return output


def _solve_comparison(config, progress, session, cancellation):
    # Retain the requested layout if cancelled, never substitute a baseline
    # that omits the user's building or religious requirements.
    constrained = _comparison_side(
        replace(config, compare_constraints=False),
        "With requirements",
        progress,
        session,
        cancellation,
    )
    if constrained.solver.status == "ERROR":
        raise deserialize_error(constrained.raw)
    baseline = _comparison_side(
        baseline_config(config), "Without requirements", progress, session, cancellation
    )
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


def _comparison_side(config, label, progress, session, cancellation):
    def relay(event):
        if progress is not None:
            progress(
                replace(event, label=f"{label}: {event.label}")
                if isinstance(event, (ModelStats, SearchStats))
                else f"{label}: {event}"
            )

    try:
        return solve_case(config, relay, session=session, cancellation=cancellation)
    except ApplicationError as error:
        return error_result(config, error)


def error_result(config: RunConfig, error: Exception) -> CaseResult:
    """Retain a failed case in a batch with the same result schema as successes."""
    try:
        assumptions = game_plugin(config.game).notes
    except ValueError:
        assumptions = ""
    return CaseResult(
        request=config,
        faction=config.faction,
        province=", ".join(config.holdings),
        solver=SolverSummary(config.algorithm, "ERROR", 0, None, None),
        income=None,
        gap_percent=None,
        metrics={},
        buildings=[],
        assumptions=assumptions,
        source_files={},
        raw=serialize_error(error),
        timings={},
    )
