"""Typed source and economic report shapes at Rome II boundaries."""

from collections.abc import Mapping, Sequence
from typing import NotRequired, TypedDict


class RawEffect(TypedDict):
    id: str
    value: int
    scope: str


class Occurrence(TypedDict):
    culture: str
    category: str
    chain_title: str
    factions: Sequence[str]
    allowed_regions: NotRequired[Sequence[str]]


class BuildingRecord(TypedDict):
    id: str
    name: str
    level: int
    facts: Sequence[str]
    effects: Sequence[RawEffect]
    occurrences: Sequence[Occurrence]


class PartyRecord(TypedDict):
    facts: Sequence[str]
    playable: bool


class TraitsRecord(TypedDict):
    culture_facts: Sequence[str]
    parties: Sequence[PartyRecord]


class FactionRecord(TypedDict):
    name: str
    traits: TraitsRecord


class TechnologyRecord(TypedDict):
    facts: Sequence[str]


class TechnologyCoverage(TypedDict):
    complete_public_tree: bool


class RegionRecord(TypedDict):
    id: str
    name: str
    province_name: str
    capital_name: str
    specialty_name: str | None
    major: bool
    has_port: bool
    ordinary_slots: int
    province: str


class Catalog(TypedDict):
    buildings: Mapping[str, BuildingRecord]
    factions: Mapping[str, FactionRecord]
    technologies: Mapping[str, Mapping[str, TechnologyRecord]]
    technologies_archived: NotRequired[Mapping[str, Mapping[str, TechnologyRecord]]]
    technology_coverage: NotRequired[Mapping[str, TechnologyCoverage]]
    regions: Mapping[str, RegionRecord]
    provinces: Mapping[str, Sequence[str]]


class CategoryEconomics(TypedDict):
    base: int
    modifier_percent: int
    minor_base: int
    minor_bonus_percent: int
    modified: float


class SiteEconomics(TypedDict):
    buildings: list[str]
    ordinary_slots_used: int
    ordinary_slots_available: int
    food_contribution: int
    order_contribution: int
    growth_contribution_unvalued: int


class Economics(TypedDict):
    domestic_tax_income: float
    domestic_net_income: float
    building_maintenance: float
    effective_corruption_points: int
    modified_wealth: float
    tax_modifier_percent_net: int
    food_surplus: int
    public_order: int
    categories: dict[str, CategoryEconomics]
    party_index: int
    party_facts: list[str]
    sites: dict[str, SiteEconomics]
