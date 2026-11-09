"""Explicit, immutable snapshot inputs for the historical Three Kingdoms model."""

from dataclasses import asdict, dataclass
from math import isfinite


def identifiers(values, label):
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(value, str) or not value for value in values
    ):
        raise ValueError(f"{label} must contain building IDs")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must contain distinct building IDs")
    return tuple(values)


def integer(value, label, lower, upper):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if not isfinite(value) or int(value) != value or not lower <= value <= upper:
        raise ValueError(f"{label} must be an integer between {lower} and {upper}")


@dataclass(frozen=True, slots=True)
class Commandery:
    id: str
    city_level: int = 5
    population: int = 1_000_000
    corruption_percent: int = 0
    order_offset: int = 0
    minimum_order: int = 0

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("Choose a commandery ID")
        integer(self.city_level, "City level", 1, 10)
        integer(self.population, "Population", 0, 10_000_000)
        integer(self.corruption_percent, "Base corruption", 0, 100)
        integer(self.order_offset, "Public-order offset", -1000, 1000)
        integer(self.minimum_order, "Minimum public order", -1000, 1000)


@dataclass(frozen=True, slots=True)
class Scenario:
    faction: str
    commanderies: tuple[Commandery, ...]
    capital_commandery: str | None = None
    all_reforms: bool = False
    include_leader_effects: bool = True
    external_food: int = 0
    external_resources: tuple[str, ...] = ()
    required_buildings: tuple[str, ...] = ()
    forbidden_buildings: tuple[str, ...] = ()
    adjacency: tuple[tuple[str, str], ...] | None = None

    def __post_init__(self):
        object.__setattr__(self, "commanderies", tuple(self.commanderies))
        if not self.commanderies or len({p.id for p in self.commanderies}) != len(
            self.commanderies
        ):
            raise ValueError("Choose at least one commandery without duplicates")
        if not isinstance(self.all_reforms, bool) or not isinstance(
            self.include_leader_effects, bool
        ):
            raise ValueError("Reforms and leader-effects settings must be boolean")
        integer(self.external_food, "External food", -100_000, 100_000)
        for name in ("required_buildings", "forbidden_buildings", "external_resources"):
            object.__setattr__(self, name, identifiers(getattr(self, name), name))
        if set(self.required_buildings) & set(self.forbidden_buildings):
            raise ValueError("A building cannot be both required and forbidden")
        if self.adjacency is not None:
            object.__setattr__(self, "adjacency", tuple(tuple(edge) for edge in self.adjacency))
            self._validate_adjacency()

    def _validate_adjacency(self):
        chosen = {p.id for p in self.commanderies}
        for edge in self.adjacency or ():
            if len(edge) != 2 or edge[0] == edge[1] or not set(edge) <= chosen:
                raise ValueError("Adjacency must link two different selected commanderies")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        values = dict(data)
        values["commanderies"] = tuple(Commandery(**p) for p in values["commanderies"])
        return cls(**values)
