"""Historical runtime observations, matched to complete expanded query settings.

These observations are context, not forecasts. In particular, an interrupted
FEASIBLE run supplies no upper bound on time to an optimality proof.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from twoptimizer.models import RunConfig
from twoptimizer.search_activity import format_duration

_DATA = Path(__file__).with_name("data") / "runtime_evidence.json"
_LOCATION_AND_EXECUTION = {"province", "provinces", "seconds", "workers"}


@dataclass(frozen=True, slots=True)
class Observation:
    wall_seconds: float
    statuses: tuple[tuple[str, int], ...]
    configured_solver_seconds: float
    complete: bool

    @property
    def proved(self) -> bool:
        return (
            self.complete
            and bool(self.statuses)
            and all(
                status in {"OPTIMAL", "INFEASIBLE"} and count > 0 for status, count in self.statuses
            )
        )


@dataclass(frozen=True, slots=True)
class Evidence:
    request: RunConfig
    holdings: tuple[tuple[str, ...], ...]
    observations: tuple[Observation, ...]
    source_path: str
    source_sha256: str
    revision: str
    measured_at: str
    machine: str
    workers: int


@lru_cache(maxsize=1)
def _evidence() -> tuple[Evidence, ...]:
    data = json.loads(_DATA.read_text())
    result = []
    for row in data["profiles"]:
        source = data["sources"][row["source"]]
        observations = tuple(
            Observation(
                item["wall_seconds"],
                tuple(sorted(item["statuses"].items())),
                item["configured_solver_seconds"],
                item["complete"],
            )
            for item in row["observations"]
        )
        result.append(
            Evidence(
                RunConfig.from_dict(row["request"]),
                tuple(sorted(tuple(sorted(group)) for group in row["holdings"])),
                observations,
                source["path"],
                source["sha256"],
                source["revision"],
                source["measured_at_utc"],
                source["machine"],
                source["workers"],
            )
        )
    return tuple(result)


def _settings(config: RunConfig) -> dict:
    return {
        key: value for key, value in config.to_dict().items() if key not in _LOCATION_AND_EXECUTION
    }


def _match(jobs: Sequence[RunConfig]) -> Evidence | None:
    if not jobs:
        return None
    settings = _settings(jobs[0])
    if any(_settings(job) != settings for job in jobs[1:]):
        return None
    holdings = tuple(sorted(tuple(sorted(job.holdings)) for job in jobs))
    return next(
        (
            row
            for row in _evidence()
            if row.holdings == holdings and _settings(row.request) == settings
        ),
        None,
    )


def _duration(value: float) -> str:
    if value < 60:
        return f"{value:.1f}s"
    return format_duration(value)


def _range(observations: Sequence[Observation]) -> str:
    times = [row.wall_seconds for row in observations]
    lower, upper = _duration(min(times)), _duration(max(times))
    return lower if lower == upper else f"{lower} to {upper}"


def runtime_outlook(config: RunConfig, jobs: Sequence[RunConfig]) -> str:
    """Return a compact observation without extrapolating an ETA from model size."""
    if not jobs:
        return "No cases selected."
    evidence = _match(jobs)
    if evidence is None:
        return "Completion time unknown · no matching measured query."
    proved = [row for row in evidence.observations if row.proved]
    if len(proved) == len(evidence.observations):
        return f"Historical reference: completed in {_range(proved)} · not an ETA."
    unfinished = [row for row in evidence.observations if not row.proved]
    if not proved:
        return f"Proof time unknown · historical reference unfinished after {_range(unfinished)}."
    return (
        f"Proof time uncertain · historical proof {_range(proved)}; "
        f"another run unfinished after {_range(unfinished)}."
    )


def _scope_note(jobs: Sequence[RunConfig]) -> str:
    if any(job.joint and len(job.holdings) > 1 for job in jobs):
        return "Joint provinces share constraints and bonuses; province count does not give an ETA."
    return f"{len(jobs)} separate solver cases; costs can differ between provinces and factions."


def _observation_line(index: int, row: Observation) -> str:
    statuses = ", ".join(f"{count} {status}" for status, count in row.statuses)
    return (
        f"Reference run {index}: {_duration(row.wall_seconds)} wall time; {statuses}. "
        f"Configured solver allowance: {_duration(row.configured_solver_seconds)} total."
    )


def runtime_details(config: RunConfig, jobs: Sequence[RunConfig]) -> str:
    """Explain scope, censored observations and source/hardware limitations."""
    if not jobs:
        return "Select at least one province to inspect a runtime outlook."
    lines = [runtime_outlook(config, jobs), _scope_note(jobs)]
    evidence = _match(jobs)
    if evidence is not None:
        lines.extend(
            _observation_line(index, row) for index, row in enumerate(evidence.observations, 1)
        )
        lines.extend(
            (
                f"Reference machine: {evidence.machine}; {evidence.workers} solver workers.",
                f"Historical reference measured {evidence.measured_at[:10]}.",
                "The current build, machine, worker count and time limit may differ. "
                "Matching gameplay settings do not make this a forecast.",
                f"Source: {evidence.source_path}.",
            )
        )
    lines.append(
        "No calibrated evidence predicts whether this run will need minutes, hours or weeks. "
        "Finding a valid layout and proving the optimum are different milestones. "
        "A timeout means unfinished, not infeasible; gap is not percent of work completed."
    )
    return "\n\n".join(lines)
