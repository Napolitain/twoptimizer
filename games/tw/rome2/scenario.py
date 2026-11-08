"""Immutable scenario settings and explicit sourced modifiers."""

from dataclasses import asdict, dataclass, field

from games.tw.immutable import thaw
from games.tw.rome2.building_constraints import identifiers


@dataclass(frozen=True, slots=True)
class ScenarioModifier:
    kind: str
    value: int
    targets: tuple[str, ...] = ()
    source_region: str | None = None
    name: str | None = None
    scope: str | None = None
    source_url: str | None = None
    source_line: int | None = None
    interpretation: str | None = None
    provided: frozenset[str] = field(default_factory=frozenset, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "targets", tuple(self.targets))

    @classmethod
    def from_dict(cls, record):
        known = set(cls.__dataclass_fields__) - {"provided"}
        unknown = set(record) - known
        if unknown:
            raise ValueError(f"Unknown scenario modifier fields: {sorted(unknown)}")
        return cls(
            kind=record["kind"],
            value=record["value"],
            targets=tuple(record.get("targets", ())),
            source_region=record.get("source_region"),
            name=record.get("name"),
            scope=record.get("scope"),
            source_url=record.get("source_url"),
            source_line=record.get("source_line"),
            interpretation=record.get("interpretation"),
            provided=frozenset(record),
        )

    def to_dict(self) -> dict:
        if self.provided:
            return {key: thaw(getattr(self, key)) for key in self.provided}
        return thaw(
            {
                key: value
                for key, value in asdict(self).items()
                if value is not None and key != "provided"
            }
        )


@dataclass(frozen=True, slots=True)
class Site:
    id: str
    major: bool = False
    port: bool = False
    resource: str | None = None
    slots: int | None = None  # Ordinary slots; excludes primary and port plots.

    @property
    def capacity(self):
        return self.slots if self.slots is not None else 4 if self.major else 2


@dataclass(frozen=True, slots=True)
class Scenario:
    faction: str
    sites: tuple[Site, ...]
    name: str = "Controlled province"
    all_technologies: bool = False
    core_level: int = 4
    maximum_level: int = 4
    tax_points: int = 0  # Normal taxation = 100% of modified wealth.
    corruption_points: int = 0
    order_offset: int = 0
    minimum_order: int = 0
    external_food: int = 0
    party: int | None = None  # None chooses the best playable source profile.
    technology_profile: str = "public"
    modifiers: tuple[ScenarioModifier, ...] = ()
    world_profile: str | None = None
    required_buildings: tuple[str, ...] = ()
    forbidden_buildings: tuple[str, ...] = ()
    retained_buildings: tuple[str, ...] = ()  # Optional candidates kept when relaxing requirements.

    def __post_init__(self) -> None:
        object.__setattr__(self, "sites", tuple(self.sites))
        object.__setattr__(self, "modifiers", tuple(self.modifiers))
        for key in ("required_buildings", "forbidden_buildings", "retained_buildings"):
            object.__setattr__(self, key, identifiers(getattr(self, key)))
        if set(self.required_buildings) & set(self.forbidden_buildings):
            raise ValueError("A building cannot be both required and forbidden")

    @classmethod
    def from_dict(cls, record):
        """Restore typed sites and modifiers at the saved-report JSON boundary."""
        data = dict(record)
        data["sites"] = tuple(Site(**site) for site in data["sites"])
        data["modifiers"] = tuple(
            ScenarioModifier.from_dict(modifier) for modifier in data.get("modifiers", ())
        )
        return cls(**data)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["modifiers"] = [modifier.to_dict() for modifier in self.modifiers]
        for key in ("required_buildings", "forbidden_buildings", "retained_buildings"):
            if not data[key]:
                del data[key]
        return thaw(data)
