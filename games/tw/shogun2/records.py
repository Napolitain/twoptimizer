"""Typed public catalog records, province rules and evaluated economics."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import NotRequired, TypedDict


class BuildingIdentity(TypedDict):
    id: str


class PublicRecord(BuildingIdentity):
    name: str
    facts: Sequence[str]
    clan_facts: NotRequired[Sequence[str]]
    requires: NotRequired[Sequence[str]]


class Catalog(TypedDict):
    factions: Mapping[str, dict[str, str]]
    buildings: Mapping[str, PublicRecord]
    technologies: Mapping[str, PublicRecord]


class Location(TypedDict):
    has_port: bool
    specialty: str | None


class ProvinceRules(Location):
    id: str
    name: str
    fertility: str
    farm_multiplier: float


class Rules(TypedDict):
    provinces: Mapping[str, ProvinceRules]
    fertility_multipliers: Mapping[str, float]
    clan_farm_percent: Mapping[str, int]
    clan_religion: Mapping[str, str]
    shared_surplus_growth_per_province: int


class GrowthComponents(TypedDict):
    buildings: int
    building_growth_bonus_percent: int
    arts: int
    shared_food_surplus: NotRequired[int]


class ProvinceEconomics(TypedDict):
    name: str
    farm_multiplier: float
    buildings: list[str]
    town_slots: int
    town_wealth: float
    farm_wealth: float
    commerce_wealth: int
    mine_wealth: int
    taxable_wealth: float
    effective_tax_percent: float
    administration_multiplier: float
    tax_income: float
    local_food_balance: int
    public_order: float
    growth_components: GrowthComponents


class Economics(TypedDict):
    domestic_tax_income: float
    food_surplus: int
    faction_arts_food: int
    farm_bonus_percent: int
    arts_tax_points: int
    religion: str
    provinces: dict[str, ProvinceEconomics]


@dataclass(frozen=True, slots=True)
class Effect:
    kind: str
    value: int
    category: str = ""


@dataclass(frozen=True, slots=True)
class Building:
    id: str
    family: str
    level: int
    prerequisites: tuple[str, ...]
    effects: tuple[Effect, ...]
    unique: str | None
    unsupported_facts: tuple[str, ...]

    def value(self, kind: str, category: str | None = None) -> int:
        return sum(
            effect.value
            for effect in self.effects
            if effect.kind == kind and (category is None or effect.category == category)
        )


@dataclass(frozen=True, slots=True)
class EconomyCatalog:
    factions: frozenset[str]
    buildings: Mapping[str, Building]
    technologies: Mapping[str, tuple[Effect, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "buildings", MappingProxyType(dict(self.buildings)))
        object.__setattr__(self, "technologies", MappingProxyType(dict(self.technologies)))
