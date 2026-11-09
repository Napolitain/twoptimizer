"""Typed application objects; dictionaries are reserved for engine/JSON boundaries."""

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any

from games.tw.attila.scenario import Scenario as CampaignScenario
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.errors import ApplicationError
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions


@dataclass(frozen=True, slots=True)
class RegionFertility:
    region: str
    value: float


@dataclass(frozen=True, slots=True)
class AttilaOptions:
    """Income-model inputs and search settings shared by every interface."""

    technologies: tuple[str, ...] | None = None
    campaign: CampaignScenario | None = None
    region_fertility: tuple[RegionFertility, ...] = ()
    city_level: int = 4
    building_level: int = 1
    military: bool = False
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "technologies": None if self.technologies is None else list(self.technologies),
            "campaign": None if self.campaign is None else self.campaign.to_dict(),
            "region_fertility": [asdict(item) for item in self.region_fertility],
            **{
                key: getattr(self, key)
                for key in (
                    "city_level",
                    "building_level",
                    "military",
                    "seed",
                )
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AttilaOptions:
        if not isinstance(payload, dict):
            raise ApplicationError("Attila options must be a JSON object.")
        data = dict(payload)
        if data.get("technologies") is not None:
            if not isinstance(data["technologies"], (tuple, list)):
                raise ApplicationError("Technologies must be a list of names.")
            data["technologies"] = tuple(data["technologies"])
        if data.get("campaign") is not None:
            data["campaign"] = CampaignScenario(data["campaign"])
        data["region_fertility"] = tuple(
            RegionFertility(**item) for item in data.get("region_fertility", ())
        )
        return cls(**data)


@dataclass(frozen=True, slots=True)
class RunConfig:
    game: str = "rome2"
    faction: str = "rom_rome"
    province: str = "coastal"
    algorithm: str = "cp-sat"
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
    technology_profile: str = "public"
    attila: AttilaOptions = field(default_factory=AttilaOptions)
    three_kingdoms: ThreeKingdomsOptions = field(default_factory=ThreeKingdomsOptions)
    constraints: ConstraintOptions = field(default_factory=ConstraintOptions)
    compare_constraints: bool = False
    comparison_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        candidates = ConstraintOptions(required_buildings=self.comparison_candidates)
        object.__setattr__(self, "comparison_candidates", candidates.required_buildings)
        if self.provinces is not None:
            object.__setattr__(self, "provinces", tuple(self.provinces))
        if self.adjacency is not None:
            object.__setattr__(self, "adjacency", tuple(tuple(pair) for pair in self.adjacency))

    @property
    def holdings(self) -> tuple[str, ...]:
        return (self.province,) if self.provinces is None else self.provinces

    def to_dict(self) -> dict[str, Any]:
        """Keep old single-case JSON fields, adding advanced options when used."""
        data = {
            key: getattr(self, key)
            for key in self.__dataclass_fields__
            if key
            not in {
                "technology_profile",
                "attila",
                "three_kingdoms",
                "constraints",
                "compare_constraints",
                "comparison_candidates",
            }
        }
        data["provinces"] = None if self.provinces is None else list(self.provinces)
        data["adjacency"] = (
            None if self.adjacency is None else [list(pair) for pair in self.adjacency]
        )
        if self.technology_profile != "public":
            data["technology_profile"] = self.technology_profile
        if self.attila != AttilaOptions():
            data["attila"] = self.attila.to_dict()
        if self.game == "three_kingdoms" or self.three_kingdoms != ThreeKingdomsOptions():
            data["three_kingdoms"] = self.three_kingdoms.to_dict()
        if self.constraints != ConstraintOptions():
            data["constraints"] = self.constraints.to_dict()
        if self.compare_constraints:
            data["compare_constraints"] = True
        if self.comparison_candidates:
            data["comparison_candidates"] = list(self.comparison_candidates)
        return data

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunConfig:
        try:
            if not isinstance(payload, dict):
                raise ApplicationError("A request must be a JSON object.")
            data = dict(payload)
            if data.get("provinces") is not None:
                if not isinstance(data["provinces"], (list, tuple)):
                    raise ApplicationError("Provinces must be a list of province IDs.")
                data["provinces"] = tuple(data["provinces"])
            data["attila"] = AttilaOptions.from_dict(data.get("attila", {}))
            data["three_kingdoms"] = ThreeKingdomsOptions.from_dict(data.get("three_kingdoms", {}))
            data["constraints"] = ConstraintOptions.from_dict(data.get("constraints", {}))
            return cls(**data)
        except (TypeError, ValueError) as error:
            raise ApplicationError(str(error)) from error


@dataclass(frozen=True, slots=True)
class RunRequest:
    """A batch of cases; empty axes retain the base request's explicit settings."""

    config: RunConfig
    factions: tuple[str, ...] = ()
    provinces: tuple[str, ...] = ()
    algorithms: tuple[str, ...] = ()
    fertilities: tuple[float, ...] = ()
    soils: tuple[str, ...] = ()
    joint: bool = False
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class BuildingSelection:
    region: str
    building: str
    id: str


@dataclass(frozen=True, slots=True)
class ObjectiveSummary:
    """One objective in priority order; a bound uses the objective's own units.

    Maximization bounds are upper bounds; minimization bounds are lower bounds.
    An omitted status inherits the case's status. Explicit statuses allow a
    proved primary objective followed by an unfinished secondary objective.
    """

    identifier: str
    label: str
    unit: str
    sense: str
    value: float | None
    bound: float | None
    status: str | None = None

    def __post_init__(self) -> None:
        for name in ("identifier", "label", "unit"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Objective {name} must be a nonempty string")
        if not isinstance(self.sense, str) or self.sense not in {"maximize", "minimize"}:
            raise ValueError("Objective sense must be maximize or minimize")
        self._validate_numbers()
        if self.status is not None:
            if not isinstance(self.status, str) or not self.status.strip():
                raise ValueError("Objective status must be a nonempty string or None")
            self.validate_status(self.status)

    def _validate_numbers(self) -> None:
        for value in (self.value, self.bound):
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isfinite(value)
            ):
                raise ValueError("Objective value and bound must be finite numbers or None")
        if self.value is None or self.bound is None:
            return
        difference = (
            self.bound - self.value if self.sense == "maximize" else self.value - self.bound
        )
        if difference < -1e-5:
            raise ValueError("Objective bound contradicts its value and optimization sense")

    def validate_status(self, fallback: str) -> None:
        status = self.status or fallback
        if status == "OPTIMAL" and (
            self.value is None or self.bound is None or abs(self.value - self.bound) > 1e-5
        ):
            raise ValueError("An optimal objective requires a value and matching bound")
        if status == "FEASIBLE" and self.value is None:
            raise ValueError("A feasible objective requires a value")
        if status == "INFEASIBLE" and self.value is not None:
            raise ValueError("An infeasible objective cannot retain a feasible value")

    @property
    def gap_percent(self) -> float | None:
        """Interval width relative to its upper endpoint, in either direction."""
        if self.value is None or self.bound is None:
            return None
        lower, upper = (
            (self.value, self.bound) if self.sense == "maximize" else (self.bound, self.value)
        )
        return 100 * max(0, upper - lower) / max(1, abs(upper))

    def to_dict(self) -> dict[str, Any]:
        result = {
            key: getattr(self, key)
            for key in ("identifier", "label", "unit", "sense", "value", "bound")
        }
        if self.status is not None:
            result["status"] = self.status
        return result

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ObjectiveSummary:
        if not isinstance(payload, dict):
            raise ValueError("An objective must be a JSON object")
        return cls(**payload)


def _objectives(values) -> tuple[ObjectiveSummary, ...]:
    if not isinstance(values, (tuple, list)) or any(
        not isinstance(value, ObjectiveSummary) for value in values
    ):
        raise ValueError("Objectives must be an ordered sequence of ObjectiveSummary records")
    result = tuple(values)
    if len({value.identifier for value in result}) != len(result):
        raise ValueError("Objective identifiers must be unique within a case")
    return result


@dataclass(frozen=True, slots=True)
class SolverSummary:
    algorithm: str
    status: str
    seconds: float
    objective: float | None
    bound: float | None
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, report: dict[str, Any]) -> SolverSummary:
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
    objectives: tuple[ObjectiveSummary, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "objectives", _objectives(self.objectives))


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
    objectives: tuple[ObjectiveSummary, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "objectives", _objectives(self.objectives))
        self._validate_objective_feasibility()
        proved_prefix = True
        for objective in self.objectives:
            objective.validate_status(self.solver.status)
            proved = (objective.status or self.solver.status) == "OPTIMAL"
            if proved and not proved_prefix:
                raise ValueError("A later objective cannot be proved before earlier priorities")
            if self.solver.status == "OPTIMAL" and not proved:
                raise ValueError("An optimal case requires every objective to be proved")
            proved_prefix = proved_prefix and proved

    def _validate_objective_feasibility(self) -> None:
        statuses = {objective.status or self.solver.status for objective in self.objectives}
        statuses.add(self.solver.status)
        if "INFEASIBLE" in statuses and (
            statuses & {"OPTIMAL", "FEASIBLE", "UNBOUNDED"}
            or any(objective.value is not None for objective in self.objectives)
        ):
            raise ValueError("An infeasible case or stage contradicts a feasible objective")

    def to_dict(self) -> dict[str, Any]:
        """Retain the existing JSON schema at the public process/export boundary."""
        result = {
            "request": self.request.to_dict(),
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
        if self.objectives:
            result["objectives"] = [objective.to_dict() for objective in self.objectives]
        return result

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CaseResult:
        data = dict(payload)
        data["request"] = RunConfig.from_dict(data["request"])
        data["solver"] = SolverSummary.from_dict(data["solver"])
        data["buildings"] = [BuildingSelection(**item) for item in data["buildings"]]
        if "objectives" in data:
            if not isinstance(data["objectives"], (tuple, list)):
                raise ValueError("Objectives must be an ordered JSON array")
            data["objectives"] = tuple(
                ObjectiveSummary.from_dict(item) for item in data["objectives"]
            )
        return cls(**data)
