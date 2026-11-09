"""Dependencies owned by one game/model, never by the process."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import TYPE_CHECKING

from games.tw.attila.enums import NameType

if TYPE_CHECKING:
    from games.tw.attila.builder import BinaryBuilder
    from games.tw.attila.game import AttilaGame
    from games.tw.attila.templates import BuildingTemplate


@dataclass(eq=False, slots=True)
class AttilaContext:
    """Game data and model settings passed explicitly to engine objects.

    Catalog entries are shared read-only. Each compiled problem owns its solver,
    settings and decision objects; copying a context never copies the catalog.
    """

    instance: AttilaGame | SimpleNamespace | None = None
    buildings: Mapping[str, Mapping[str, BuildingTemplate]] | None = None
    builder: BinaryBuilder | None = None
    fertility: float = 5
    name_type: NameType = NameType.NAME
    _identifiers: dict[str, int] = field(default_factory=lambda: defaultdict(int), repr=False)

    def current(self) -> AttilaGame | SimpleNamespace:
        if self.instance is None:
            raise ValueError("No game selected")
        return self.instance

    def model_builder(self) -> BinaryBuilder:
        if self.builder is None:
            raise ValueError("Create a model builder before compiling constraints")
        return self.builder

    def next_id(self, prefix: str) -> str:
        self._identifiers[prefix] += 1
        return f"{prefix}{self._identifiers[prefix]}"

    def for_model(self, *, fertility: float | None = None) -> AttilaContext:
        return replace(
            self,
            builder=None,
            fertility=self.fertility if fertility is None else fertility,
            _identifiers=defaultdict(int),
        )
