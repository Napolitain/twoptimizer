import abc

from games.tw.parser.parser import Parser


class Solver(abc.ABC):
    technologies: frozenset[str] | None = None
    disabled_technologies: set[str]
    require_income_metadata: bool = False
    catalogue_exclusions: list[dict]

    @abc.abstractmethod
    def __init__(self):
        pass

    @abc.abstractmethod
    def __iadd__(self, other):
        pass

    @abc.abstractmethod
    def __isub__(self, other):
        pass

    @abc.abstractmethod
    def variables(self):
        pass

    @abc.abstractmethod
    def constraints(self):
        pass

    @abc.abstractmethod
    def solve(self, **kwargs):
        pass

    @abc.abstractmethod
    def get_objective(self):
        pass

    @abc.abstractmethod
    def add_objective(self, buildings):
        pass

    @abc.abstractmethod
    def create_variable(self, name: str, cat: str) -> object:
        pass

    @abc.abstractmethod
    def create_constraint(self, name: str, variables, variables2=None, constraint_fn=None):
        pass

    @abc.abstractmethod
    def get_problem_answers(self, parser: Parser):
        """
        Get the answers from the solver.
        :return: dictionary of answers
        """
        pass

    def filter_added(self, buildings):
        """Immediate-variable backends need no deferred registration."""
        return None
