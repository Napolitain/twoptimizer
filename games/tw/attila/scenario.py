"""Immutable, typed campaign inputs after validation at the JSON boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from games.tw.attila.building_rules import BuildingRule
from games.tw.attila.scenario_validation import ScenarioValidator
from games.tw.immutable import FrozenMap, freeze, thaw


@dataclass(frozen=True, slots=True)
class ProvinceInputs:
    corruption_percent: float = 0
    tax_percent: float = 100
    immigration_order: float = 0
    religious_order: float = 0
    public_order: float = 0
    food: float = 0
    minimum_food: float = 0
    minimum_public_order: float = 0


@dataclass(frozen=True, slots=True)
class RegionInputs:
    wealth_percent: Mapping[str, float] = field(default_factory=lambda: FrozenMap({}))

    immigration_wealth: float = 0
    food: float = 0
    sanitation: float = 0
    minimum_sanitation: float = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "wealth_percent", freeze(self.wealth_percent))


@dataclass(frozen=True, slots=True)
class CampaignInputs:
    province_capitals_held: int | None = None
    active_trade_routes: int = 0
    base_tribute: float = 0
    at_peace_with_sassanids: bool = False
    poor_fertility_regions: tuple[str, ...] = ()
    provided: frozenset[str] = frozenset()

    def to_dict(self) -> dict[str, Any]:
        return {key: thaw(getattr(self, key)) for key in self.provided}


@dataclass(frozen=True, slots=True)
class MetricInput:
    metric: str
    scope: str
    value: float
    target: str | None = None

    @property
    def recipient(self) -> str:
        return self.target if self.target is not None else "faction"

    def to_dict(self) -> dict[str, Any]:
        record = asdict(self)
        if self.target is None:
            del record["target"]
        return record


@dataclass(frozen=True, slots=True)
class ExternalEffect:
    effect: str
    scope: str
    amount: float
    region: str


@dataclass(frozen=True, slots=True)
class ProjectInput:
    region: str
    base_cost: float
    name: str | None = None
    sanitation: bool = False
    conversion: bool = False
    main_settlement: bool = False
    category: str | None = None


@dataclass(frozen=True, slots=True, init=False)
class Scenario:
    data: FrozenMap
    provinces: Mapping[str, ProvinceInputs]
    regions: Mapping[str, RegionInputs]
    campaign: CampaignInputs
    adjacency: Mapping[str, tuple[str, ...]]
    conditional_targets: Mapping[str, Mapping[str, tuple[str, ...]]]
    external_effects: tuple[ExternalEffect, ...]
    targets: tuple[MetricInput, ...]
    weights: tuple[MetricInput, ...]
    projects: tuple[ProjectInput, ...]
    building_rules: tuple[BuildingRule, ...]
    base_tariffs: float
    resource_prices: Mapping[str, float]
    resource_demand: Mapping[str, float]
    project_budget: float | None
    faction_traits: bool
    technology_effects: bool
    religion_traits: bool

    def __init__(self, data: Mapping | None = None):
        validated = ScenarioValidator(thaw(data)).data
        frozen = freeze(validated)
        object.__setattr__(self, "data", frozen)
        object.__setattr__(
            self,
            "provinces",
            FrozenMap(
                {key: ProvinceInputs(**value) for key, value in frozen.get("provinces", {}).items()}
            ),
        )
        object.__setattr__(
            self,
            "regions",
            FrozenMap(
                {key: RegionInputs(**value) for key, value in frozen.get("regions", {}).items()}
            ),
        )
        campaign = frozen.get("campaign", {})
        object.__setattr__(
            self, "campaign", CampaignInputs(**campaign, provided=frozenset(campaign))
        )
        for key in ("adjacency", "conditional_targets", "resource_prices", "resource_demand"):
            object.__setattr__(self, key, frozen.get(key, FrozenMap({})))
        for key, record_type in (
            ("external_effects", ExternalEffect),
            ("targets", MetricInput),
            ("weights", MetricInput),
            ("projects", ProjectInput),
            ("building_rules", BuildingRule),
        ):
            object.__setattr__(self, key, tuple(record_type(**row) for row in frozen.get(key, ())))
        object.__setattr__(self, "base_tariffs", frozen.get("base_tariffs", 0))
        object.__setattr__(self, "project_budget", frozen.get("project_budget"))
        for key in ("faction_traits", "technology_effects", "religion_traits"):
            object.__setattr__(self, key, frozen.get(key, True))

    def bind(self, provinces) -> Scenario:
        ScenarioValidator(self.to_dict()).bind(provinces)
        return self

    def to_dict(self) -> dict[str, Any]:
        return thaw(self.data)

    def for_region(self, region) -> RegionInputs:
        return self.regions.get(region.name, DEFAULT_REGION)

    def for_province(self, province) -> ProvinceInputs:
        name = province if isinstance(province, str) else province.name
        return self.provinces.get(name, DEFAULT_PROVINCE)


DEFAULT_REGION = RegionInputs()
DEFAULT_PROVINCE = ProvinceInputs()
