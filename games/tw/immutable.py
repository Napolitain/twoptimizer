"""Recursive catalog ownership with explicit JSON serialization boundaries."""

import json
from collections.abc import Iterator, Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any


class FrozenMap[K, V](Mapping[K, V]):
    """A mapping whose private backing store and nested values are read-only."""

    __slots__ = ("__values",)

    def __init__(self, values: Mapping[K, V]):
        object.__setattr__(
            self,
            "_FrozenMap__values",
            MappingProxyType({key: freeze(item) for key, item in values.items()}),
        )

    def __setattr__(self, name: str, value: object) -> None:
        raise TypeError("Catalog mappings are immutable")

    def __delattr__(self, name: str) -> None:
        raise TypeError("Catalog mappings are immutable")

    def __getitem__(self, key: K) -> V:
        return self.__values[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self.__values)

    def __len__(self) -> int:
        return len(self.__values)

    def __deepcopy__(self, memo: dict) -> "FrozenMap[K, V]":
        return self


def freeze(value: Any) -> Any:
    """Detach a JSON-like input and freeze every mapping and sequence once."""
    if isinstance(value, FrozenMap):
        return value
    if isinstance(value, Mapping):
        return FrozenMap(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    """Create caller-owned JSON containers from read-only engine data."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [thaw(item) for item in value]
    return value


def read_catalog(path: str | Path) -> FrozenMap:
    source = Path(path)
    stamp = source.stat()
    return _read_catalog(source, stamp.st_mtime_ns, stamp.st_size)


@lru_cache(maxsize=32)
def _read_catalog(path: Path, modified_ns: int, size: int) -> FrozenMap:
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("A catalog must contain a JSON object")
    return freeze(data)
