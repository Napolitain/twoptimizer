"""Selection-derived domains and resource implications against explicit alternatives."""

from itertools import combinations, product
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st
from ortools.linear_solver import pywraplp

from games.tw.three_kingdoms.catalog import load_data
from games.tw.three_kingdoms.compiler import Compiler
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.scenario import Commandery, Scenario
from games.tw.three_kingdoms.selection import SelectionBounds, guaranteed_resources


def small_holding(*, automatic=False, slots=2):
    buildings = {
        key: SimpleNamespace(
            role=role,
            superchain=chain,
            kind="city" if role == "primary" else role,
            level=level,
            provided_resources=resources,
        )
        for key, role, chain, level, resources in (
            ("town", "primary", "city", 1, ("tea",)),
            ("city", "primary", "city", 2, ("tea", "copper")),
            ("fish", "port", "port", 1, ("fish",)),
            ("trade", "port", "port", 2, ("fish", "silk")),
            ("farm1", "district", "farm", 1, ()),
            ("farm2", "district", "farm", 2, ()),
            ("market", "district", "market", 1, ("spice",)),
            ("office", "district", "office", 1, ()),
        )
    }
    province = SimpleNamespace(id="p", city_level=None if automatic else 1)
    return SimpleNamespace(
        candidates={"county": buildings},
        regions={"county": SimpleNamespace(commandery="p")},
        provinces={"p": province},
        scenario=SimpleNamespace(external_resources=("jade",)),
        data=SimpleNamespace(
            commanderies={"p": SimpleNamespace(capital="county")},
            rules=SimpleNamespace(
                city_levels={1: SimpleNamespace(slots=slots), 2: SimpleNamespace(slots=slots + 1)}
            ),
        ),
        role=lambda county, building: building.role,
    )


def selection_bounds(economy):
    solver = pywraplp.Solver.CreateSolver("SAT")
    choices = {
        (county, key): solver.BoolVar(key)
        for county, buildings in economy.candidates.items()
        for key in buildings
    }
    # Keep the owner alive while reading names from its native variables.
    return SelectionBounds(economy, choices)


def possible_selections(district_slots):
    districts = ("farm1", "farm2", "market", "office")
    for count in range(district_slots + 1):
        for chosen in combinations(districts, count):
            if {"farm1", "farm2"} <= set(chosen):
                continue
            for primary, port in product(("town", "city"), ("fish", "trade")):
                yield primary, port, *chosen


@given(st.lists(st.integers(-20, 20), min_size=9, max_size=9))
def test_signed_duplicate_and_missing_terms_match_enumerated_selection_extrema(amounts):
    bounds = selection_bounds(small_holding())
    names = ("town", "city", "fish", "trade", "farm1", "farm2", "market", "office", "town")
    terms = [(amount, name) for amount, name in zip(amounts, names, strict=True) if amount]
    actual = [
        sum(amount for amount, name in terms if name in selected)
        for selected in possible_selections(1)
    ]
    assert bounds.bounds(terms) == (min(actual), max(actual))


def test_automatic_city_capacity_and_optional_empty_districts_bound_all_levels():
    bounds = selection_bounds(small_holding(automatic=True))
    terms = [(20, "farm1"), (30, "farm2"), (10, "market"), (-12, "office")]
    actual = [
        sum(amount for amount, name in terms if name in selected)
        for selected in possible_selections(2)
    ]
    assert bounds.bounds(terms) == (min(actual), max(actual)) == (-12, 40)
    assert bounds.bounds([]) == (0, 0)


def test_mandatory_harbour_consumes_the_only_district_slot():
    bounds = selection_bounds(small_holding(slots=1))
    assert bounds.bounds([(50, "market"), (-50, "office")]) == (0, 0)


def test_only_resources_shared_by_every_mandatory_alternative_are_guaranteed():
    holding = small_holding()
    assert guaranteed_resources(holding) == {"tea", "fish", "jade"}
    # An unupgraded settlement with no supply prevents the tea implication.
    holding.candidates["county"]["town"].provided_resources = ()
    assert guaranteed_resources(holding) == {"fish", "jade"}
    # A port becomes optional by being an ordinary district in this scenario.
    for key in ("fish", "trade"):
        holding.candidates["county"][key].role = "district"
    assert guaranteed_resources(holding) == {"jade"}


def test_full_holding_resource_reduction_keeps_optional_requirements():
    data = load_data()
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao",
            tuple(Commandery(key, city_level=None) for key in data["commanderies"]),
        )
    )
    compiler = Compiler(model)
    proto = compiler.compile()
    resource_rows = [row for row in proto.constraint if row.name.startswith("__resource:")]
    assert len(resource_rows) == 5
    assert all("tea" not in row.name for row in resource_rows)
    assert any("artisans" in row.name for row in resource_rows)
    assert any("entrepreneurs" in row.name for row in resource_rows)
    assert sum(row.name == "__realm_food" for row in proto.constraint) == 1


def test_changan_domains_respect_selection_limits_and_fixed_population_effects():
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao",
            (Commandery("3k_main_province_changan", city_level=None),),
        )
    )
    compiler = Compiler(model)
    compiler.compile()
    county = model.data.commanderies["3k_main_province_changan"].capital
    assert compiler.quantity("wealth", county, "peasantry").upper <= 430
    assert compiler.quantity("wealth", county, "commerce").upper <= 170
    # Population contributes a fixed +65% peasantry modifier at one million.
    modifier = compiler.quantity("wealth_percent", county, "peasantry", offset=100)
    assert modifier.lower == 165
    assert modifier.upper >= modifier.lower


@pytest.mark.parametrize(("city_level", "needs_tea"), [(1, False), (5, True), (None, True)])
def test_missing_tea_keeps_requirements_for_available_consumers(city_level, needs_tea):
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao",
            (Commandery("3k_main_province_changan", city_level=city_level),),
        )
    )
    proto = model.compile()
    assert (
        any("tea" in row.name for row in proto.constraint if row.name.startswith("__resource:"))
        == needs_tea
    )
