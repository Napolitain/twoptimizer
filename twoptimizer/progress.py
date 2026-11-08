"""Worker progress protocol and typed phase timing."""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from time import perf_counter
from typing import Any

from games.tw.cancellation import Cancellation

PREFIX = "__TWOPTIMIZER_PROGRESS__ "


@dataclass(frozen=True, slots=True)
class ModelStats:
    """Observed input counts, not a presolved size or a runtime prediction.

    Storage, when reported, is the constraint matrix's bytes, not solver RAM.
    Reference formulations and native solver inputs stay separate.
    """

    label: str
    variables: int
    constraints: int
    formulation: str = ""
    stage: str = "reference"
    decision_variables: int | None = None
    nonzeros: int | None = None
    storage_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "variables": self.variables,
            "constraints": self.constraints,
            "formulation": self.formulation,
            "stage": self.stage,
            "decision_variables": self.decision_variables,
            "nonzeros": self.nonzeros,
            "storage_bytes": self.storage_bytes,
        }

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> ModelStats:
        return cls(
            label=record["label"],
            variables=record["variables"],
            constraints=record["constraints"],
            formulation=record.get("formulation", ""),
            stage=record.get("stage", "reference"),
            decision_variables=record.get("decision_variables"),
            nonzeros=record.get("nonzeros"),
            storage_bytes=record.get("storage_bytes"),
        )


@dataclass(frozen=True, slots=True)
class SearchStats:
    """Unfinished solver observations in original objective units, before validation."""

    label: str
    objective: float | None
    bound: float | None
    elapsed_seconds: float
    sense: str = "maximize"
    unit: str = "income/turn"

    def __post_init__(self) -> None:
        if self.sense not in {"maximize", "minimize"}:
            raise ValueError("Search sense must be maximize or minimize")
        for value in (self.objective, self.bound, self.elapsed_seconds):
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError("Search observations must be finite numbers or null")
        if self.elapsed_seconds is None or self.elapsed_seconds < 0:
            raise ValueError("Search elapsed seconds must be nonnegative")

    @property
    def gap_percent(self) -> float | None:
        if self.objective is None or self.bound is None:
            return None
        difference = (
            self.bound - self.objective if self.sense == "maximize" else self.objective - self.bound
        )
        return 100 * difference / max(1, abs(self.bound)) if difference >= 0 else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "objective": self.objective,
            "bound": self.bound,
            "elapsed_seconds": self.elapsed_seconds,
            "sense": self.sense,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> SearchStats:
        return cls(
            label=record["label"],
            objective=record["objective"],
            bound=record["bound"],
            elapsed_seconds=record["elapsed_seconds"],
            sense=record.get("sense", "maximize"),
            unit=record.get("unit", "income/turn"),
        )


type ProgressEvent = str | ModelStats | SearchStats


def encode_progress(event: ProgressEvent) -> dict[str, Any]:
    if isinstance(event, ModelStats):
        return {"model": event.to_dict()}
    if isinstance(event, SearchStats):
        return {"search": event.to_dict()}
    return {"phase": event}


def decode_progress(record: dict[str, Any]) -> ProgressEvent:
    if "model" in record:
        return ModelStats.from_dict(record["model"])
    if "search" in record:
        return SearchStats.from_dict(record["search"])
    return record["phase"]


class PhaseTimer:
    """Collect phase durations and notify the optional progress observer."""

    def __init__(
        self,
        progress: Callable[[ProgressEvent], None] | None = None,
        *,
        cancellation: Cancellation | None = None,
    ):
        self.timings: dict[str, float] = {}
        self.models: list[ModelStats] = []
        self.stage: str | None = None
        self.started = perf_counter()
        self.progress = progress
        self.cancellation = cancellation
        self._search_emitted: dict[str, float] = {}
        self._search_lock = Lock()

    def __call__(self, key: str | None = None, label: str | None = None) -> None:
        now = perf_counter()
        if self.stage is not None:
            self.timings[self.stage] = now - self.started
        self.stage, self.started = key, now
        if self.progress is not None and label is not None:
            self.progress(label)

    def record_model(self, stats: ModelStats) -> None:
        if stats in self.models:
            return
        self.models.append(stats)
        if self.progress is not None:
            self.progress(stats)

    def record_search(self, stats: SearchStats, *, force: bool = False) -> None:
        """Bound callback/IPC traffic; the first and explicitly final updates always pass."""
        if self.progress is None:
            return
        with self._search_lock:
            now = perf_counter()
            previous = self._search_emitted.get(stats.label)
            if not force and previous is not None and now - previous < 0.75:
                return
            self._search_emitted[stats.label] = now
            self.progress(stats)
