"""Immutable Shogun 2 province and faction scenario settings."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Province:
    id: str
    town_wealth: float = 0
    base_tax_percent: float = 30
    administration: float = 1
    order_offset: float = -4  # Normal-tax unrest; other unrest must be supplied.
    minimum_order: float = 0
    farm_multiplier: float | None = None  # None uses the source's native soil.


@dataclass(frozen=True, slots=True)
class Scenario:
    clan: str
    provinces: tuple[Province, ...]
    all_arts: bool = True
    religion: str | None = None
    nanban_contact: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "provinces", tuple(self.provinces))
