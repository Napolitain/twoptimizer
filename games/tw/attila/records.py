"""Typed imported metadata and evaluated economic report shapes."""

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class BuildingCosts(TypedDict):
    source_tree_group: str
    source_level: int
    construction_cost: int
    construction_turns: int
    upkeep: int


class EconomicObservation(TypedDict):
    kind: str
    category: str | None
    reach: str
    value: float


class BuildingMetadata(TypedDict):
    metadata: BuildingCosts
    sources: Sequence[str]
    requirements_by_culture: Mapping[str, Sequence[Sequence[str]]]
    observations_by_culture: Mapping[str, Sequence[EconomicObservation]]


class RegionFinance(TypedDict):
    wealth: float
    tax_multiplier: float
    tax_bonus_income: float
    corruption_loss: float
    tax_income: float
    building_upkeep: float
    net_income: float


class FinanceTotals(TypedDict):
    wealth: float
    tax_bonus_income: float
    corruption_loss: float
    tax_income: float
    building_upkeep: float
    net_income: float
    trade_income: float
    other_recurring_income: float


class Finances(TypedDict):
    total: FinanceTotals
    regions: dict[str, RegionFinance]


class RegionEconomics(TypedDict):
    wealth: float
    food: float
    sanitation: float
    fertility: float


class LayoutReport(TypedDict):
    finances: Finances
    faction_traits: dict[str, Any]
    catalogue_exclusions: list[dict[str, str]]
    imported_modifiers: dict[str, Any]
    assumptions: dict[str, Any]
    state_religion: str | None
    metric_semantics: str
    targets: list[dict[str, Any]]
    weighted_metrics: list[dict[str, Any]]
    metrics: dict[str, float]
    export_income: float
    project_cost: float
    objective_kind: str
    objective: float
    regions: dict[str, RegionEconomics]
    corruption_percent: dict[str, float]
    province_food: dict[str, float]
    public_order: dict[str, float]
