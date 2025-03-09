from time import perf_counter_ns
from typing import List

from pulp import PULP_CBC_CMD

from engine.building import Building
from engine.enums import ProblemState, SolverType
from engine.games import Games
from engine.province import Province
from engine.solver import Solver
from engine.solver_ortools import SolverOrTools
from engine.solver_pulp import SolverPulp


class Problem:
    def __init__(self, solver=SolverType.PULP):
        """
        Init a linear programming problem.
        """
        self.provinces: List[Province] = []
        self.solver_type = solver
        self.problem = self.get_solver()
        self.state = ProblemState.INIT
        self.global_time = 0
        Games.problem = self.problem

    def get_solver(self) -> Solver:
        if self.solver_type == SolverType.PULP:
            return SolverPulp()
        elif self.solver_type == SolverType.SCIP:
            return SolverPulp()
        elif self.solver_type == SolverType.GOOGLE:
            return SolverOrTools()
        else:
            raise ValueError("Unknown solver.")

    def add_province(self, province: Province) -> None:
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        self.provinces.append(province)
        self.state = ProblemState.PROVINCES_ADDED

    def add_provinces(self) -> None:
        """
        Add all provinces to the problem.
        :return:
        """
        for province in Games.instance.get_parser().provinces.values():
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
        self.problem.add_objective(self.buildings())
        self.state = ProblemState.OBJECTIVE_ADDED

    def reset_problem(self) -> None:
        self.problem = self.get_solver()
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
        if self.solver_type == SolverType.PULP:
            self.problem.solve(solver=solver)
        else:
            self.problem.solve()
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
            f"Number of variables: {len(self.problem.variables())}\nNumber of constraints: {len(self.problem.constraints())}\n")

    def get_problem_answers(self) -> List[tuple[str, str]]:
        """
        Return the variables equal to 1 with their respective contribution.
        :return: list of tuples (region_name, building_name)
        """
        if self.state != ProblemState.SOLVED:
            raise ValueError("Problem must be solved first.")
        return Games.problem.get_problem_answers(Games.instance.get_parser())

    def print_problem_answers(self):
        """
        Print the variables equal to 1 with their respective contribution.
        :return:
        """
        problem_answers = self.get_problem_answers()
        for region_name, building_name in problem_answers:
            print(f"{region_name}: {building_name}")

    def dump(self, path: str):
        if self.solver_type == SolverType.GOOGLE:
            # Assuming self.problem.solver is an instance of pywraplp.Solver
            if path.endswith('.lp'):
                model_str = self.problem.solver.ExportModelAsLpFormat(False)
            elif path.endswith('.mps'):
                model_str = self.problem.solver.ExportModelAsMpsFormat(False)
            else:
                raise ValueError("Unsupported file format. Use '.lp' or '.mps'.")
            with open(path, 'w') as file:
                file.write(model_str)
        elif self.solver_type == SolverType.PULP:
            self.problem.solver.writeLP(path)
        else:
            raise ValueError("Unknown solver.")
