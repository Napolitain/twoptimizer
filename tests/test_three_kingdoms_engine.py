"""Native-backend parity and independently enumerated commandery economics."""

from dataclasses import replace
from itertools import combinations

import pytest
from ortools.linear_solver import pywraplp

from games.tw.immutable import thaw
from games.tw.three_kingdoms.catalog import load_data
from games.tw.three_kingdoms.integer import Arithmetic, Quantity
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.optimization import native_model
from games.tw.three_kingdoms.scenario import Commandery, Scenario

FACTION = "3k_main_faction_cao_cao"
PROVINCE = "3k_main_province_yingchuan"
OTHER = "3k_main_province_chenjun"


def scenario(**kwargs):
    return Scenario(FACTION, (Commandery(PROVINCE),), **kwargs)


def layout_from(report):
    return {
        county: details["buildings"]
        for province in report["commanderies"].values()
        for county, details in province["counties"].items()
    }


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_both_backends_match_exhaustive_building_choices(algorithm):
    data = thaw(load_data())
    keep = {
        "3k_city_5",
        "3k_resource_wood_farms_grain_2",
        "3k_resource_wood_farms_grain_3",
        "3k_district_artisan_workshop_state_2",
        "3k_district_market_inn_3",
        "3k_district_residential_landlords_3",
        "3k_district_residential_logistics_2",
        "3k_district_government_religion_1",
    }
    data["buildings"] = {k: b for k, b in data["buildings"].items() if k in keep}
    model = Economy(scenario(), data)
    best = float("-inf")
    capital, county = tuple(model.regions)
    districts = sorted(
        keep - {"3k_city_5", "3k_resource_wood_farms_grain_2", "3k_resource_wood_farms_grain_3"}
    )
    for count in range(5):
        for selected in combinations(districts, count):
            for farm in ("3k_resource_wood_farms_grain_2", "3k_resource_wood_farms_grain_3"):
                layout = {capital: ["3k_city_5", *selected], county: [farm]}
                try:
                    income = model.evaluate(layout)["domestic_income"]
                except ValueError:
                    continue
                best = max(best, income)
    result = model.optimize(algorithm, workers=1, seconds=10)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["domestic_income"] == pytest.approx(best)
    assert best == pytest.approx(627.75)
    assert model.evaluate(layout_from(result))["domestic_income"] == pytest.approx(best)


def test_food_is_shared_but_order_is_local():
    model = Economy(scenario())
    result = model.optimize(workers=1, seconds=10)
    row = result["commanderies"][PROVINCE]
    assert row["counties"]["3k_main_yingchuan_capital"]["food_surplus"] < 0
    assert result["food_surplus"] >= 0
    assert row["public_order"] >= 0
    stricter = Economy(replace(model.scenario, external_food=-100))
    with pytest.raises(ValueError, match="food deficit"):
        stricter.evaluate(layout_from(result))
    unhappy = Economy(
        replace(model.scenario, commanderies=(Commandery(PROVINCE, order_offset=-100),))
    )
    with pytest.raises(ValueError, match="public order"):
        unhappy.evaluate(layout_from(result))


def test_full_catalog_backend_and_native_counts():
    model = Economy(scenario())
    native, _ = native_model(model.compile())
    observed = []
    result = model.optimize(workers=1, seconds=10, on_model=observed.append)
    assert result["solver"]["status"] == "OPTIMAL"
    assert observed == [result["solver"]["model_stats"]]
    assert observed[0]["variables"] == len(native.proto.variables)
    assert observed[0]["constraints"] == len(native.proto.constraints)


def test_positive_corruption_single_commandery_needs_no_external_border():
    model = Economy(
        replace(scenario(), commanderies=(Commandery(PROVINCE, corruption_percent=70),))
    )
    result = model.optimize(workers=1, seconds=10)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["commanderies"][PROVINCE]["effective_corruption_percent"] <= 70


