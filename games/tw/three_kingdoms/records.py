"""Immutable game-domain records, separate from the provenance-rich source JSON."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Effect:
    metric: str
    value: int
    category: str
    scope: str
    source_id: str = ""
    raw_scope: str = ""
    source_signature: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class EffectVariant:
    group: str
    priority: int
    factions: tuple[str, ...]
    subcultures: tuple[str, ...]
    campaigns: tuple[str, ...]
    effects: tuple[Effect, ...]


@dataclass(frozen=True, slots=True)
class ResourceRequirement:
    operator: str
    resources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Building:
    id: str
    name: str
    chain: str
    superchain: str
    level: int
    kind: str
    upkeep: int
    minimum_city_level: int
    faction_unique: bool
    only_in_capital: bool
    required_technologies: tuple[str, ...]
    required_resources: ResourceRequirement
    provided_resources: tuple[str, ...]
    effect_variants: tuple[EffectVariant, ...]


@dataclass(frozen=True, slots=True)
class Faction:
    id: str
    subculture: str
    chains: tuple[str, ...]
    leader_effects: tuple[Effect, ...]
    faction_effects: tuple[Effect, ...]


@dataclass(frozen=True, slots=True)
class Reform:
    id: str
    subculture: str
    faction: str
    effects: tuple[Effect, ...]


@dataclass(frozen=True, slots=True)
class Region:
    id: str
    battle_name: str
    commandery: str
    primary_superchains: tuple[str, ...]
    secondary_superchains: tuple[str, ...]
    port_superchains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Commandery:
    name: str
    capital: str


@dataclass(frozen=True, slots=True)
class PopulationBand:
    minimum: int
    maximum: int
    public_order: int
    peasantry_percent: int


@dataclass(frozen=True, slots=True)
class CityLevel:
    slots: int


@dataclass(frozen=True, slots=True)
class Rules:
    population_unit: int
    population_bands: tuple[PopulationBand, ...]
    city_levels: Mapping[int, CityLevel]

    def __post_init__(self) -> None:
        object.__setattr__(self, "city_levels", MappingProxyType(dict(self.city_levels)))


@dataclass(frozen=True, slots=True)
class Catalog:
    buildings: Mapping[str, Building]
    factions: Mapping[str, Faction]
    reforms: Mapping[str, Reform]
    regions: Mapping[str, Region]
    commanderies: Mapping[str, Commandery]
    resources: frozenset[str]
    rules: Rules

    def __post_init__(self) -> None:
        for field in ("buildings", "factions", "reforms", "regions", "commanderies"):
            object.__setattr__(self, field, MappingProxyType(dict(getattr(self, field))))
