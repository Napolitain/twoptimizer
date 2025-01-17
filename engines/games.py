from pulp import LpProblem, LpMaximize

from engines.enums import AttilaFactions


class Games:
    problem = LpProblem("GDP Maximization", LpMaximize)
    buildings = {}
    current_game = "att"
    faction = AttilaFactions.ATTILA_NONE