def test_unknown_borders_fail_closed_when_economically_relevant():
    selected = (
        Commandery(PROVINCE, city_level=8, corruption_percent=70),
        Commandery(OTHER, city_level=8, corruption_percent=70),
    )
    with pytest.raises(ValueError, match="explicit commandery adjacency"):
        Economy(Scenario(FACTION, selected, all_reforms=True))
    Economy(Scenario(FACTION, selected, all_reforms=True, adjacency=()))
    Economy(Scenario(FACTION, tuple(replace(p, corruption_percent=0) for p in selected)))


def test_input_validation_and_serialization():
    with pytest.raises(ValueError, match="City level"):
        Commandery(PROVINCE, city_level=0)
    original = scenario(
        external_resources=("3k_main_provincial_resources_copper",), capital_commandery=PROVINCE
    )
    assert Scenario.from_dict(original.to_dict()) == original
    for field in (
        "city_level",
        "population",
        "corruption_percent",
        "order_offset",
        "minimum_order",
    ):
        with pytest.raises(ValueError):
            Scenario.from_dict(
                {**original.to_dict(), "commanderies": [{"id": PROVINCE, field: float("nan")}]}
            )
        with pytest.raises(ValueError):
            Scenario.from_dict(
                {**original.to_dict(), "commanderies": [{"id": PROVINCE, field: 1.0}]}
            )
    with pytest.raises(ValueError, match="both required and forbidden"):
        scenario(required_buildings=("x",), forbidden_buildings=("x",))
    with pytest.raises(ValueError, match="Unknown external"):
        Economy(scenario(external_resources=("fake",)))


@pytest.mark.parametrize(("left", "right"), [(-3, 7), (4, -2), (0, 6), (5, 9)])
def test_integer_products_and_zero_clamp(left, right):
    solver = pywraplp.Solver.CreateSolver("SAT")
    arithmetic = Arithmetic(solver)
    x, y = solver.IntVar(-5, 5, "x"), solver.IntVar(-10, 10, "y")
    solver.Add(x == left)
    solver.Add(y == right)
    product = arithmetic.product(Quantity(x, -5, 5), Quantity(y, -10, 10), "product")
    positive = arithmetic.maximum_zero(product, "positive")
    solver.Maximize(positive.expression)
    from ortools.linear_solver import linear_solver_pb2
    from ortools.sat.python import cp_model

    proto = linear_solver_pb2.MPModelProto()
    solver.ExportModelToProto(proto)
    native, variables = native_model(proto)
    backend = cp_model.CpSolver()
    backend.parameters.num_search_workers = 1
    assert backend.solve(native) == cp_model.OPTIMAL
    assert backend.objective_value == max(0, left * right)
    values = {v.name: backend.value(x) for v, x in zip(proto.variable, variables, strict=True)}
    assert values[product.expression.name()] == left * right


def effect(metric, value, category="", scope="region"):
    return {"metric": metric, "value": value, "category": category, "scope": scope}


