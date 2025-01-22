from pulp import LpProblem, LpMaximize

from engine.models.game import Game


class Games:
    problem = LpProblem("GDP Maximization", LpMaximize)
    instance = None
    buildings = None

    def set_game(self, game: Game) -> None:
        """
        Set the game to be used.
        :param game:
        :return:
        """
        self.instance = game
        self.buildings = game.parser.buildings
        self.problem = LpProblem("GDP Maximization", LpMaximize)
