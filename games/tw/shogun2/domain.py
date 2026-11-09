"""Parse source facts and building identifiers once at the game-model boundary."""

from collections.abc import Mapping, Sequence

from games.tw.shogun2.effects import family, level, parse, unique_key
from games.tw.shogun2.records import Building, Catalog, EconomyCatalog, Effect, PublicRecord


def _texts(values: object, label: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) for v in values):
        raise ValueError(f"{label} must be a sequence of text")
    return tuple(value for value in values if isinstance(value, str))


def _facts(record: PublicRecord) -> tuple[str, ...]:
    if "facts" not in record:
        raise ValueError("A source record needs its facts sequence")
    return (*_texts(record["facts"], "facts"), *_texts(record.get("clan_facts", ()), "clan_facts"))


def _effects(facts: Sequence[str]) -> tuple[Effect, ...]:
    return tuple(effect for fact in facts if (effect := parse(fact)) is not None)


def parse_building(record: PublicRecord) -> Building:
    """Keep unsupported source facts visible; never infer economic effects from them."""
    key = record["id"]
    if not isinstance(key, str) or not key.startswith("sho_"):
        raise ValueError("A Shogun building needs a source building identifier")
    group = family(record)
    facts = _facts(record)
    recognized = tuple((fact, parse(fact)) for fact in facts)
    return Building(
        key,
        group,
        0 if group == "portuguese" else level(record),  # A land-sale transaction has no stage.
        tuple(
            url.rsplit("/", 1)[-1].removesuffix(".html")
            for url in _texts(record.get("requires", ()), "requires")
        ),
        tuple(effect for _, effect in recognized if effect is not None),
        unique_key(record),
        tuple(fact for fact, effect in recognized if effect is None),
    )


def _table(value: Mapping[str, PublicRecord], key: str) -> Mapping[str, PublicRecord]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Catalog {key} must be an object")
    for identity, row in value.items():
        if (
            not isinstance(identity, str)
            or not isinstance(row, Mapping)
            or identity != row.get("id")
        ):
            raise ValueError(f"Catalog {key} key disagrees with its source identifier")
    return value


def parse_catalog(data: Catalog | EconomyCatalog) -> EconomyCatalog:
    if isinstance(data, EconomyCatalog):
        return data
    if not isinstance(data, Mapping) or any(
        key not in data for key in ("factions", "buildings", "technologies")
    ):
        raise ValueError("A catalog needs factions, buildings and technologies")
    if not isinstance(data["factions"], Mapping):
        raise ValueError("Catalog factions must be an object")
    return EconomyCatalog(
        frozenset(data["factions"]),
        {key: parse_building(row) for key, row in _table(data["buildings"], "buildings").items()},
        {
            key: _effects(_facts(row))
            for key, row in _table(data["technologies"], "technologies").items()
        },
    )
