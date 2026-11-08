"""Native CP-SAT and nonlinear SCIP model construction adapters."""

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
