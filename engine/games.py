from engine.enums import NameType
from engine.models.game import Game
from engine.solver_pulp import SolverPulp


class Games:
    fertility = 5
    problem = SolverPulp()
    instance: Game = None
    buildings = None
    USE_NAME = NameType.NAME

    def set_game(self, game: Game) -> None:
        """
        Set the game to be used.
        :param game:
        :return:
        """
        self.instance = game
        self.buildings = game.parser.buildings
        self.problem = SolverPulp()
