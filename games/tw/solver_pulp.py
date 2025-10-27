from pulp import LpMaximize, LpProblem, LpVariable, lpSum, value

from games.tw.enums import EntryType
from games.tw.models.model import FullEntryName
from games.tw.parser.parser import Parser
from games.tw.solver import Solver


class SolverPulp(Solver):
    def __init__(self):
        self.solver = LpProblem("GDP Maximization", LpMaximize)

    def __iadd__(self, other):
        self.solver += other
        return self

    def __isub__(self, other):
        self.solver -= other
        return self

    def variables(self):
        return self.solver.variables()

    def constraints(self):
        return self.solver.constraints

    def solve(self, **kwargs):
        return self.solver.solve(**kwargs)

    def get_objective(self):
        return value(self.solver.objective)

    def create_variable(self, name: str, cat: str) -> LpVariable:
        return LpVariable(name, cat=cat)

    def create_constraint(self, name: str, variables, variables2=None, constraint_fn=None):
        """Handles summation internally using lpSum"""
        # Sum up the variables
        expr1 = lpSum(variables)

        # If there's a second set of variables, sum that as well
        if variables2:
            expr2 = lpSum(variables2)

        # Apply the constraint function
        if constraint_fn:
            if variables2:
                # Use the constraint function with both expressions
                self.solver += constraint_fn(expr1, expr2), f"{name}_Constraint"
            else:
                # Use the constraint function with only the first expression
                self.solver += constraint_fn(expr1), f"{name}_Constraint"

    def add_objective(self, buildings):
        self.solver += sum(
            building.gdp() * building.lp_variable
            for building in buildings
        ), "Objective Function"

    def get_problem_answers(self, parser: Parser) -> list[tuple[str, str]]:
        answers = []
        for v in self.variables():
            building_name = parser.get_name_from_use_name(
                parser.get_entry_name(FullEntryName(v.name), EntryType.BUILDING),
                EntryType.BUILDING)
            region_name = parser.get_name_from_use_name(parser.get_entry_name(FullEntryName(v.name), EntryType.REGION),
                                                        EntryType.REGION)
            building_print_name = parser.get_print_name(building_name, EntryType.BUILDING)
            region_print_name = parser.get_print_name(region_name, EntryType.REGION)
            if v.varValue == 1:
                answers.append((region_print_name, building_print_name))
        return answers
