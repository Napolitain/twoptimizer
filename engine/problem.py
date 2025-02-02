import enum
from pathlib import Path
from time import perf_counter_ns
from typing import List

from pulp import LpProblem, LpMaximize, PULP_CBC_CMD

from engine.building import Building
from engine.enums import EntryType
from engine.games import Games
from engine.province import Province


class ProblemState(enum.Enum):
    INIT = 0
    PROVINCES_ADDED = 1
    BUILDINGS_ADDED = 2
    FILTERS_ADDED = 3
    CONSTRAINTS_ADDED = 4
    OBJECTIVE_ADDED = 5
    SOLVED = 6


class Problem:
    def __init__(self):
        """
        Init a linear programming problem.
        """
        self.provinces: List[Province] = []
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        self.state = ProblemState.INIT
        self.global_time = 0
        Games.problem = self.problem

    def add_province(self, province: Province) -> None:
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        self.provinces.append(province)
        self.state = ProblemState.PROVINCES_ADDED

    def add_provinces(self, file_tsv: Path) -> None:
        """
        Add all provinces to the problem.
        :param file_tsv: file containing the provinces schema, usually start_pos_region_slot_templates_table.tsv
        :return:
        """
        dictionary_provinces = Games.instance.get_parser().parse_start_pos_tsv(file_tsv)
        for province in dictionary_provinces.values():
            self.add_province(province)

    def add_buildings(self) -> None:
        """
        Add all buildings to the problem.
        :return: None
        """
        if self.state != ProblemState.PROVINCES_ADDED:
            raise ValueError("Provinces must be added first.")
        for province in self.provinces:
            for region in province.regions:
                region.add_buildings()
        self.state = ProblemState.BUILDINGS_ADDED

    def buildings(self) -> List[Building]:
        """
        Return all buildings in the problem that are potentially built. Basically, will be all our LpVariables.
        :return:
        """
        return [building for province in self.provinces for region in province.regions for building in region.buildings]

    def add_objective(self) -> None:
        """
        Add the objective function to the problem.
        Objective function: Maximize GDP on LpVariables (buildings) that are remaining.
        After this, we CANNOT change the buildings anymore, because LpVariables are already factored in the objective function.
        :return: None
        """
        if self.state != ProblemState.CONSTRAINTS_ADDED:
            raise ValueError("Constraints must be added first.")
        self.problem += sum(
            building.gdp() * building.lp_variable
            for building in self.buildings()
        ), "Objective Function"
        self.state = ProblemState.OBJECTIVE_ADDED

    def reset_problem(self) -> None:
        self.problem = LpProblem("GDP Maximization", LpMaximize)
        self.state = ProblemState.INIT
        Games.problem = self.problem

    def solve(self, verbose=False, timing=False) -> None:
        """
        Solve the problem.
        :return: None
        """
        if self.state != ProblemState.OBJECTIVE_ADDED:
            raise ValueError("Objective must be added first.")
        solver = PULP_CBC_CMD(msg=verbose)
        start_time = perf_counter_ns()
        self.problem.solve(solver)
        end_time = perf_counter_ns()
        if timing:
            print(f"Solving time: {(end_time - start_time) / 1_000_000_000} seconds")
        self.state = ProblemState.SOLVED
        self.global_time += end_time - start_time

    def print_problem_xy(self) -> None:
        """
        Print the number of variables and constraints in the problem.
        :return: None
        """
        print(
            f"Number of variables: {len(self.problem.variables())}\nNumber of constraints: {len(self.problem.constraints)}\n")

    def get_problem_answers(self) -> List[tuple[str, str]]:
        """
        Return the variables equal to 1 with their respective contribution.
        :return: list of tuples (region_name, building_name)
        """
        if self.state != ProblemState.SOLVED:
            raise ValueError("Problem must be solved first.")
        answers = []
        for v in self.problem.variables():
            name = Games.instance.get_parser().get_entry_name(v.name, EntryType.BUILDING)
            if v.varValue == 1:
                answers.append(
                    (Games.instance.get_parser().get_entry_name(v.name, EntryType.REGION),
                     Games.buildings[Games.instance.get_campaign().value[1]][name]))
        return answers

    def print_problem_answers(self):
        """
        Print the variables equal to 1 with their respective contribution.
        :return:
        """
        problem_answers = self.get_problem_answers()
        for region_name, building_name in problem_answers:
            print(f"{region_name}: {building_name}")
