"""Bounded search observations, with case clocks separate from solver clocks."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from twoptimizer.progress import SearchStats

GAP_THRESHOLDS = (10, 5, 2, 1)
CASE_CLOCK = "Seconds since case start, including preparation; excludes worker startup"


@dataclass(slots=True)
class _Stream:
    label: str
    sense: str
    unit: str
    observations: int = 0
    first_candidate_seconds: float | None = None
    gap_reached_seconds: dict[str, float] = field(default_factory=dict)

    def observe(self, stats: SearchStats, elapsed: float) -> None:
        self.observations += 1
        if stats.objective is not None and self.first_candidate_seconds is None:
            self.first_candidate_seconds = elapsed
        gap = stats.gap_percent
        if gap is not None:
            for threshold in GAP_THRESHOLDS:
                if gap <= threshold:
                    self.gap_reached_seconds.setdefault(str(threshold), elapsed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "sense": self.sense,
            "unit": self.unit,
            "observations": self.observations,
            "first_candidate_seconds": self.first_candidate_seconds,
            "gap_reached_seconds": self.gap_reached_seconds.copy(),
        }


class SearchMeasurements:
    """Keep exact first-observed milestones while thinning a bounded time series.

    Observations have not passed the engine's independent layout evaluation.
    Milestones use monotonic time since the case began, including preparation.
    Native elapsed clocks remain in each sample and may reset between stages.
    """

    def __init__(self, max_samples: int = 128, max_streams: int = 16, *, clock: str = CASE_CLOCK):
        if max_samples < 4 or max_streams < 1:
            raise ValueError("Search measurements need at least four samples and one stream")
        self.clock = clock
        self.max_samples = max_samples
        self.max_streams = max_streams
        self.streams: dict[tuple[str, str, str], _Stream] = {}
        self.samples: list[dict[str, Any]] = []
        self.observations = 0
        self.dropped_samples = 0
        self.untracked_observations = 0

    def observe(self, stats: SearchStats, elapsed: float) -> None:
        self.observations += 1
        key = (stats.label, stats.sense, stats.unit)
        if key not in self.streams:
            if len(self.streams) >= self.max_streams:
                self.untracked_observations += 1
                return
            self.streams[key] = _Stream(*key)
        self.streams[key].observe(stats, elapsed)
        self.samples.append({**stats.to_dict(), "case_elapsed_seconds": elapsed})
        if len(self.samples) > self.max_samples:
            previous_size = len(self.samples)
            self.samples = self.samples[:1] + self.samples[2:-1:2] + self.samples[-1:]
            self.dropped_samples += previous_size - len(self.samples)

    def to_dict(self, final: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "validation": "Search observations precede independent layout validation",
            "sample_limit": self.max_samples,
            "stream_limit": self.max_streams,
            "observations": self.observations,
            "dropped_samples": self.dropped_samples,
            "untracked_observations": self.untracked_observations,
            "streams": [stream.to_dict() for stream in self.streams.values()],
            "samples": deepcopy(self.samples),
            "final": deepcopy(final),
        }
