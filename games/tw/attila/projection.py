"""Necessary local bounds from relaxed rows, using optimistic external domains."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from ortools.sat.python import cp_model

from games.optimization.native_model import (
    SAFE_INTEGER,
    UnsupportedNativeModel,
    constraint_variables,
)


@dataclass(frozen=True)
class _Row:
    terms: dict[int, tuple[int, int, int]]
    minimum: int
    maximum: int
    lower: int | None
    upper: int | None

    @property
    def impossible(self):
        return (self.lower is not None and self.lower > self.maximum) or (
            self.upper is not None and self.upper < self.minimum
        )


def _domain(variable):
    values = tuple(variable.domain)
    if not values or len(values) % 2 or any(abs(value) >= SAFE_INTEGER for value in values):
        raise UnsupportedNativeModel("Projection needs safely bounded integer domains")
    intervals = tuple(zip(values[::2], values[1::2], strict=True))
    if any(lower > upper for lower, upper in intervals) or any(
        left[1] >= right[0] for left, right in pairwise(intervals)
    ):
        raise UnsupportedNativeModel("Projection variable domains must be ordered intervals")
    return intervals


def _row(original, index, fixed):
    if (
        not isinstance(index, int)
        or isinstance(index, bool)
        or not 0 <= index < len(original.proto.constraints)
    ):
        raise UnsupportedNativeModel("Unknown projection row")
    row = original.proto.constraints[index]
    if not row.has_linear() or row.enforcement_literal or len(row.linear.domain) != 2:
        raise UnsupportedNativeModel("Projection requires a plain contiguous linear row")
    constraint_variables(row, len(original.proto.variables))
    coefficients = defaultdict(int)
    for variable, amount in zip(row.linear.vars, row.linear.coeffs, strict=True):
        coefficients[variable] += amount
    lower, upper = tuple(row.linear.domain)
    lower = None if lower == cp_model.INT_MIN else lower
    upper = None if upper == cp_model.INT_MAX else upper
    if any(value is not None and abs(value) >= SAFE_INTEGER for value in (lower, upper)):
        raise UnsupportedNativeModel("Projection row bounds exceed safe integer scaling")
    return _ranges(original, coefficients, fixed, lower, upper)


def _ranges(original, coefficients, fixed, lower, upper):
    terms, minimum, maximum, activity = {}, 0, 0, 0
    for index, coefficient in coefficients.items():
        intervals = _domain(original.proto.variables[index])
        lo, hi = intervals[0][0], intervals[-1][1]
        if index in fixed:
            value = fixed[index]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not any(a <= value <= b for a, b in intervals)
            ):
                raise UnsupportedNativeModel(
                    "Projection fixed value is outside its original domain"
                )
            lo = hi = value
        low, high = sorted((coefficient * lo, coefficient * hi))
        minimum += low
        maximum += high
        activity += max(abs(low), abs(high))
        if index not in fixed and coefficient:
            terms[index] = (coefficient, low, high)
    if activity >= SAFE_INTEGER:
        raise UnsupportedNativeModel("Projection row exceeds safe integer activity")
    return _Row(terms, minimum, maximum, lower, upper)


def _local(row, selected, remapping):
    indices = row.terms.keys() & selected
    minimum = sum(row.terms[index][1] for index in indices)
    maximum = sum(row.terms[index][2] for index in indices)
    lower = None if row.lower is None else row.lower - (row.maximum - maximum)
    upper = None if row.upper is None else row.upper - (row.minimum - minimum)
    if (lower is not None and lower > maximum) or (upper is not None and upper < minimum):
        return False
    lower = lower if lower is not None and lower > minimum else None
    upper = upper if upper is not None and upper < maximum else None
    if lower is None and upper is None:
        return None
    if any(index not in remapping for index in indices):
        raise UnsupportedNativeModel("Projection omitted a local variable")
    terms = tuple((remapping[index], row.terms[index][0]) for index in sorted(indices))
    return terms, lower, upper


class ProjectionRows:
    """Compile external extrema once; each component visits only intersecting rows."""

    def __init__(self, original, fixed, rows):
        self.rows = tuple(_row(original, index, fixed) for index in dict.fromkeys(rows))
        self.by_variable = defaultdict(set)
        self.impossible = any(row.impossible for row in self.rows)
        for number, row in enumerate(self.rows):
            for index in row.terms:
                self.by_variable[index].add(number)

    def apply(self, model, original_indices, local_indices):
        remapping = {original: local for local, original in enumerate(original_indices)}
        if len(remapping) != len(original_indices) or len(original_indices) != len(
            model.proto.variables
        ):
            raise UnsupportedNativeModel("Projection needs an exact local variable mapping")
        if self.impossible:
            model.add(False)
            return 1
        selected = set(local_indices)
        rows = {number for index in selected for number in self.by_variable.get(index, ())}
        planned = [_local(self.rows[number], selected, remapping) for number in sorted(rows)]
        count = 0
        for row in planned:
            if row is None:
                continue
            if row is False:
                model.add(False)
            else:
                terms, lower, upper = row
                expression = sum(
                    amount * model.get_int_var_from_proto_index(index) for index, amount in terms
                )
                model.add_linear_constraint(
                    expression,
                    cp_model.INT_MIN if lower is None else lower,
                    cp_model.INT_MAX if upper is None else upper,
                )
            count += 1
        return count


def project(original, model, original_indices, local_indices, fixed, rows):
    """Add only necessary, nonredundant projections; leave the original model intact."""
    return ProjectionRows(original, fixed, rows).apply(model, original_indices, local_indices)
