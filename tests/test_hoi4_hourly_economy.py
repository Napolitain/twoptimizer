"""Consumer-goods factors, floors and power shortages stay inspectable."""

import math
from dataclasses import replace

import pytest

from games.hoi4.planning.economy import (
    ConsumerGoodsInputs,
    PowerInputs,
    consumer_goods,
    powered_output,
)


def test_consumer_goods_multiplies_each_factor_instead_of_summing():
    inputs = ConsumerGoodsInputs(100, 60, (0.35, -0.05), (-0.1, -0.2), 0.1, 1)
    result = consumer_goods(inputs)
    assert result.expected_fraction == pytest.approx(0.3)
    assert result.factor_multiplier == pytest.approx(0.72)
    assert result.effective_fraction == pytest.approx(0.216)
    assert result.required_factories == result.allocated_factories == 21
    assert result.construction_factories == 39 and result.unmet_factory_requirement == 0


def test_percentage_floor_then_rounding_then_explicit_absolute_floor():
    inputs = ConsumerGoodsInputs(9, 9, (0.05,), (), 0.1, 1)
    result = consumer_goods(inputs)
    assert result.unfloored_fraction == 0.05 and result.effective_fraction == 0.1
    assert result.percentage_factory_requirement == 0
    assert result.required_factories == 1 and result.construction_factories == 8
    no_floor = consumer_goods(replace(inputs, minimum_factories=0))
    assert no_floor.required_factories == 0


def test_consumer_goods_reports_an_unmet_requirement_and_never_negative_capacity():
    result = consumer_goods(ConsumerGoodsInputs(100, 5, (0.35,), (), 0.1, 1))
    assert result.required_factories == 35 and result.allocated_factories == 5
    assert result.unmet_factory_requirement == 30 and result.construction_factories == 0
    empty = consumer_goods(ConsumerGoodsInputs(0, 0, (), (), 0.1, 1))
    assert empty.allocated_factories == 0 and empty.unmet_factory_requirement == 1


def test_decimal_factor_arithmetic_does_not_accidentally_lose_a_factory():
    result = consumer_goods(ConsumerGoodsInputs(100, 50, (0.29,), (), 0, 0))
    assert result.required_factories == 29
    exact_product = consumer_goods(ConsumerGoodsInputs(100, 50, (0.5,), (-0.42,), 0, 0))
    assert exact_product.required_factories == 29


def test_inputs_defensively_freeze_modifier_sequences():
    terms = [0.35]
    inputs = replace(ConsumerGoodsInputs(100, 50, (), (), 0, 0), expected_fraction_terms=terms)
    terms.clear()
    assert inputs.expected_fraction_terms == (0.35,)


@pytest.mark.parametrize("value", [True, 1.5, "1", -1, None])
def test_consumer_goods_count_fields_reject_coercion(value):
    inputs = ConsumerGoodsInputs(100, 50, (0.35,), (), 0, 0)
    for field in (
        "factory_count_for_consumer_goods",
        "available_civilian_factories",
        "minimum_factories",
    ):
        with pytest.raises(ValueError, match="whole number"):
            replace(inputs, **{field: value})


@pytest.mark.parametrize("value", [True, None, "0.1", math.inf, math.nan])
def test_numeric_profiles_reject_nonfinite_and_coerced_inputs(value):
    goods = ConsumerGoodsInputs(10, 10, (), (), 0, 0)
    power = PowerInputs(10, 10, 4, 5, ())
    with pytest.raises(ValueError):
        replace(goods, expected_fraction_terms=(value,))
    with pytest.raises(ValueError):
        replace(goods, factor_modifiers=(value,))
    with pytest.raises(ValueError):
        replace(goods, minimum_fraction=value)
    for field in ("supply", "demand", "unpowered_ic_per_factory_day", "powered_ic_per_factory_day"):
        with pytest.raises(ValueError):
            replace(power, **{field: value})
    with pytest.raises(ValueError):
        replace(power, output_modifier_terms=(value,))


def test_invalid_floor_and_factor_profiles_are_rejected():
    goods = ConsumerGoodsInputs(10, 10, (), (), 0, 0)
    with pytest.raises(ValueError, match="exceed one"):
        replace(goods, minimum_fraction=1.1)
    with pytest.raises(ValueError, match="below -1"):
        replace(goods, factor_modifiers=(-1.1,))
    with pytest.raises(ValueError, match="ordered sequence"):
        replace(goods, expected_fraction_terms={0.35})


def test_power_shortage_interpolates_output_and_scales_positive_modifier_sum():
    result = powered_output(PowerInputs(50, 100, 4, 5, (0.4, -0.2)))
    assert result.supplied_fraction == 0.5 and result.base_ic_per_factory_day == 4.5
    assert result.modifier_sum == pytest.approx(0.2)
    assert result.applied_modifier_sum == pytest.approx(0.1)
    assert result.effective_ic_per_factory_day == pytest.approx(4.95)


def test_power_shortage_does_not_scale_nonpositive_sum():
    result = powered_output(PowerInputs(0, 100, 4, 5, (0.1, -0.3)))
    assert result.applied_modifier_sum == pytest.approx(-0.2)
    assert result.effective_ic_per_factory_day == pytest.approx(3.2)
    offsetting = powered_output(PowerInputs(0, 100, 4, 5, (0.5, -0.5)))
    assert offsetting.effective_ic_per_factory_day == 4


@pytest.mark.parametrize("supply,demand", [(0, 0), (100, 50), (100, 100)])
def test_zero_demand_and_sufficient_supply_use_powered_output(supply, demand):
    result = powered_output(PowerInputs(supply, demand, 4, 5, (0.2,)))
    assert result.supplied_fraction == 1 and result.effective_ic_per_factory_day == 6


def test_unusable_power_profile_is_rejected():
    with pytest.raises(ValueError, match="below unpowered"):
        PowerInputs(1, 1, 5, 4, ())
    with pytest.raises(ValueError, match="below -1"):
        PowerInputs(1, 1, 4, 5, (-1.1,))


def test_overflowing_arithmetic_is_reported_as_validation_failure():
    with pytest.raises(ValueError, match="finite float64"):
        PowerInputs(1, 1, 4, 5, (1e308, 1e308))
    with pytest.raises(ValueError, match="finite float64"):
        consumer_goods(ConsumerGoodsInputs(10, 10, (0.3,), (1e308, 1e308), 0, 0))


@pytest.mark.parametrize("value", [None, {}])
def test_economy_functions_require_typed_inputs(value):
    with pytest.raises(ValueError):
        consumer_goods(value)
    with pytest.raises(ValueError):
        powered_output(value)
