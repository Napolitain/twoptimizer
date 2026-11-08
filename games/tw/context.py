"""Dependencies owned by one game/model, never by the process."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import SimpleNamespace
from typing import TYPE_CHECKING

from games.tw.enums import NameType

if TYPE_CHECKING:
    from games.tw.catalog import BuildingTemplate
    from games.tw.models.game import Game
    from games.tw.solver_cpsat import SolverCpSat
    from games.tw.solver_ortools import SolverOrTools
    from games.tw.solver_pulp import SolverPulp

    type Solver = SolverPulp | SolverOrTools | SolverCpSat


@dataclass(eq=False, slots=True)
class GameContext:
    """Game data and model settings passed explicitly to engine objects.

    Catalog entries are shared read-only. Each compiled problem owns its solver,
    settings and decision objects; copying a context never copies the catalog.
    """

    instance: Game | SimpleNamespace | None = None
    buildings: Mapping[str, Mapping[str, BuildingTemplate]] | None = None
    problem: Solver | None = None
    fertility: float = 5
    legacy_effects: bool = False
    name_type: NameType = NameType.NAME
    _identifiers: dict[str, int] = field(default_factory=lambda: defaultdict(int), repr=False)

    def current(self) -> Game | SimpleNamespace:
        if self.instance is None:
            raise ValueError("No game selected")
        return self.instance

    @property
    def solver(self) -> Solver:
        if self.problem is None:
            raise ValueError("Create a problem before compiling constraints")
        return self.problem

    def next_id(self, prefix: str) -> str:
        self._identifiers[prefix] += 1
        return f"{prefix}{self._identifiers[prefix]}"

    def for_problem(self, *, fertility: float | None = None) -> GameContext:
        return replace(
            self,
            problem=None,
            fertility=self.fertility if fertility is None else fertility,
            _identifiers=defaultdict(int),
        )
