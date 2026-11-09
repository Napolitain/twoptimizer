"""Validate raw catalog shapes once before they enter the game model."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import pairwise

from games.tw.immutable import freeze
from games.tw.three_kingdoms.records import (
    Building,
    Catalog,
    CityLevel,
    Commandery,
    Effect,
    EffectVariant,
    Faction,
    PopulationBand,
    Reform,
    Region,
    ResourceRequirement,
    Rules,
)


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be an object with string keys")
    return value


@dataclass(frozen=True, slots=True)
class _Reader:
    values: Mapping[str, object]
    path: str

    def value(self, key: str) -> object:
        if key not in self.values:
            raise ValueError(f"Missing {self.path}.{key}")
        return self.values[key]

    def text(self, key: str) -> str:
        value = self.value(key)
        if not isinstance(value, str):
            raise ValueError(f"{self.path}.{key} must be text")
        return value

    def integer(self, key: str) -> int:
        value = self.value(key)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{self.path}.{key} must be an integer")
        return value

    def boolean(self, key: str) -> bool:
        value = self.value(key)
        if not isinstance(value, bool):
            raise ValueError(f"{self.path}.{key} must be a boolean")
        return value

    def sequence(self, key: str) -> tuple[object, ...]:
        value = self.value(key)
        if not isinstance(value, (tuple, list)):
            raise ValueError(f"{self.path}.{key} must be a sequence")
        return tuple(value)

    def strings(self, key: str) -> tuple[str, ...]:
        values = self.sequence(key)
        if any(not isinstance(value, str) for value in values):
            raise ValueError(f"{self.path}.{key} must contain text")
        return tuple(value for value in values if isinstance(value, str))

    def child(self, key: str) -> _Reader:
        path = f"{self.path}.{key}"
        return _Reader(_mapping(self.value(key), path), path)

    def children(self, key: str) -> tuple[_Reader, ...]:
        return tuple(
            _Reader(_mapping(value, f"{self.path}.{key}[{index}]"), f"{self.path}.{key}[{index}]")
            for index, value in enumerate(self.sequence(key))
        )

    def option(self, key: str, allowed: set[str]) -> str:
        value = self.text(key)
        if value not in allowed:
            raise ValueError(f"Unsupported {self.path}.{key}: {value}")
        return value


def _source_fields(values: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(sorted((key, _source_value(value)) for key, value in values.items()))


def _source_value(value: object) -> object:
    """Immutable comparison identity preserving raw source mapping/sequence equality."""
    if isinstance(value, Mapping):
        return ("mapping", _source_fields(_mapping(value, "effect source metadata")))
    if isinstance(value, list):
        return ("list", tuple(_source_value(item) for item in value))
    if isinstance(value, tuple):
        return ("tuple", tuple(_source_value(item) for item in value))
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Effect source metadata must contain JSON-compatible values")


def _effect(row: _Reader) -> Effect:
    return Effect(
        row.option(
            "metric",
            {
                "wealth",
                "wealth_percent",
                "food",
                "food_percent",
                "order",
                "corruption_percent",
                "population_capacity",
                "slots",
                "unmodeled",
            },
        ),
        row.integer("value"),
        row.text("category"),
        row.option(
            "scope",
            {
                "region",
                "province",
                "faction",
                "adjacent_provinces",
                "enemy_adjacent_provinces",
                "unmodeled",
            },
        ),
        row.text("effect") if "effect" in row.values else "",
        row.text("raw_scope") if "raw_scope" in row.values else "",
        _source_fields(row.values),
    )


def _effects(row: _Reader, key: str) -> tuple[Effect, ...]:
    return tuple(_effect(effect) for effect in row.children(key))


def _variant(row: _Reader) -> EffectVariant:
    return EffectVariant(
        row.text("group"),
        row.integer("priority"),
        row.strings("factions"),
        row.strings("subcultures"),
        row.strings("campaigns"),
        _effects(row, "effects"),
    )


def _building(row: _Reader) -> Building:
    requirement = row.child("required_resources")
    return Building(
        row.text("id"),
        row.text("name"),
        row.text("chain"),
        row.text("superchain"),
        row.integer("level"),
        row.text("kind"),
        row.integer("upkeep"),
        row.integer("minimum_city_level"),
        row.boolean("faction_unique"),
        row.boolean("only_in_capital"),
        row.strings("required_technologies"),
        ResourceRequirement(
            requirement.option("operator", {"AND", "OR"}), requirement.strings("resources")
        ),
        row.strings("provided_resources"),
        tuple(_variant(variant) for variant in row.children("effect_variants")),
    )


def _faction(row: _Reader) -> Faction:
    return Faction(
        row.text("id"),
        row.text("subculture"),
        row.strings("chains"),
        _effects(row, "leader_effects") if "leader_effects" in row.values else (),
        _effects(row, "faction_effects") if "faction_effects" in row.values else (),
    )


def _reform(row: _Reader) -> Reform:
    return Reform(
        row.text("id"), row.text("subculture"), row.text("faction"), _effects(row, "effects")
    )


def _region(row: _Reader) -> Region:
    return Region(
        row.text("id"),
        row.text("battle_name"),
        row.text("commandery"),
        row.strings("primary_superchains"),
        row.strings("secondary_superchains"),
        row.strings("port_superchains"),
    )


def _commandery(row: _Reader) -> Commandery:
    return Commandery(row.text("name"), row.text("capital"))


def _band(row: _Reader) -> PopulationBand:
    band = PopulationBand(
        row.integer("minimum"),
        row.integer("maximum"),
        row.integer("public_order"),
        row.integer("peasantry_percent"),
    )
    if band.minimum < 0 or band.maximum < band.minimum:
        raise ValueError(f"Invalid population interval in {row.path}")
    return band


def _rules(row: _Reader) -> Rules:
    unit = row.integer("population_unit")
    if unit <= 0:
        raise ValueError("Population unit must be positive")
    bands = tuple(_band(band) for band in row.children("population_bands"))
    if not bands or bands[0].minimum != 0:
        raise ValueError("Population bands must start at zero")
    if any(right.minimum != left.maximum + 1 for left, right in pairwise(bands)):
        raise ValueError("Population bands must be ordered and contiguous")
    levels = row.child("city_levels")
    cities = {
        _city_level_key(key): CityLevel(levels.child(key).integer("slots")) for key in levels.values
    }
    if any(level < 0 or city.slots < 0 for level, city in cities.items()):
        raise ValueError("City levels and slots cannot be negative")
    return Rules(unit, bands, cities)


def _city_level_key(key: str) -> int:
    level = int(key)
    if str(level) != key or level < 0:
        raise ValueError("City level keys must be canonical nonnegative integers")
    return level


def _records[T](root: _Reader, key: str, parse: Callable[[_Reader], T]) -> dict[str, T]:
    rows = root.child(key)
    records = {}
    for name in rows.values:
        row = rows.child(name)
        if "id" in row.values and row.text("id") != name:
            raise ValueError(f"Catalog key disagrees with {row.path}.id")
        records[name] = parse(row)
    return records


def parse_catalog(data: Mapping[str, object] | Catalog) -> Catalog:
    """Own and validate custom mappings; reuse an already parsed immutable catalog."""
    if isinstance(data, Catalog):
        return data
    root = _Reader(_mapping(freeze(data), "catalog"), "catalog")
    catalog = Catalog(
        _records(root, "buildings", _building),
        _records(root, "factions", _faction),
        _records(root, "reforms", _reform),
        _records(root, "regions", _region),
        _records(root, "commanderies", _commandery),
        frozenset(root.child("resources").values),
        _rules(root.child("rules")),
    )
    _validate_references(catalog)
    return catalog


def _validate_references(catalog: Catalog) -> None:
    for region in catalog.regions.values():
        if region.commandery not in catalog.commanderies:
            raise ValueError(f"Unknown commandery for county {region.id}: {region.commandery}")
    for building in catalog.buildings.values():
        resources = set(building.provided_resources) | set(building.required_resources.resources)
        if resources - catalog.resources:
            raise ValueError(f"Unknown resource in building {building.id}")


def parse_variant(data: Mapping[str, object]) -> EffectVariant:
    """Decode a source effect group for import audits without loading a full catalog."""
    return _variant(_Reader(data, "variant"))
