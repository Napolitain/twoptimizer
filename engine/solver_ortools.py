from ortools.linear_solver import pywraplp

from engine.solver import Solver


class SolverOrTools(Solver):
    def __init__(self):
        self.solver = pywraplp.Solver.CreateSolver("GLOP")  # Linear solver (supports LP problems)
        self.objective = self.solver.Objective()
        self.objective.SetMaximization()
        self.constraints_list = []  # Maintain constraints for retrieval

    def __iadd__(self, other):
        """Supports adding constraints or objective terms using `+=`."""
        if isinstance(other, pywraplp.Constraint):
            # Add the constraint to the solver
            self.solver.Add(other)
            self.constraints_list.append(other)
        elif isinstance(other, pywraplp.LinearExpr):
            # Add to the objective if it's a valid LinearExpr
            self.objective.SetCoefficient(other, 1)
        elif isinstance(other, (int, float)):  # Handle simple constants if needed
            # Convert constants into LinearExpr and add
            self.objective.SetCoefficient(self.solver.Const(other), 1)
        else:
            raise TypeError("Unsupported type for += operation")
        return self

    def __isub__(self, other):
        """Supports removing objective terms (not constraints)."""
        if isinstance(other, pywraplp.LinearExpr):
            self.objective.SetCoefficient(other, -1)  # Subtracting from the objective
        else:
            raise TypeError("Only objective terms can be subtracted.")
        return self

    def variables(self):
        """Returns all decision variables."""
        return [self.solver.LookupVariable(name) for name in self.solver.variables()]

    def constraints(self):
        """Returns all added constraints."""
        return self.constraints_list

    def solve(self, **kwargs):
        """Solves the optimization problem."""
        return self.solver.Solve(**kwargs)

    def objective(self):
        """Returns the current objective function."""
        return self.solver.Objective()

    def create_variable(self, name: str, cat: str) -> pywraplp.Variable:
        if cat == "Binary":
            return self.solver.BoolVar(name)
        elif cat == "Continuous":
            return self.solver.NumVar(0, self.solver.infinity(), name)
        else:
            raise ValueError("Unknown variable category")

    def create_constraint(self, name: str, variables: list, variables2: list = None, constraint_fn=None):
        """
        Handles summation and constraint creation using pywraplp.LinearExpr.
        """
        # Sum up the first set of variables
        expr1 = self.solver.Sum(variables)

        # If there's a second set of variables, sum that as well
        if variables2:
            expr2 = self.solver.Sum(variables2)

        # Apply the constraint function
        if constraint_fn:
            constraint = None
            if variables2:
                # Use the constraint function with both expressions
                constraint = constraint_fn(expr1, expr2)
            else:
                # Use the constraint function with only the first expression
                constraint = constraint_fn(expr1)

            # Add the constraint to the solver
            self.solver.Add(constraint)  # Corrected to Add instead of AddConstraint
            self.constraints_list.append(constraint)
        else:
            raise ValueError("Constraint function is required.")

    def add_objective(self, buildings):
        # Initialize the objective function
        self.objective.Clear()  # Clear any existing objective

        # Set the coefficients for each variable
        for building in buildings:
            if isinstance(building.lp_variable, pywraplp.Variable):
                self.objective.SetCoefficient(building.lp_variable, building.gdp())

        # Set the optimization direction to maximize
        self.objective.SetMaximization()
