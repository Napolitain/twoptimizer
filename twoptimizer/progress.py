"""Worker progress protocol and typed phase timing."""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

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


type ProgressEvent = str | ModelStats


def encode_progress(event: ProgressEvent) -> dict[str, Any]:
    return {"model": event.to_dict()} if isinstance(event, ModelStats) else {"phase": event}


def decode_progress(record: dict[str, Any]) -> ProgressEvent:
    return ModelStats.from_dict(record["model"]) if "model" in record else record["phase"]


class PhaseTimer:
    """Collect phase durations and notify the optional progress observer."""

    def __init__(self, progress: Callable[[ProgressEvent], None] | None = None):
        self.timings: dict[str, float] = {}
        self.models: list[ModelStats] = []
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

    def record_model(self, stats: ModelStats) -> None:
        if stats in self.models:
            return
        self.models.append(stats)
        if self.progress is not None:
            self.progress(stats)
