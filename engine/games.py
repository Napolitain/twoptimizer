from pulp import LpProblem, LpMaximize

from engine.enums import AttilaGame


class Games:
    problem = LpProblem("GDP Maximization", LpMaximize)
    buildings = {}
    instance = AttilaGame
