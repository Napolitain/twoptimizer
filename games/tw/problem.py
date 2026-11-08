from time import perf_counter_ns

from pulp import PULP_CBC_CMD

from games.tw.building import Building
from games.tw.context import GameContext
from games.tw.enums import ProblemState, SolverType
from games.tw.models.model_attila import AttilaCampaign
from games.tw.province import Province
from games.tw.solver_cpsat import SolverCpSat
from games.tw.solver_ortools import SolverOrTools
from games.tw.solver_pulp import SolverPulp


class Problem:
    def __init__(
        self,
        solver=SolverType.CP_SAT,
        objective=None,
        adjacency=None,
        technologies=None,
        scenario=None,
        *,
        context: GameContext | None = None,
    ):
        """
        Init a linear programming problem.
        """
        self._legacy = context is None
        if context is None:
            from games.tw.games import legacy_context

            context = legacy_context()
        self.context = context.for_problem()
        self.provinces: list[Province] = []
        if objective is None:
            campaign = getattr(self.context.instance, "campaign", None)
            objective = (
                "income" if campaign is None or isinstance(campaign, AttilaCampaign) else "legacy"
            )
        if objective not in ("legacy", "wealth", "income"):
            raise ValueError("Unknown objective mode")
        if objective == "legacy" and scenario is not None:
            raise ValueError("Scenarios require wealth or income mode")
        self.objective_mode = objective
        self.technologies = None if technologies is None else frozenset(technologies)
        self.technology_profile = None
        if objective != "legacy" and getattr(self.context.instance, "faction", None) is not None:
            from games.tw.attila.modifiers import technology_profile
            from games.tw.attila.scenario import Scenario

            scenario_data = scenario.data if isinstance(scenario, Scenario) else scenario or {}
            self.technology_profile = technology_profile(
                self.context.instance,
                technologies,
                scenario_data.get("technology_effects", True),
            )
            if self.technology_profile is not None and technologies is not None:
                self.technologies = frozenset(self.technology_profile["active"])
        self.scenario = scenario
        self.adjacency = adjacency
        self.economy = None
        self.context.legacy_effects = objective == "legacy"
        self.solver_type = solver
        self.problem = self.get_solver()
        self._configure_solver()
        self.state = ProblemState.INIT
        self.global_time = 0
        self.context.problem = self.problem
        if self._legacy:
            from games.tw.games import Games

            Games.problem = self.problem
            Games.legacy_effects = self.context.legacy_effects

    def _configure_solver(self) -> None:
        self.problem.technologies = self.technologies
        self.problem.disabled_technologies = (
            set(self.technology_profile["disabled_legacy"]) if self.technology_profile else set()
        )
        self.problem.require_income_metadata = self.objective_mode == "income"
        self.problem.catalogue_exclusions = []

    def get_solver(self) -> SolverPulp | SolverOrTools | SolverCpSat:
        if self.solver_type == SolverType.PULP:
            return SolverPulp()
        elif self.solver_type == SolverType.SCIP:
            return SolverOrTools("SCIP")
        elif self.solver_type == SolverType.GOOGLE:
            return SolverOrTools()
        elif self.solver_type == SolverType.CP_SAT:
            return SolverCpSat()
        else:
            raise ValueError("Unknown solver.")

    def add_province(self, province: Province) -> None:
        """
        Add a province to the problem.
        :param province:
        :return:
        """
        if not self._legacy:
            province._context = self.context
            for region in province.regions:
                region._context = self.context
        self.provinces.append(province)
        self.state = ProblemState.PROVINCES_ADDED

    def add_provinces(self) -> None:
        """
        Add all provinces to the problem.
        :return:
        """
        for province in self.context.current().get_parser().provinces.values():
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
                self.problem.filter_added(
                    {building.name: building for building in region.buildings}
                )
        self.state = ProblemState.BUILDINGS_ADDED

    def buildings(self) -> list[Building]:
        """
        Return all buildings in the problem that are potentially built. Basically, will be all
        our LpVariables.
        :return:
        """
        return [
            building
            for province in self.provinces
            for region in province.regions
            for building in region.buildings
        ]

    def add_objective(self) -> None:
        """
        Add the objective function to the problem.
        Objective function: Maximize GDP on LpVariables (buildings) that are remaining.
        After this, we CANNOT change the buildings anymore, because LpVariables are already
        factored in the objective function.
        :return: None
        """
        if self.state != ProblemState.CONSTRAINTS_ADDED:
            raise ValueError("Constraints must be added first.")
        if self.objective_mode == "legacy":
            self.problem.add_objective(self.buildings())
        else:
            from games.tw.attila.economy import Economy

            self.economy = Economy(
                self.provinces,
                self.adjacency,
                self.scenario,
                self.technology_profile,
                context=None if self._legacy else self.context,
            )
            self.economy.catalogue_exclusions = self.problem.catalogue_exclusions
            self.economy.install_constraints(self.problem)
            self.problem.add_objective_terms(
                self.economy.compile(self.economy.objective(self.objective_mode), self.problem)
            )
        self.state = ProblemState.OBJECTIVE_ADDED

    def reset_problem(self) -> None:
        self.problem = self.get_solver()
        self._configure_solver()
        self.provinces = []
        self.economy = None
        self.state = ProblemState.INIT
        self.context.problem = self.problem
        if self._legacy:
            from games.tw.games import Games

            Games.problem = self.problem
            Games.legacy_effects = self.context.legacy_effects

    def solve(self, verbose=False, timing=False) -> None:
        """
        Solve the problem.
        :return: None
        """
        if self.state != ProblemState.OBJECTIVE_ADDED:
            raise ValueError("Objective must be added first.")
        start_time = perf_counter_ns()
        if self.solver_type == SolverType.PULP:
            self.problem.solve(solver=PULP_CBC_CMD(msg=verbose))
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
            "Number of variables: "
            f"{len(self.problem.variables())}"
            "\nNumber of constraints: "
            f"{len(self.problem.constraints())}"
            "\n"
        )

    def get_problem_answers(self) -> list[tuple[str, str]]:
        """
        Return the variables equal to 1 with their respective contribution.
        :return: list of tuples (region_name, building_name)
        """
        if self.state != ProblemState.SOLVED:
            raise ValueError("Problem must be solved first.")
        return self.problem.get_problem_answers(self.context.current().get_parser())

    def print_problem_answers(self):
        """
        Print the variables equal to 1 with their respective contribution.
        :return:
        """
        problem_answers = self.get_problem_answers()
        for region_name, building_name in problem_answers:
            print(f"{region_name}: {building_name}")

    def dump(self, path: str):
        if isinstance(self.problem, SolverOrTools):
            # Assuming self.problem.solver is an instance of pywraplp.Solver
            if path.endswith(".lp"):
                model_str = self.problem.solver.ExportModelAsLpFormat(False)
            elif path.endswith(".mps"):
                model_str = self.problem.solver.ExportModelAsMpsFormat(False)
            else:
                raise ValueError("Unsupported file format. Use '.lp' or '.mps'.")
            with open(path, "w") as file:
                file.write(model_str)
        elif self.solver_type == SolverType.PULP:
            self.problem.solver.writeLP(path)
        else:
            raise ValueError("Unknown solver.")
