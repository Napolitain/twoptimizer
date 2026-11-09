"""Elapsed-time accounting without choosing a game's preparation allowance."""

from collections.abc import Callable
from math import isfinite
from time import perf_counter


class Budget:
    """Share one finite allowance across stages, with an injectable monotonic clock."""

    def __init__(self, seconds: float, *, clock: Callable[[], float] = perf_counter) -> None:
        if not isfinite(seconds) or seconds < 0:
            raise ValueError("Preparation seconds must be nonnegative and finite")
        self.limit = seconds
        self._clock = clock
        self.started = clock()

    @property
    def remaining(self) -> float:
        return max(0.0, self.limit - self.elapsed)

    @property
    def elapsed(self) -> float:
        return self._clock() - self.started
