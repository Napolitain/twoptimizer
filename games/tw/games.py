from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.tw.solver_cpsat import SolverCpSat
    from games.tw.solver_ortools import SolverOrTools

from games.tw.enums import NameType
from games.tw.models.game import Game
from games.tw.solver_pulp import SolverPulp


class Games:
    legacy_effects = False
    fertility = 5
    problem: SolverPulp | SolverOrTools | SolverCpSat = SolverPulp()
    instance: Game | SimpleNamespace | None = None
    buildings = None
    USE_NAME = NameType.NAME

    @classmethod
    def current(cls) -> Game | SimpleNamespace:
        if cls.instance is None:
            raise ValueError("No game selected")
        return cls.instance

    def set_game(self, game: Game) -> None:
        """
        Set the game to be used.
        :param game:
        :return:
        """
        self.instance = game
        self.buildings = game.parser.buildings
        self.problem: SolverPulp | SolverOrTools | SolverCpSat = SolverPulp()
