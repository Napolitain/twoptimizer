"""Bounded integer arithmetic expressed as exact mixed-integer linear constraints."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Quantity:
    expression: Any
    lower: int
    upper: int

    @classmethod
    def constant(cls, value):
        return cls(value, value, value)


class Arithmetic:
    def __init__(self, solver):
        self.solver = solver
        self.counter = 0

    def variable(self, lower, upper, label):
        self.counter += 1
        return self.solver.IntVar(lower, upper, f"{label}:{self.counter}")

    def sum(self, terms, offset=0):
        terms = list(terms)
        lower = offset + sum(min(a * q.lower, a * q.upper) for a, q in terms)
        upper = offset + sum(max(a * q.lower, a * q.upper) for a, q in terms)
        expression = offset + sum(a * q.expression for a, q in terms)
        return Quantity(expression, lower, upper)

    def materialize(self, quantity, label):
        if quantity.lower == quantity.upper:
            return Quantity.constant(quantity.lower)
        variable = self.variable(quantity.lower, quantity.upper, label)
        self.solver.Add(variable == quantity.expression)
        return Quantity(variable, quantity.lower, quantity.upper)

    def selected(self, quantity, selector):
        """Multiply a bounded integer expression by a Boolean, exactly."""
        result = self.variable(min(0, quantity.lower), max(0, quantity.upper), "selected")
        self.solver.Add(result >= quantity.lower * selector)
        self.solver.Add(result <= quantity.upper * selector)
        self.solver.Add(result >= quantity.expression - quantity.upper * (1 - selector))
        self.solver.Add(result <= quantity.expression - quantity.lower * (1 - selector))
        return result

    def product(self, left, right, label):
        """Use a binary expansion of the smaller interval, avoiding quadratic tables."""
        if left.upper - left.lower > right.upper - right.lower:
            left, right = right, left
        if left.lower == left.upper:
            return self.sum([(left.lower, right)])
        bits = (left.upper - left.lower).bit_length()
        selectors = [self.variable(0, 1, label + "_bit") for _ in range(bits)]
        self.solver.Add(
            left.expression == left.lower + sum((1 << i) * v for i, v in enumerate(selectors))
        )
        expression = left.lower * right.expression + sum(
            (1 << i) * self.selected(right, v) for i, v in enumerate(selectors)
        )
        bounds = [a * b for a in (left.lower, left.upper) for b in (right.lower, right.upper)]
        return self.materialize(Quantity(expression, min(bounds), max(bounds)), label)

    def maximum_zero(self, quantity, label):
        if quantity.lower >= 0:
            return quantity
        if quantity.upper <= 0:
            return Quantity.constant(0)
        positive = self.variable(0, 1, label + "_positive")
        result = self.variable(0, quantity.upper, label)
        self.solver.Add(result >= quantity.expression)
        self.solver.Add(result <= quantity.upper * positive)
        self.solver.Add(result <= quantity.expression - quantity.lower * (1 - positive))
        return Quantity(result, 0, quantity.upper)
