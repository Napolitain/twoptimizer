"""Native HiGHS backend for the shared binary Total War modeling interface."""

from games.tw.solver_cpsat import SolverCpSat


class SolverHighs(SolverCpSat):
    """Reuse construction and validation, with HiGHS solving the reference MILP."""

    algorithm = "highs"
