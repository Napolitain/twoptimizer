"""Native CP-SAT backend for the existing Total War modeling interface."""

from dataclasses import dataclass

from games.tw.competition import BinaryModel, solve
from games.tw.solver_ortools import SolverOrTools


@dataclass(frozen=True)
class SolutionVariable:
    variable_name: str
    value: float | None

    def name(self):
        return self.variable_name

    def solution_value(self):
        if self.value is None:
            raise RuntimeError("No feasible CP-SAT solution is available")
        return self.value


class SolverCpSat(SolverOrTools):
    """Reuse linear expression construction, then solve with native CP-SAT.

    The inherited MPSolver only builds/exports the binary model; CBC is never
    invoked. Decimal coefficients are scaled exactly and the returned layout
    is validated against the original coefficients before it is exposed.
    """

    def __init__(self):
        super().__init__()
        self.result = None

    def solve(self, seconds=60, seed=0):
        model = BinaryModel.from_solver(self.solver)
        self.result = solve(model, "cp-sat", seconds=seconds, seed=seed)
        if self.result.values is None:
            raise RuntimeError(
                f"CP-SAT returned {self.result.status}: "
                f"{self.result.detail or 'no feasible layout available'}"
            )
        return self.result.status

    def variables(self):
        values = self.result.values if self.result is not None else None
        return [
            SolutionVariable(v.name(), None if values is None else values[i])
            for i, v in enumerate(self.solver.variables())
        ]

    def get_objective(self):
        if self.result is None or self.result.objective is None:
            raise RuntimeError("No feasible CP-SAT solution is available")
        return self.result.objective
