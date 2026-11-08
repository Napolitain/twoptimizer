"""Bounded, session-local observations for exactly matching requests.

Past runtimes are evidence about completed or stopped runs, never an ETA.
Callers supply total observed case time and the status of the entire case;
for a constraint comparison, one proved side does not prove the whole case.
"""

import json
from collections import OrderedDict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from twoptimizer.models import RunConfig
from twoptimizer.search_activity import format_duration

_PROVED = frozenset({"OPTIMAL", "INFEASIBLE"})
_UNFINISHED = frozenset({"FEASIBLE", "UNKNOWN", "CANCELLED"})


@dataclass(frozen=True, slots=True)
class _Observation:
    status: str
    seconds: float


def _key(job: RunConfig) -> str:
    return json.dumps(job.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _duration(seconds: float) -> str:
    return f"{seconds:.1f}s" if seconds < 60 else format_duration(seconds)


def _range(observations: Sequence[_Observation]) -> str:
    times = [observation.seconds for observation in observations]
    low, high = _duration(min(times)), _duration(max(times))
    return low if low == high else f"{low} to {high}"


def _outcomes(observations: Sequence[_Observation]) -> str:
    proved = [item for item in observations if item.status in _PROVED]
    unfinished = [item for item in observations if item.status in _UNFINISHED]
    parts = []
    if proved:
        parts.append(f"previously proved in {_range(proved)}")
    if unfinished:
        parts.append(f"stopped without proof after {_range(unfinished)}")
    return "; ".join(parts)


class RuntimeHistory:
    """Keep recent evidence without persistence or model/solver work."""

    def __init__(self, max_requests: int = 128, samples_per_request: int = 5):
        for value in (max_requests, samples_per_request):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("Runtime history limits must be positive integers")
        self.max_requests = max_requests
        self.samples_per_request = samples_per_request
        self._history: OrderedDict[str, deque[_Observation]] = OrderedDict()

    def record(self, job: RunConfig, status: str, elapsed_seconds: float) -> None:
        """Record a proof or an unfinished case; ignore failed/invalid execution."""
        if status not in _PROVED | _UNFINISHED:
            return
        if (
            isinstance(elapsed_seconds, bool)
            or not isinstance(elapsed_seconds, (int, float))
            or not isfinite(elapsed_seconds)
            or elapsed_seconds < 0
        ):
            raise ValueError("Observed runtime must be finite and nonnegative")
        key = _key(job)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.samples_per_request)
        self._history[key].append(_Observation(status, float(elapsed_seconds)))
        self._history.move_to_end(key)
        while len(self._history) > self.max_requests:
            self._history.popitem(last=False)

    def _matching(self, jobs: Sequence[RunConfig]) -> tuple[int, list[_Observation]]:
        keys = [_key(job) for job in jobs]
        matched = sum(key in self._history for key in keys)
        # A repeated query in a batch references the same observations once.
        observations = [item for key in dict.fromkeys(keys) for item in self._history.get(key, ())]
        return matched, observations

    def summary(self, jobs: Sequence[RunConfig]) -> str | None:
        """Describe observed case ranges; never extrapolate a batch finish time."""
        matched, observations = self._matching(jobs)
        if not observations:
            return None
        outcomes = _outcomes(observations)
        if len(jobs) == 1:
            return f"This session: {outcomes}. Not an ETA."
        return (
            f"This session: history for {matched}/{len(jobs)} cases; "
            f"{outcomes} per case. No batch ETA."
        )

    def details(self, jobs: Sequence[RunConfig]) -> str:
        matched, observations = self._matching(jobs)
        if not observations:
            return "No runs with these exact settings recorded this session."
        statuses = ", ".join(
            f"{status}: {sum(item.status == status for item in observations)}"
            for status in sorted({item.status for item in observations})
        )
        return (
            f"Session history: {matched}/{len(jobs)} requested cases have matching settings.\n"
            f"{len(observations)} retained observations ({statuses}).\n"
            f"Observed per-case outcomes: {_outcomes(observations)}.\n"
            "Matches include solver, limits, workers, province scope and all scenario options.\n"
            "These are past runs on this session's machine, not a completion guarantee. "
            "Unfinished runs do not establish how long a proof would take. "
            "No durations are inferred for unmatched cases."
        )
