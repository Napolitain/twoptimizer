"""Linear-time accumulation preserves the reference algebra and objective decomposition."""

from copy import deepcopy
from fractions import Fraction
from functools import reduce
from itertools import product

from hypothesis import given
from hypothesis import strategies as st

from games.tw.attila.algebra import Polynomial, add, sum_polynomials
from games.tw.attila.economy import Economy
from games.tw.attila.region import Region
from tests.support.attila import building, province


@given(
    st.lists(
        st.dictionaries(
            st.sampled_from([(), ("a",), ("b",), ("a", "b")]),
            st.integers(-20, 20),
        ),
        max_size=20,
    )
)
def test_accumulation_matches_ordered_reference_and_all_boolean_evaluations(parts):
    original = deepcopy(parts)
    summed = sum_polynomials(iter(parts))
    assert list(summed.items()) == list(reduce(add, parts, {}).items())
    for a, b in product((0, 1), repeat=2):
        values = {"a": a, "b": b}

        def evaluate(poly, values=values):
            return sum(value for term, value in poly.items() if all(values[k] for k in term))

        assert evaluate(summed) == sum(map(evaluate, parts))
    assert parts == original


def test_decimal_fraction_cancellation_reinserts_terms_in_reference_order():
    parts: list[Polynomial] = [
        {("a",): 0.1, ("b",): Fraction(1, 3)},
        {("a",): Fraction(-1, 10)},
        {("a",): 0.2},
    ]
    assert list(sum_polynomials(parts).items()) == [
        (("b",), Fraction(1, 3)),
        (("a",), Fraction(1, 5)),
    ]


def test_non_tax_income_preserves_explicit_income_channels(context):
    region = Region("r", context=context)
    building(region, "market", ("economy_gdp_industry", "building_to_building_own", 100), upkeep=7)
    economy = Economy(
        [province("p", region)],
        scenario={
            "technology_effects": False,
            "religion_traits": False,
            "base_tariffs": 10,
            "campaign": {"base_tribute": 25},
        },
    )
    expected = add(
        economy.objective(), {term: -amount for term, amount in economy.tax_income(region).items()}
    )
    assert economy.non_tax_income() == expected
    assert economy.evaluate(economy.non_tax_income(), set(economy.by_id)) == 28
