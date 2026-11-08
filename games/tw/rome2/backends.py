"""Native CP-SAT and nonlinear SCIP model construction adapters."""

from math import isfinite

from ortools.sat.python import cp_model


class NativeCP:
    def __init__(self):
        self.model = cp_model.CpModel()
        self.variables = []

    def BoolVar(self, name):
        variable = self.model.new_bool_var(name)
        self.variables.append(variable)
        return variable

    def IntVar(self, lower, upper, name):
        variable = self.model.new_int_var(lower, upper, name)
        self.variables.append(variable)
        return variable

    def Add(self, expression):
        return self.model.add(expression)

    def Maximize(self, expression):
        self.model.maximize(expression)

    def multiply(self, result, left, right):
        self.model.add_multiplication_equality(result, [left, right])

    @classmethod
    def from_linear(cls, proto):
        """Import the exact integer linearization without floating-point scaling."""

        def integer(value):
            if not isfinite(value) or int(value) != value:
                raise ValueError("Rome II CP-SAT requires exact integer coefficients")
            return int(value)

        problem = cls()
        for variable in proto.variable:
            if not variable.is_integer:
                raise ValueError("Rome II CP-SAT requires integer variables")
            problem.IntVar(
                integer(variable.lower_bound),
                integer(variable.upper_bound),
                variable.name,
            )
        for row in proto.constraint:
            expression = sum(
                integer(amount) * problem.variables[index]
                for index, amount in zip(row.var_index, row.coefficient, strict=True)
            )
            if isfinite(row.lower_bound):
                problem.Add(expression >= integer(row.lower_bound))
            if isfinite(row.upper_bound):
                problem.Add(expression <= integer(row.upper_bound))
        problem.Maximize(
            integer(proto.objective_offset)
            + sum(
                integer(variable.objective_coefficient) * value
                for variable, value in zip(proto.variable, problem.variables, strict=True)
            )
        )
        return problem


class NativeSCIP:
    def __init__(self):
        from pyscipopt import Model

        self.model = Model("Rome II")
        self.model.hideOutput()
        self.variables = []

    def BoolVar(self, name):
        variable = self.model.addVar(name, vtype="B")
        self.variables.append(variable)
        return variable

    def IntVar(self, lower, upper, name):
        variable = self.model.addVar(name, vtype="I", lb=lower, ub=upper)
        self.variables.append(variable)
        return variable

    def Add(self, expression):
        if isinstance(expression, bool):
            if expression:
                return None
            from pyscipopt import quicksum

            expression = quicksum([]) >= 1
        return self.model.addCons(expression)

    def Maximize(self, expression):
        self.model.setObjective(expression, "maximize")

    def multiply(self, result, left, right):
        self.model.addCons(result == left * right)
