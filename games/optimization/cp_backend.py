"""Native CP-SAT construction and exact linear-model import."""

from math import inf, isfinite, isnan

from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model


def _integer(value: float) -> int:
    if not isfinite(value) or int(value) != value:
        raise ValueError("CP-SAT requires exact integer coefficients")
    return int(value)


def _validate_row(row: linear_solver_pb2.MPConstraintProto, variable_count: int) -> None:
    bounds = row.lower_bound, row.upper_bound
    if any(isnan(value) for value in bounds) or row.lower_bound > row.upper_bound:
        raise ValueError("Constraint bounds must be ordered and not NaN")
    if row.lower_bound == inf or row.upper_bound == -inf:
        raise ValueError("Constraint requires a finite attainable activity")
    if any(index < 0 or index >= variable_count for index in row.var_index):
        raise ValueError("Constraint references an unknown variable")


class NativeCP:
    """Integer CP model with stable original-variable positions and native products."""

    def __init__(self) -> None:
        self.model = cp_model.CpModel()
        self.variables: list[cp_model.IntVar] = []

    def BoolVar(self, name: str) -> cp_model.IntVar:
        variable = self.model.new_bool_var(name)
        self.variables.append(variable)
        return variable

    def IntVar(self, lower: int, upper: int, name: str) -> cp_model.IntVar:
        variable = self.model.new_int_var(lower, upper, name)
        self.variables.append(variable)
        return variable

    def Add(self, expression: cp_model.BoundedLinearExpression | bool) -> cp_model.Constraint:
        return self.model.add(expression)

    def Maximize(self, expression: cp_model.LinearExpr | int) -> None:
        self.model.maximize(expression)

    def multiply(
        self, result: cp_model.IntVar, left: cp_model.IntVar | int, right: cp_model.IntVar | int
    ) -> None:
        self.model.add_multiplication_equality(result, [left, right])

    def clone(self) -> NativeCP:
        """Keep canonical proof inputs isolated from search hints and bound cuts."""
        copied = NativeCP()
        copied.model = self.model.clone()
        copied.variables = [
            copied.model.get_int_var_from_proto_index(index)
            for index in range(len(copied.model.proto.variables))
        ]
        return copied

    @classmethod
    def from_linear(cls, proto: linear_solver_pb2.MPModelProto) -> NativeCP:
        """Import the exact integer linearization without floating-point scaling."""
        if proto.general_constraint or proto.HasField("quadratic_objective"):
            raise ValueError("Expected linear constraints and objective")
        problem = cls()
        for variable in proto.variable:
            if not variable.is_integer:
                raise ValueError("CP-SAT requires integer variables")
            problem.IntVar(
                _integer(variable.lower_bound),
                _integer(variable.upper_bound),
                variable.name,
            )
        problem._linear_rows(proto)
        objective = _integer(proto.objective_offset) + sum(
            _integer(variable.objective_coefficient) * value
            for variable, value in zip(proto.variable, problem.variables, strict=True)
        )
        if proto.maximize:
            problem.Maximize(objective)
        else:
            problem.model.minimize(objective)
        return problem

    def _linear_rows(self, proto: linear_solver_pb2.MPModelProto) -> None:
        for row in proto.constraint:
            _validate_row(row, len(self.variables))
            expression = sum(
                _integer(amount) * self.variables[index]
                for index, amount in zip(row.var_index, row.coefficient, strict=True)
            )
            if isfinite(row.lower_bound):
                self.Add(expression >= _integer(row.lower_bound))
            if isfinite(row.upper_bound):
                self.Add(expression <= _integer(row.upper_bound))
