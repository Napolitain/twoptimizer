"""Explicit exact product definitions alongside the canonical linear formulation."""

from dataclasses import dataclass
from math import isfinite

from ortools.linear_solver.python.linear_solver_natural_api import OFFSET_KEY


def integer(value):
    if not isfinite(value) or int(value) != value:
        raise ValueError("Product metadata requires finite integer coefficients")
    return int(value)


@dataclass(frozen=True, slots=True)
class Factor:
    terms: tuple[tuple[int, int], ...]
    offset: int
    lower: int
    upper: int

    @classmethod
    def from_quantity(cls, quantity):
        expression = quantity.expression
        if isinstance(expression, (int, float)):
            return cls((), integer(expression), integer(quantity.lower), integer(quantity.upper))
        coefficients = expression.GetCoeffs()
        terms = tuple(
            (variable.index(), integer(coefficient))
            for variable, coefficient in coefficients.items()
            if variable is not OFFSET_KEY and coefficient
        )
        return cls(
            terms,
            integer(coefficients.get(OFFSET_KEY, 0)),
            integer(quantity.lower),
            integer(quantity.upper),
        )

    def value(self, values):
        return self.offset + sum(coefficient * values[index] for index, coefficient in self.terms)


@dataclass(frozen=True, slots=True)
class Product:
    target: int
    left: Factor
    right: Factor
    bits: tuple[int, ...]
    selected: tuple[int, ...]
    rows: tuple[int, ...]

    @property
    def auxiliaries(self):
        return (*self.bits, *self.selected)
