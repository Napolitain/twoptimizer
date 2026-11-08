"""Typed application objects; dictionaries are reserved for engine/JSON boundaries."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RunConfig:
    game: str = "rome2"
    faction: str = "rom_rome"
    province: str = "coastal"
    algorithm: str = "portfolio"
    seconds: float | None = None
    workers: int | None = None
    research: str = "none"
    fertility: float = 5
    religion: str = "CHRIST_ORTHODOX"
    soil: str = "native"
    town_wealth: float = 0
    tax: float = 30
    world_bonuses: bool = True
    provinces: tuple[str, ...] | None = None
    joint: bool = False
    adjacency: tuple[tuple[str, str], ...] | None = None

    def __post_init__(self):
        # JSON uses lists; keep requests immutable after crossing the worker boundary.
        if self.provinces is not None:
            object.__setattr__(self, "provinces", tuple(self.provinces))
        if self.adjacency is not None:
            object.__setattr__(self, "adjacency", tuple(tuple(pair) for pair in self.adjacency))


@dataclass(frozen=True, slots=True)
class BuildingSelection:
    region: str
    building: str
    id: str


@dataclass(frozen=True, slots=True)
class SolverSummary:
    algorithm: str
    status: str
    seconds: float
    objective: float | None
    bound: float | None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, report: dict[str, Any]) -> "SolverSummary":
        fields = {
            key: report[key] for key in ("algorithm", "status", "seconds", "objective", "bound")
        }
        return cls(
            **fields, details={key: value for key, value in report.items() if key not in fields}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "status": self.status,
            "seconds": self.seconds,
            "objective": self.objective,
            "bound": self.bound,
            **self.details,
        }


@dataclass(frozen=True, slots=True)
class EngineResult:
    raw: dict[str, Any]
    income: float | None
    buildings: list[BuildingSelection]
    metrics: dict[str, float | None]


@dataclass(frozen=True, slots=True, kw_only=True)
class CaseResult:
    request: RunConfig
    faction: str
    province: str
    solver: SolverSummary
    income: float | None
    gap_percent: float | None
    metrics: dict[str, float | None]
    buildings: list[BuildingSelection]
    assumptions: str
    source_files: dict[str, str]
    raw: dict[str, Any]
    timings: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Retain the existing JSON schema at the public process/export boundary."""
        return {
            "request": asdict(self.request),
            "faction": self.faction,
            "province": self.province,
            "solver": self.solver.to_dict(),
            "income": self.income,
            "gap_percent": self.gap_percent,
            "metrics": self.metrics,
            "buildings": [asdict(building) for building in self.buildings],
            "assumptions": self.assumptions,
            "source_files": self.source_files,
            "raw": self.raw,
            "timings": self.timings,
        }
