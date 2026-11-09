"""Construct Attila's exact reference model and attach its compact CP-SAT plan."""

from ortools.linear_solver import pywraplp


class BinaryBuilder:
    def __init__(self):
        # This container constructs the exact reference MILP. Shared backends
        # solve its exported BinaryModel and validate every incumbent.
        self.solver = pywraplp.Solver.CreateSolver("SAT")
        if self.solver is None:
            raise ValueError("OR-Tools SAT model container is unavailable")
        self.solver.Objective().SetMaximization()
        self.pending_buildings: list[str] = []
        self.product_definitions = {}
        self.product_constraint_indices = set()
        self.compact_economy = None
        self.technologies: frozenset[str] | None = None
        self.disabled_technologies: set[str] = set()
        self.require_income_metadata = False
        self.catalogue_exclusions: list[dict] = []

    def register_building(self, name: str) -> None:
        """Remember candidate order until availability filters have finished."""
        self.pending_buildings.append(name)

    def create_constraint(
        self,
        name: str,
        variables: list,
        constraint_fn=None,
    ):
        """Add a linear row, preserving reference-model insertion order."""
        if constraint_fn is None:
            raise ValueError("Constraint function is required.")
        self.solver.Add(constraint_fn(self.solver.Sum(variables)))

    def assign_buildings(self, buildings):
        """Allocate variables only for candidates that survived availability filters."""
        buildings = {building.get_name(): building for building in buildings.values()}
        for name in self.pending_buildings:
            building = buildings.get(name)
            if building is not None:
                building.lp_variable = self.solver.BoolVar(name)
        self.pending_buildings.clear()

    def create_product(self, left, right, name):
        result = self.solver.BoolVar(name)
        self.product_definitions[result.name()] = (left.name(), right.name())
        for expression in (result <= left, result <= right, result >= left + right - 1):
            constraint = self.solver.Add(expression)
            self.product_constraint_indices.add(constraint.index())
        return result

    def binary_model(self):
        """Keep the reference MILP and attach an equivalent compact CP model."""
        from games.optimization.competition import BinaryModel

        model = BinaryModel.from_solver(self.solver)
        if self.compact_economy is not None:
            from games.tw.attila.compact import CompactIncome

            model.cp_sat_plan = CompactIncome(
                self.compact_economy,
                self.product_definitions,
                self.product_constraint_indices,
            )
        return model

    def add_objective_terms(self, terms):
        self.solver.Maximize(self.solver.Sum(terms))

    def create_auxiliary(self, name):
        return self.solver.BoolVar(name)
