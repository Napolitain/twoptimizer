"""Immutable building templates, separate from mutable solver decisions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from games.tw.attila.records import BuildingMetadata
from games.tw.enums import NameType
from games.tw.immutable import freeze

if TYPE_CHECKING:
    from games.tw.building import Building
    from games.tw.context import GameContext


@dataclass(frozen=True, slots=True)
class BuildingTemplate:
    name: str
    print_name: str
    hash_name: str
    raw_effects: Mapping[tuple[str, str], float]
    metadata: BuildingMetadata | None
    effects_to_faction: Mapping[str, float]
    effects_to_province: Mapping[str, float]
    effects_to_region: Mapping[str, float]
    effects_to_building: Mapping[str, float]

    def __post_init__(self) -> None:
        for name in (
            "raw_effects",
            "metadata",
            "effects_to_faction",
            "effects_to_province",
            "effects_to_region",
            "effects_to_building",
        ):
            object.__setattr__(self, name, freeze(getattr(self, name)))

    @classmethod
    def from_building(cls, building: Building) -> BuildingTemplate:
        return cls(
            building.name,
            building.print_name,
            building.hash_name,
            freeze(building.raw_effects),
            freeze(building.metadata),
            freeze(building.effects_to_faction),
            freeze(building.effects_to_province),
            freeze(building.effects_to_region),
            freeze(building.effects_to_building),
        )

    def instantiate(self, context: GameContext) -> Building:
        from games.tw.building import Building

        building = Building(self.name, self.print_name, self.hash_name, context=context)
        building.raw_effects = dict(self.raw_effects)
        building.metadata = self.metadata
        building.effects_to_faction = dict(self.effects_to_faction)
        building.effects_to_province = dict(self.effects_to_province)
        building.effects_to_region = dict(self.effects_to_region)
        building.effects_to_building = dict(self.effects_to_building)
        return building

    def get_name(self, name_type: NameType) -> str:
        if name_type is NameType.HASH_NAME:
            return self.hash_name
        if name_type is NameType.PRINT_NAME:
            return self.print_name
        return self.name

    def get_name_output(self, name_type: NameType = NameType.NAME) -> str:
        return self.hash_name if name_type is NameType.HASH_NAME else self.print_name
