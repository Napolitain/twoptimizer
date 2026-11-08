"""Exact sparse Boolean polynomials used by the Attila economic rules."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

type Monomial = tuple[str, ...]
type Coefficient = int | float | Fraction
type Polynomial = Mapping[Monomial, Coefficient]


@dataclass(frozen=True, slots=True)
class Indicator:
    identity: tuple[tuple[Monomial, Fraction], ...]
    expression: Polynomial
    lower: Coefficient
    upper: Coefficient
    step: Fraction


def rational(value: Coefficient) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(str(value))


def add(left: Polynomial, right: Polynomial) -> dict[Monomial, Fraction]:
    result = defaultdict(Fraction, {key: rational(value) for key, value in left.items()})
    for key, value in right.items():
        result[key] += rational(value)
    return {key: value for key, value in result.items() if value}


def multiply(left: Polynomial, right: Polynomial) -> dict[Monomial, Fraction]:
    result = defaultdict(Fraction)
    for a, x in left.items():
        for b, y in right.items():
            # Decisions are Boolean: x*x == x. Sorted keys share auxiliaries.
            result[tuple(sorted(set(a) | set(b)))] += rational(x) * rational(y)
    return dict(result)
