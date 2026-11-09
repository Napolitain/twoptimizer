"""Exact connected components of an explicitly relaxed integer linear model.

Only the requested rows are removed. Fixed-variable substitution and singleton
propagation preserve every remaining feasible assignment. Shared variables and
requirements therefore connect components regardless of province or party names.
No solve, incumbent, or native timeout status is interpreted here.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from math import inf, isfinite

from ortools.linear_solver import linear_solver_pb2

SAFE_INTEGER = 2**53


class UnsupportedDecomposition(ValueError):
    """The input cannot be represented by this exact integer partitioner."""


class InfeasibleRelaxation(ValueError):
    """Bounds or a retained constraint prove even the relaxed model infeasible."""


@dataclass(frozen=True, slots=True)
class Part:
    indices: tuple[int, ...]
    proto: linear_solver_pb2.MPModelProto


@dataclass(frozen=True, slots=True)
class Decomposition:
    parts: tuple[Part, ...]
    fixed: dict[int, int]
    constant: int


@dataclass(slots=True)
class _Row:
    coefficients: dict[int, int]
    lower: int | None
    upper: int | None
    source: linear_solver_pb2.MPConstraintProto


def _integer(value) -> int:
    if not isfinite(value) or int(value) != value or abs(value) >= SAFE_INTEGER:
        raise UnsupportedDecomposition("Decomposition needs integers strictly within +/-2**53")
    return int(value)


def _bound(value, unbounded) -> int | None:
    return None if value == unbounded else _integer(value)


def _linear_model(proto):
    if (
        not isinstance(proto, linear_solver_pb2.MPModelProto)
        or proto.general_constraint
        or proto.HasField("quadratic_objective")
    ):
        raise UnsupportedDecomposition("Decomposition accepts a purely linear MPModelProto")


def _domains(proto):
    domains = []
    for variable in proto.variable:
        if not variable.is_integer:
            raise UnsupportedDecomposition("Decomposition requires integer variables")
        lower, upper = _integer(variable.lower_bound), _integer(variable.upper_bound)
        if lower > upper:
            raise InfeasibleRelaxation("Empty variable domain")
        domains.append((lower, upper))
    return domains


def _rows(proto, domains, relaxed):
    rows = []
    for number, source in enumerate(proto.constraint):
        coefficients = defaultdict(int)
        if len(source.var_index) != len(source.coefficient):
            raise UnsupportedDecomposition("Constraint indices and coefficients differ")
        for index, value in zip(source.var_index, source.coefficient, strict=True):
            if not 0 <= index < len(domains):
                raise UnsupportedDecomposition("Constraint references an unknown variable")
            coefficients[index] += _integer(value)
        coefficients = {index: _integer(value) for index, value in coefficients.items() if value}
        _integer(
            sum(abs(value) * max(map(abs, domains[index])) for index, value in coefficients.items())
        )
        lower, upper = _bound(source.lower_bound, -inf), _bound(source.upper_bound, inf)
        if number not in relaxed:
            rows.append(_Row(coefficients, lower, upper, source))
    return rows


def _reduce(row, fixed):
    shift = sum(
        row.coefficients.pop(index) * fixed[index] for index in row.coefficients.keys() & fixed
    )
    if row.lower is not None:
        row.lower = _integer(row.lower - shift)
    if row.upper is not None:
        row.upper = _integer(row.upper - shift)
    if row.lower is not None and row.upper is not None and row.lower > row.upper:
        raise InfeasibleRelaxation("Contradictory constraint bounds")
    if not row.coefficients and (
        (row.lower is not None and row.lower > 0) or (row.upper is not None and row.upper < 0)
    ):
        raise InfeasibleRelaxation("A constant constraint is false")


def _tighten(row, domains):
    index, coefficient = next(iter(row.coefficients.items()))
    lower, upper = row.lower, row.upper
    if coefficient < 0:
        coefficient, lower, upper = (
            -coefficient,
            None if upper is None else -upper,
            None if lower is None else -lower,
        )
    old_lower, old_upper = domains[index]
    lower = old_lower if lower is None else max(old_lower, -(-lower // coefficient))
    upper = old_upper if upper is None else min(old_upper, upper // coefficient)
    if lower > upper:
        raise InfeasibleRelaxation("A singleton constraint has no integer value")
    domains[index] = lower, upper
    return index if lower == upper else None


def _propagate(rows, domains):
    fixed = {index: lower for index, (lower, upper) in enumerate(domains) if lower == upper}
    membership = defaultdict(list)
    for number, row in enumerate(rows):
        for index in row.coefficients:
            membership[index].append(number)
    pending = set(range(len(rows)))
    queue = deque(range(len(rows)))
    while queue:
        number = queue.popleft()
        pending.remove(number)
        row = rows[number]
        _reduce(row, fixed)
        index = _tighten(row, domains) if len(row.coefficients) == 1 else None
        if index is not None:
            fixed[index] = domains[index][0]
            for dependent in membership[index]:
                if dependent not in pending:
                    pending.add(dependent)
                    queue.append(dependent)
    return fixed


def _root(parents, index):
    while parents[index] is not None:
        parent = parents[index]
        if parents[parent] is not None:
            parents[index] = parents[parent]
        index = parent
    return index


def _components(rows, indices):
    parents = dict.fromkeys(indices)
    for row in rows:
        if row.coefficients:
            first, *others = row.coefficients
            for other in others:
                left, right = _root(parents, first), _root(parents, other)
                if left != right:
                    parents[right] = left
    groups, grouped_rows = defaultdict(list), defaultdict(list)
    for index in indices:
        groups[_root(parents, index)].append(index)
    for row in rows:
        if row.coefficients:
            grouped_rows[_root(parents, next(iter(row.coefficients)))].append(row)
    return [(tuple(group), grouped_rows[key]) for key, group in groups.items()]


def _part(original, domains, indices, rows):
    proto = linear_solver_pb2.MPModelProto(maximize=original.maximize, objective_offset=0)
    local = {index: position for position, index in enumerate(indices)}
    for index in indices:
        variable = proto.variable.add()
        variable.CopyFrom(original.variable[index])
        variable.lower_bound, variable.upper_bound = domains[index]
    for row in rows:
        target = proto.constraint.add(
            name=row.source.name,
            is_lazy=row.source.is_lazy,
            lower_bound=-inf if row.lower is None else row.lower,
            upper_bound=inf if row.upper is None else row.upper,
        )
        target.var_index.extend(local[index] for index in row.coefficients)
        target.coefficient.extend(row.coefficients.values())
    return Part(indices, proto)


def objective_upper_bound(proto) -> int:
    """A safe integer domain bound, including the supplied objective offset.

    This also applies to a component whose objective was repriced by its caller.
    It uses no native response, so an unfinished solve cannot introduce a zero bound.
    """
    _linear_model(proto)
    return _objective_bound(proto, _domains(proto))


def _objective_bound(proto, domains):
    coefficients = [_integer(variable.objective_coefficient) for variable in proto.variable]
    constant = _integer(proto.objective_offset)
    _integer(
        abs(constant)
        + sum(abs(c) * max(map(abs, d)) for c, d in zip(coefficients, domains, strict=True))
    )
    return constant + sum(
        max(c * lower, c * upper) for c, (lower, upper) in zip(coefficients, domains, strict=True)
    )


def decompose(proto, *, relaxed_rows=()) -> Decomposition:
    """Partition a copy of an integer model after dropping exactly the given rows.

    ``Part.indices`` maps local variable positions to original positions. Component
    objectives omit their offset; ``constant`` owns the original offset and fixed
    objective contribution once. All unfixed variables, including zero-profit and
    unconstrained ones, remain present. The input model is never changed.
    """
    _linear_model(proto)
    relaxed = frozenset(relaxed_rows)
    if any(type(index) is not int or not 0 <= index < len(proto.constraint) for index in relaxed):
        raise UnsupportedDecomposition("Relaxed row indices must identify existing constraints")
    domains = _domains(proto)
    _objective_bound(proto, domains)
    rows = _rows(proto, domains, relaxed)
    fixed = _propagate(rows, domains)
    constant = _integer(proto.objective_offset) + sum(
        _integer(proto.variable[index].objective_coefficient) * value
        for index, value in fixed.items()
    )
    indices = [index for index in range(len(domains)) if index not in fixed]
    parts = tuple(_part(proto, domains, group, rows) for group, rows in _components(rows, indices))
    return Decomposition(parts, fixed, constant)
