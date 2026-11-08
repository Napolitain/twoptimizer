"""Worker progress protocol and typed phase timing."""

from collections.abc import Callable
from time import perf_counter

PREFIX = "__TWOPTIMIZER_PROGRESS__ "


class PhaseTimer:
    """Collect phase durations and notify the optional progress observer."""

    def __init__(self, progress: Callable[[str], None] | None = None):
        self.timings: dict[str, float] = {}
        self.stage: str | None = None
        self.started = perf_counter()
        self.progress = progress

    def __call__(self, key: str | None = None, label: str | None = None) -> None:
        now = perf_counter()
        if self.stage is not None:
            self.timings[self.stage] = now - self.started
        self.stage, self.started = key, now
        if self.progress is not None and label is not None:
            self.progress(label)
