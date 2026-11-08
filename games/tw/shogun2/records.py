"""Typed public catalog records, province rules and evaluated economics."""

from collections.abc import Mapping, Sequence
from typing import NotRequired, TypedDict


class PublicRecord(TypedDict):
    id: str
    name: str
    facts: Sequence[str]
    clan_facts: NotRequired[Sequence[str]]
    requires: NotRequired[Sequence[str]]


class Catalog(TypedDict):
    factions: Mapping[str, dict[str, str]]
    buildings: Mapping[str, PublicRecord]
    technologies: Mapping[str, PublicRecord]


class ProvinceRules(TypedDict):
    id: str
    name: str
    fertility: str
    farm_multiplier: float
    has_port: bool
    specialty: str | None


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