@pytest.fixture
def coupled_data():
    """A tiny economy with manually checkable global and adjacent interactions."""
    data = thaw(load_data())
    template = data["buildings"]["3k_city_5"]
    buildings = {}
    effects = {
        "city": [
            effect("wealth", 100, "commerce"),
            effect("food", -5, "distribution"),
            effect("population_capacity", 1000),
            effect("order", 2, scope="province"),
        ],
        "farm": [effect("food", 10, "farming")],
        "office": [effect("wealth_percent", 100, "commerce", "faction")],
        "ward": [
            effect("corruption_percent", -50, scope="province"),
            effect("corruption_percent", -50, scope="adjacent_provinces"),
        ],
    }
    for key, values in effects.items():
        buildings[key] = {
            **template,
            "id": key,
            "name": key,
            "chain": key,
            "superchain": key,
            "kind": "city" if key == "city" else "district",
            "level": 5,
            "minimum_city_level": 0,
            "upkeep": 10 if key == "farm" else 0,
            "effect_variants": [
                {
                    "group": key,
                    "priority": 0,
                    "factions": [],
                    "subcultures": [],
                    "campaigns": [],
                    "effects": values,
                }
            ],
        }
    data["buildings"] = buildings
    data["factions"][FACTION]["chains"] = list(buildings)
    data["factions"][FACTION]["leader_effects"] = []
    data["rules"]["city_levels"]["5"]["slots"] = 1
    data["regions"] = {
        key: {
            **data["regions"][key],
            "primary_superchains": ["city"],
            "secondary_superchains": ["farm", "office", "ward"],
            "port_superchains": [],
        }
        for key in (
            data["commanderies"][PROVINCE]["capital"],
            data["commanderies"][OTHER]["capital"],
        )
    }
    return data


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_joint_food_and_faction_bonus_match_manual_optimum(coupled_data, algorithm):
    options = Scenario(FACTION, (Commandery(PROVINCE), Commandery(OTHER)))
    model = Economy(options, coupled_data)
    result = model.optimize(algorithm, seconds=10, workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    # One farm supplies both cities, freeing the other slot for a factionwide
    # +100% commerce office: two base-100 cities double, less 10 farm upkeep.
    assert result["domestic_income"] == 390
    assert result["food_surplus"] == 0
    assert sum("farm" in keys for keys in layout_from(result).values()) == 1
    assert sum("office" in keys for keys in layout_from(result).values()) == 1


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_adjacent_and_own_corruption_apply_once_each(coupled_data, algorithm):
    options = Scenario(
        FACTION,
        (Commandery(PROVINCE, corruption_percent=70), Commandery(OTHER, corruption_percent=70)),
        external_food=10,
        adjacency=((PROVINCE, OTHER),),
        required_buildings=("ward",),
        forbidden_buildings=("office",),
    )
    model = Economy(options, coupled_data)
    result = model.optimize(algorithm, seconds=10, workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    # Two wards give -50 local and -50 adjacent per city, removing corruption.
    assert result["domestic_income"] == 200
    assert all(row["effective_corruption_percent"] == 0 for row in result["commanderies"].values())
    layout = layout_from(result)
    first, second = tuple(layout)
    layout[first] = ["city", "ward"]
    layout[second] = ["city"]
    evaluated = model.evaluate(layout)
    assert evaluated["domestic_income"] == 130
    assert all(
        row["effective_corruption_percent"] == 35 for row in evaluated["commanderies"].values()
    )
    isolated = Economy(replace(options, adjacency=()), coupled_data)
    assert isolated.evaluate(layout)["domestic_income"] == 95


def test_resource_prerequisites_require_actual_supply(coupled_data):
    coupled_data["buildings"]["office"]["required_resources"] = {
        "operator": "AND",
        "resources": ["3k_main_provincial_resources_copper"],
    }
    options = Scenario(
        FACTION, (Commandery(PROVINCE), Commandery(OTHER)), required_buildings=("office",)
    )
    unavailable = Economy(options, coupled_data).optimize(seconds=10, workers=1)
    assert unavailable["solver"]["status"] == "INFEASIBLE"
    supplied = replace(options, external_resources=("3k_main_provincial_resources_copper",))
    available = Economy(supplied, coupled_data).optimize(seconds=10, workers=1)
    assert available["solver"]["status"] == "OPTIMAL"
    assert available["domestic_income"] == 390


def test_cancellation_retains_a_validated_candidate():
    from games.tw.cancellation import Cancellation

    token = Cancellation()
    observed = []

    def cancel_after_candidate(objective, bound, elapsed):
        observed.append(objective)
        if objective is not None:
            token.cancel()

    model = Economy(scenario())
    result = model.optimize(
        workers=1, seconds=10, cancellation=token, on_search=cancel_after_candidate
    )
    assert token.requested
    assert any(value is not None for value in observed)
    assert result["solver"]["status"] in {"FEASIBLE", "OPTIMAL"}
    assert model.evaluate(layout_from(result))["domestic_income"] == result["domestic_income"]
