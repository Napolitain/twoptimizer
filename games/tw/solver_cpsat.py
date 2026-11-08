"""Native CP-SAT backend for the existing Total War modeling interface."""

from dataclasses import dataclass

from games.tw.competition import solve
from games.tw.solver_ortools import SolverOrTools


@dataclass(frozen=True)
class SolutionVariable:
    variable_name: str
    value: float | None

    def name(self):
        return self.variable_name

    def solution_value(self):
        if self.value is None:
            raise RuntimeError("No feasible solver solution is available")
        return self.value


class SolverCpSat(SolverOrTools):
    """Reuse linear expression construction, then solve with native CP-SAT.

    The inherited SAT MPSolver only builds/exports the binary model. Decimal
    coefficients are scaled exactly and the returned layout is validated against
    the original coefficients before it is exposed.
    """

    algorithm = "cp-sat"

    def __init__(self):
        super().__init__()
        self.result = None

    def solve(self, seconds=None, seed=0, workers=None, **kwargs):
        if kwargs:
            raise TypeError(f"Unsupported {self.algorithm} options: {sorted(kwargs)}")
        model = self.binary_model()
        self.result = solve(model, self.algorithm, seconds=seconds, seed=seed, workers=workers)
        if self.result.values is None:
            raise RuntimeError(
                f"{self.algorithm} returned {self.result.status}: "
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
            raise RuntimeError("No feasible solver solution is available")
        return self.result.objective
