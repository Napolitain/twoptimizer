"""Observed search activity, without extrapolating an optimality deadline.

The caller owns a monotonic clock and starts a fresh activity for each solver
case. Native elapsed times anchor observations; local ticks keep their ages
advancing while the solver emits nothing. Throttled events describe observed
improvements, not every change made inside the solver.
"""

from dataclasses import dataclass, replace

from twoptimizer.progress import SearchStats


def format_duration(seconds: float) -> str:
    """Compact elapsed duration, including long-running searches."""
    total = max(0, int(seconds))
    for unit, size, lower, divisor in (
        ("w", 604800, "d", 86400),
        ("d", 86400, "h", 3600),
        ("h", 3600, "m", 60),
        ("m", 60, "s", 1),
    ):
        if total >= size:
            return f"{total // size}{unit} {(total % size) // divisor}{lower}"
    return f"{total}s"


def _improves(value: float, current: float | None, *, increasing: bool) -> bool:
    return current is None or (value > current if increasing else value < current)


@dataclass(frozen=True, slots=True)
class SearchSnapshot:
    elapsed_seconds: float
    first_candidate_seconds: float | None
    candidate_age_seconds: float | None
    bound_age_seconds: float | None
    stats: SearchStats | None

    @property
    def improvement_age_seconds(self) -> float | None:
        """Time since either candidate or bound last improved, when observed."""
        ages = [
            age for age in (self.candidate_age_seconds, self.bound_age_seconds) if age is not None
        ]
        return min(ages) if ages else None


class SearchActivity:
    """Track one search; ``begin`` also clears all state from the previous one."""

    def __init__(self):
        self._clock_at: float | None = None
        self._clock_elapsed = 0.0
        self._latest: SearchStats | None = None
        self._candidate: float | None = None
        self._bound: float | None = None
        self._first_candidate: float | None = None
        self._candidate_changed: float | None = None
        self._bound_changed: float | None = None

    def begin(self, now: float) -> None:
        self._clock_at, self._clock_elapsed = now, 0.0
        self._latest = None
        self._candidate = self._bound = None
        self._first_candidate = self._candidate_changed = self._bound_changed = None

    def _elapsed(self, now: float) -> float:
        if self._clock_at is None:
            return 0.0
        return self._clock_elapsed + max(0.0, now - self._clock_at)

    def observe(self, stats: SearchStats, now: float) -> None:
        def identity(row: SearchStats) -> tuple[str, str, str]:
            return row.label, row.sense, row.unit

        if self._clock_at is None or (
            self._latest is not None and identity(self._latest) != identity(stats)
        ):
            self.begin(now - stats.elapsed_seconds)
        # Delayed callbacks must not move the live clock backwards. A native
        # elapsed time may also reveal search that began before its UI event.
        self._clock_elapsed = max(self._elapsed(now), stats.elapsed_seconds)
        self._clock_at, self._latest = now, stats
        increasing = stats.sense == "maximize"
        if stats.objective is not None:
            self._first_candidate = (
                stats.elapsed_seconds
                if self._first_candidate is None
                else min(self._first_candidate, stats.elapsed_seconds)
            )
            if _improves(stats.objective, self._candidate, increasing=increasing):
                self._candidate, self._candidate_changed = stats.objective, stats.elapsed_seconds
        if stats.bound is not None and _improves(
            stats.bound, self._bound, increasing=not increasing
        ):
            self._bound, self._bound_changed = stats.bound, stats.elapsed_seconds

    def snapshot(self, now: float) -> SearchSnapshot:
        elapsed = self._elapsed(now)

        def age(changed: float | None) -> float | None:
            return None if changed is None else max(0.0, elapsed - changed)

        stats = (
            None
            if self._latest is None
            else replace(
                self._latest,
                objective=self._candidate,
                bound=self._bound,
                elapsed_seconds=elapsed,
            )
        )
        return SearchSnapshot(
            elapsed,
            self._first_candidate,
            age(self._candidate_changed),
            age(self._bound_changed),
            stats,
        )

    def summary(self, now: float) -> str:
        if self._clock_at is None:
            return "Search not started"
        snapshot = self.snapshot(now)
        candidate = (
            "No candidate observed yet"
            if snapshot.first_candidate_seconds is None
            else f"Candidate found at {format_duration(snapshot.first_candidate_seconds)}"
        )

        def last(age: float | None) -> str:
            return "none yet" if age is None else format_duration(age) + " ago"

        return (
            f"{candidate} · search {format_duration(snapshot.elapsed_seconds)} · proof pending\n"
            f"Last observed improvement: layout {last(snapshot.candidate_age_seconds)}"
            f" · bound {last(snapshot.bound_age_seconds)}"
        )
