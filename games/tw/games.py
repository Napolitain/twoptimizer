from games.tw.enums import NameType
from games.tw.models.game import Game
from games.tw.solver_pulp import SolverPulp


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
