from pulp import LpProblem, LpMaximize

from engine.enums import AttilaFactions


class Games:
    problem = LpProblem("GDP Maximization", LpMaximize)
    buildings = {}
    current_game = "att"
    faction = AttilaFactions.ATTILA_NONE
