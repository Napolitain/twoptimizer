"""Exact, fail-closed operations on integer CP-SAT subproblems.

Boolean literals encode negation as ``-index - 1``. Numeric references in the
supported OR-Tools 9.15 model format must be nonnegative; their signs belong in
coefficients. Keeping these conventions separate matters for both remapping and
independent assignment validation.
"""

from collections import defaultdict
from collections.abc import Mapping
from math import isfinite, prod

from ortools.sat.python import cp_model

SAFE_INTEGER = 2**60


class UnsupportedNativeModel(ValueError):
    """The model cannot be interpreted exactly by these native-model helpers."""


def _integer(value, *, limit=SAFE_INTEGER):
    if isinstance(value, bool) or not isfinite(value) or int(value) != value or abs(value) >= limit:
        raise UnsupportedNativeModel("Expected a safely scaled exact integer")
    return int(value)


def _index(value, count):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < count:
        raise UnsupportedNativeModel("Invalid numeric variable reference")
    return value


def _literal_index(value, count):
    return _index(value if value >= 0 else -value - 1, count)


def _kind(row):
    for kind in ("linear", "int_prod", "bool_and", "bool_or"):
        if getattr(row, "has_" + kind)():
            return kind
    raise UnsupportedNativeModel("Unsupported native constraint type")


def _intervals(domain, *, variable=False):
    values = tuple(domain)
    if len(values) % 2 or (variable and not values):
        raise UnsupportedNativeModel("Malformed native integer domain")
    intervals = tuple(zip(values[::2], values[1::2], strict=True))
    previous = None
    for lower, upper in intervals:
        if lower > upper or (previous is not None and lower <= previous + 1):
            raise UnsupportedNativeModel("Native domains must be ordered disjoint intervals")
        if variable:
            _integer(lower)
            _integer(upper)
        previous = upper
    return intervals


def _in_domain(domain, value):
    return any(lower <= value <= upper for lower, upper in _intervals(domain))


def _expression_variables(expression, count):
    if len(expression.vars) != len(expression.coeffs):
        raise UnsupportedNativeModel("Mismatched numeric references and coefficients")
    for amount in expression.coeffs:
        _integer(amount)
    return {_index(index, count) for index in expression.vars}


def constraint_variables(row, variable_count: int) -> set[int]:
    """Return all body and enforcement support, rejecting unsupported row shapes."""
    result = {_literal_index(value, variable_count) for value in row.enforcement_literal}
    kind = _kind(row)
    if kind == "linear":
        _intervals(row.linear.domain)
        result.update(_expression_variables(row.linear, variable_count))
    elif kind == "int_prod":
        for expression in (row.int_prod.target, *row.int_prod.exprs):
            _integer(expression.offset)
            result.update(_expression_variables(expression, variable_count))
    else:
        result.update(
            _literal_index(value, variable_count) for value in getattr(row, kind).literals
        )
    return result


def _header(model):
    if model.proto.assumptions or model.proto.has_symmetry():
        raise UnsupportedNativeModel("Native assumptions and explicit symmetries are unsupported")


def _boolean_domains(row, variables):
    literals = list(row.enforcement_literal)
    kind = _kind(row)
    if kind in {"bool_and", "bool_or"}:
        literals.extend(getattr(row, kind).literals)
    for literal in literals:
        domain = variables[_literal_index(literal, len(variables))].domain
        intervals = _intervals(domain, variable=True)
        if intervals[0][0] < 0 or intervals[-1][1] > 1:
            raise UnsupportedNativeModel("A Boolean literal references a non-Boolean domain")


def _objective_activity(variables, coefficients, offset):
    activity = abs(offset)
    for index, amount in coefficients.items():
        intervals = _intervals(variables[index].domain, variable=True)
        activity += abs(amount) * max(abs(intervals[0][0]), abs(intervals[-1][1]))
    if activity >= SAFE_INTEGER:
        raise UnsupportedNativeModel("Native objective exceeds safe integer activity")


def objective_terms(model) -> tuple[dict[int, int], int]:
    """Recover the exact maximizing expression from CP-SAT's signed objective."""
    _header(model)
    proto = model.proto
    if proto.has_floating_point_objective() or not proto.has_objective():
        raise UnsupportedNativeModel("Expected a native integer objective")
    objective = proto.objective
    if objective.scaling_factor != -1 and not (
        objective.scaling_factor == 1 and not objective.vars
    ):
        raise UnsupportedNativeModel("Expected unscaled maximization or a constant objective")
    if (
        objective.domain
        or objective.integer_before_offset
        or objective.integer_after_offset
        or objective.integer_scaling_factor
        or objective.scaling_was_exact
    ):
        raise UnsupportedNativeModel("Unsupported native objective scaling or domain")
    _expression_variables(objective, len(proto.variables))
    sign = int(objective.scaling_factor)
    offset = sign * _integer(objective.offset, limit=2**53)
    coefficients = defaultdict(int)
    for index, amount in zip(objective.vars, objective.coeffs, strict=True):
        coefficients[index] += sign * int(amount)
    coefficients = {index: _integer(amount) for index, amount in coefficients.items() if amount}
    _objective_activity(proto.variables, coefficients, offset)
    return coefficients, offset


