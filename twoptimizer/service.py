"""Shared case behavior, independent of foreground or subprocess execution."""

from collections.abc import Callable
from math import isfinite

from twoptimizer.catalog import NOTES, faction_name
from twoptimizer.engines import solve_attila, solve_rome, solve_shogun
from twoptimizer.errors import ApplicationError, serialize_error
from twoptimizer.holdings import province_label
from twoptimizer.models import CaseResult, RunConfig, SolverSummary
from twoptimizer.progress import PhaseTimer
from twoptimizer.provenance import source_files
from twoptimizer.requests import make_jobs as make_jobs
from twoptimizer.session import RunSession


def solve_case(
    config: RunConfig,
    progress: Callable[[str], None] | None = None,
    *,
    session: RunSession | None = None,
) -> CaseResult:
    phase = PhaseTimer(progress)
    phase("request_seconds", "Validating request")
    jobs, _ = make_jobs(config)
    if len(jobs) != 1:
        raise ApplicationError("A case must receive exactly one holding, faction and solver.")
    config = jobs[0]
    phase("load_engine_seconds", "Loading engine and game data")
    adapter = {"rome2": solve_rome, "shogun2": solve_shogun, "attila": solve_attila}[config.game]
    try:
        result = adapter(config, phase, session)
    except (ValueError, TypeError) as error:
        raise ApplicationError(str(error)) from error
    income = result.income
    solver = SolverSummary.from_dict(result.raw["solver"])
    bound = solver.bound
    gap = (
        100 * max(0, bound - income) / max(1, abs(bound))
        if income is not None and bound is not None and isfinite(bound)
        else None
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
        assumptions=NOTES[config.game],
        source_files=source_files(config.game),
        raw=result.raw,
        timings=phase.timings,
    )
    if session is not None:
        session.record(output)
    phase()
    return output


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
