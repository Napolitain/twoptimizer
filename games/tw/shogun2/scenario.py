"""Immutable Shogun 2 province and faction scenario settings."""

from dataclasses import asdict, dataclass

from games.tw.shogun2.constraints import normalize_ids


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
    required_buildings: tuple[str, ...] = ()
    forbidden_buildings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "provinces", tuple(self.provinces))
        for name in ("required_buildings", "forbidden_buildings"):
            object.__setattr__(self, name, normalize_ids(getattr(self, name), name))
        if set(self.required_buildings) & set(self.forbidden_buildings):
            raise ValueError("A building cannot be both required and forbidden")

    def to_dict(self) -> dict:
        """Keep historical default report fields; include active building constraints."""
        data = asdict(self)
        for name in ("required_buildings", "forbidden_buildings"):
            if not data[name]:
                del data[name]
        return data
