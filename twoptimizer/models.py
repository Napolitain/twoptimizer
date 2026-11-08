"""Typed application objects; dictionaries are reserved for engine/JSON boundaries."""

from dataclasses import asdict, dataclass, field
from typing import Any

from games.tw.attila.scenario import Scenario as CampaignScenario
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.errors import ApplicationError


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
    beam_width: int = 128
    restarts: int = 16

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
                    "beam_width",
                    "restarts",
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
    technology_profile: str = "public"
    attila: AttilaOptions = field(default_factory=AttilaOptions)
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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> CaseResult:
        data = dict(payload)
        data["request"] = RunConfig.from_dict(data["request"])
        data["solver"] = SolverSummary.from_dict(data["solver"])
        data["buildings"] = [BuildingSelection(**item) for item in data["buildings"]]
        return cls(**data)
