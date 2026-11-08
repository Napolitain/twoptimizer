"""Configurable consumer-goods and coal-era power accounting.

The consumer-goods percentage/factor sequence and power interpolation follow
publisher descriptions linked in construction-economy.md. Factory pools, both
consumer-goods floors, power supply/demand and base outputs remain explicit
inputs: the helpers do not certify a complete target-patch rules profile.
"""

import math
from dataclasses import dataclass
from fractions import Fraction

from games.hoi4.planning.mechanics import _finite_nonnegative, _whole_nonnegative


def _finite_real(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be finite numeric input")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must fit finite float64 arithmetic") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite numeric input")
    return number


def _terms(values, label: str) -> tuple[float, ...]:
    if not isinstance(values, (tuple, list)):
        raise ValueError(f"{label} must be an ordered sequence")
    return tuple(_finite_real(value, label) for value in values)


def _reported_fraction(value: Fraction, label: str) -> float:
    try:
        return _finite_real(float(value), label)
    except OverflowError as error:
        raise ValueError(f"{label} exceeds finite float64 reporting") from error


def _modifier_sum(values: tuple[float, ...]) -> float:
    try:
        return _finite_real(math.fsum(values), "Output modifier sum")
    except OverflowError as error:
        raise ValueError("Output modifier sum exceeds finite float64 arithmetic") from error


@dataclass(frozen=True, slots=True)
class ConsumerGoodsInputs:
    factory_count_for_consumer_goods: int
    available_civilian_factories: int
    expected_fraction_terms: tuple[float, ...]
    factor_modifiers: tuple[float, ...]
    minimum_fraction: float
    minimum_factories: int

    def __post_init__(self):
        for name in (
            "factory_count_for_consumer_goods",
            "available_civilian_factories",
            "minimum_factories",
        ):
            _whole_nonnegative(getattr(self, name), name)
        for name in ("expected_fraction_terms", "factor_modifiers"):
            object.__setattr__(self, name, _terms(getattr(self, name), name))
        object.__setattr__(
            self, "minimum_fraction", _finite_nonnegative(self.minimum_fraction, "Minimum fraction")
        )
        if self.minimum_fraction > 1:
            raise ValueError("Minimum consumer-goods fraction cannot exceed one")
        if any(value < -1 for value in self.factor_modifiers):
            raise ValueError("Consumer-goods factor modifiers cannot be below -1")


@dataclass(frozen=True, slots=True)
class ConsumerGoodsBreakdown:
    expected_fraction: float
    factor_multiplier: float
    unfloored_fraction: float
    effective_fraction: float
    percentage_factory_requirement: int
    required_factories: int
    allocated_factories: int
    unmet_factory_requirement: int
    construction_factories: int


def consumer_goods(inputs: ConsumerGoodsInputs) -> ConsumerGoodsBreakdown:
    """Apply percentage floor, round down, then the explicit absolute floor.

    The profile selects both floor values. Allocation is capped at the supplied
    usable civilian pool, with any unmet requirement reported separately. Simple
    decimal fractions keep e.g. 0.29*100 from accidentally rounding down to 28.
    """
    if not isinstance(inputs, ConsumerGoodsInputs):
        raise ValueError("Consumer goods requires ConsumerGoodsInputs")
    expected = sum((Fraction(str(value)) for value in inputs.expected_fraction_terms), Fraction())
    factors = math.prod(
        (1 + Fraction(str(value)) for value in inputs.factor_modifiers), start=Fraction(1)
    )
    raw = expected * factors
    effective = max(raw, Fraction(str(inputs.minimum_fraction)))
    percentage_requirement = math.floor(effective * inputs.factory_count_for_consumer_goods)
    required = max(inputs.minimum_factories, percentage_requirement)
    allocated = min(required, inputs.available_civilian_factories)
    return ConsumerGoodsBreakdown(
        expected_fraction=_reported_fraction(expected, "Expected fraction"),
        factor_multiplier=_reported_fraction(factors, "Factor multiplier"),
        unfloored_fraction=_reported_fraction(raw, "Consumer-goods fraction"),
        effective_fraction=_reported_fraction(effective, "Effective fraction"),
        percentage_factory_requirement=percentage_requirement,
        required_factories=required,
        allocated_factories=allocated,
        unmet_factory_requirement=required - allocated,
        construction_factories=inputs.available_civilian_factories - allocated,
    )


@dataclass(frozen=True, slots=True)
class PowerInputs:
    supply: float
    demand: float
    unpowered_ic_per_factory_day: float
    powered_ic_per_factory_day: float
    output_modifier_terms: tuple[float, ...]

    def __post_init__(self):
        for name in (
            "supply",
            "demand",
            "unpowered_ic_per_factory_day",
            "powered_ic_per_factory_day",
        ):
            object.__setattr__(self, name, _finite_nonnegative(getattr(self, name), name))
        object.__setattr__(
            self, "output_modifier_terms", _terms(self.output_modifier_terms, "Output modifiers")
        )
        if self.powered_ic_per_factory_day < self.unpowered_ic_per_factory_day:
            raise ValueError("Powered base output cannot be below unpowered base output")
        if _modifier_sum(self.output_modifier_terms) < -1:
            raise ValueError("Output modifier sum below -1 requires an explicit separate rule")


@dataclass(frozen=True, slots=True)
class PowerBreakdown:
    supplied_fraction: float
    base_ic_per_factory_day: float
    modifier_sum: float
    applied_modifier_sum: float
    effective_ic_per_factory_day: float


def powered_output(inputs: PowerInputs) -> PowerBreakdown:
    """Interpolate base output; shortage scales only a positive modifier sum.

    Zero demand has no shortage penalty, matching the published 1.17.2 fix.
    Coal-to-power conversion and industrial demand are supplied, not inferred.
    """
    if not isinstance(inputs, PowerInputs):
        raise ValueError("Power accounting requires PowerInputs")
    fraction = 1.0 if inputs.demand == 0 else min(1.0, inputs.supply / inputs.demand)
    base = inputs.unpowered_ic_per_factory_day + fraction * (
        inputs.powered_ic_per_factory_day - inputs.unpowered_ic_per_factory_day
    )
    modifier_sum = _modifier_sum(inputs.output_modifier_terms)
    applied = modifier_sum * fraction if modifier_sum > 0 else modifier_sum
    output = _finite_nonnegative(base * (1 + applied), "Effective factory output")
    return PowerBreakdown(fraction, base, modifier_sum, applied, output)