def _assignment(model, values):
    variables = model.proto.variables
    if not isinstance(values, Mapping) or set(values) != set(range(len(variables))):
        return False
    return all(
        isinstance(values[index], int)
        and not isinstance(values[index], bool)
        and _in_domain(variable.domain, values[index])
        for index, variable in enumerate(variables)
    )


def objective_value(model, values: Mapping[int, int]) -> int:
    coefficients, offset = objective_terms(model)
    if not _assignment(model, values):
        raise ValueError("A complete integer assignment within variable domains is required")
    return offset + sum(amount * values[index] for index, amount in coefficients.items())


def objective_upper_bound(model) -> int:
    """Exact domain bound; independent of any native status or response defaults."""
    coefficients, offset = objective_terms(model)
    total = offset
    for index, amount in coefficients.items():
        intervals = _intervals(model.proto.variables[index].domain, variable=True)
        total += amount * (intervals[-1][1] if amount >= 0 else intervals[0][0])
    return total


def _literal(value, values):
    return values[value] == 1 if value >= 0 else values[-value - 1] == 0


def _evaluate_expression(expression, values):
    return int(expression.offset) + sum(
        int(amount) * values[index]
        for index, amount in zip(expression.vars, expression.coeffs, strict=True)
    )


def _satisfied(row, values):
    if not all(_literal(value, values) for value in row.enforcement_literal):
        return True
    kind = _kind(row)
    if kind == "linear":
        total = sum(
            int(amount) * values[index]
            for index, amount in zip(row.linear.vars, row.linear.coeffs, strict=True)
        )
        return _in_domain(row.linear.domain, total)
    if kind == "int_prod":
        return _evaluate_expression(row.int_prod.target, values) == prod(
            _evaluate_expression(expression, values) for expression in row.int_prod.exprs
        )
    literals = (_literal(value, values) for value in getattr(row, kind).literals)
    return all(literals) if kind == "bool_and" else any(literals)


def feasible(model, values: Mapping[int, int]) -> bool:
    """Evaluate every supported original constraint with exact integer arithmetic."""
    _header(model)
    variables = model.proto.variables
    for variable in variables:
        _intervals(variable.domain, variable=True)
    for row in model.proto.constraints:
        constraint_variables(row, len(variables))
        _boolean_domains(row, variables)
    # Objective domains are model constraints too; unsupported ones fail closed.
    if model.proto.has_objective() or model.proto.has_floating_point_objective():
        objective_terms(model)
    return _assignment(model, values) and all(
        _satisfied(row, values) for row in model.proto.constraints
    )


def _remap_expression(expression, remapping):
    for position, index in enumerate(expression.vars):
        expression.vars[position] = remapping[index]


def _remap_literals(literals, remapping):
    for position, literal in enumerate(literals):
        literals[position] = remapping[literal] if literal >= 0 else -remapping[-literal - 1] - 1


def _remap_row(row, remapping):
    _remap_literals(row.enforcement_literal, remapping)
    kind = _kind(row)
    if kind == "linear":
        _remap_expression(row.linear, remapping)
    elif kind == "int_prod":
        for expression in (row.int_prod.target, *row.int_prod.exprs):
            _remap_expression(expression, remapping)
    else:
        _remap_literals(getattr(row, kind).literals, remapping)


def _indices(model, variable_indices, constraint_indices, fixed):
    variables = model.proto.variables
    selected = {_index(index, len(variables)) for index in variable_indices}
    rows = tuple(_index(index, len(model.proto.constraints)) for index in constraint_indices)
    for index in fixed:
        _index(index, len(variables))
    for index in rows:
        row = model.proto.constraints[index]
        support = constraint_variables(row, len(variables))
        _boolean_domains(row, variables)
        if support - selected - fixed.keys():
            raise UnsupportedNativeModel(
                "Component constraints reference an omitted nonfixed variable"
            )
        selected.update(support & fixed.keys())
    return tuple(sorted(selected)), rows


def extract(
    model: cp_model.CpModel,
    variable_indices,
    constraint_indices,
    fixed: dict[int, int],
    objective_coefficients: dict[int, int],
) -> tuple[cp_model.CpModel, tuple[int, ...]]:
    """Copy a closed component; include fixed support and exclude its objective.

    ``objective_coefficients`` may contain the whole original objective. Only
    selected nonfixed coefficients enter the subproblem; its offset is zero.
    The caller owns the proof of each supplied fixed value and accounts for its
    objective contribution exactly once in the global bound.
    """
    _header(model)
    indices, rows = _indices(model, variable_indices, constraint_indices, fixed)
    remapping = {index: local for local, index in enumerate(indices)}
    result = cp_model.CpModel()
    for index in indices:
        source = model.proto.variables[index]
        _intervals(source.domain, variable=True)
        variable = result.proto.variables.add()
        variable.copy_from(source)
        if index in fixed:
            value = _integer(fixed[index])
            if not _in_domain(source.domain, value):
                raise UnsupportedNativeModel("Fixed value lies outside its original domain")
            variable.domain.clear()
            variable.domain.extend((value, value))
    for index in rows:
        row = result.proto.constraints.add()
        row.copy_from(model.proto.constraints[index])
        _remap_row(row, remapping)
    result.maximize(
        sum(
            _integer(objective_coefficients.get(index, 0))
            * result.get_int_var_from_proto_index(local)
            for local, index in enumerate(indices)
            if index not in fixed
        )
    )
    objective_terms(result)
    return result, indices
