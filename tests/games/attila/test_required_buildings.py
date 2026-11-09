"""Required building counts survive compilation, search and independent evaluation."""

import pytest

from games.optimization.competition import solve
from games.tw.attila.builder import BinaryBuilder
from games.tw.attila.construction import Construction
from games.tw.attila.region import Region
from games.tw.attila.scenario import Scenario
from games.tw.attila.templates import BuildingTemplate
from tests.support.attila import building, province


def _model(context, rules, *, cubic=False, unavailable=False):
    problem = Construction(
        context=context,
        scenario={
            "regions": {key: {"minimum_sanitation": 0} for key in ("one", "two")},
            "building_rules": rules,
        },
    )
    assert isinstance(problem.builder, BinaryBuilder)
    for key in ("one", "two"):
        region = Region(key, context=problem.context)
        problem.add_province(province(key, region))
        building(
            region,
            key + "_farm",
            ("economy_gdp_agriculture_farming", "building_to_building_own", 100),
        )
        temple = building(region, key + "_temple", upkeep=25)
        if unavailable:
            problem.context.buildings = {"att": {"temple": BuildingTemplate.from_building(temple)}}
            region.buildings.remove(temple)
        if cubic:
            building(
                region,
                key + "_market",
                ("economy_gdp_mod_agriculture_farming", "province_to_region_own", 20),
            )
            building(region, key + "_tax", ("province_tax_rate", "province_to_province_own", 20))
        for candidate in region.buildings:
            candidate.lp_variable = problem.builder.solver.BoolVar(candidate.get_name())
    problem.add_objective()
    assert problem.economy is not None
    return problem.builder.binary_model(), problem.economy


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_required_unique_building_changes_income_and_retains_placement(context, algorithm):
    model, economy = _model(
        context,
        [{"buildings": ["temple"], "minimum": 1, "maximum": 1, "regions": ["two"]}],
    )
    result = solve(model, algorithm, seconds=5, workers=1)
    assert result.values is not None
    selected = {name for name, value in zip(model.names, result.values, strict=True) if value > 0.5}
    assert "two_temple" in selected and "one_temple" not in selected
    assert result.objective == pytest.approx(175)
    report = economy.evaluate_layout(selected)
    rule = report["assumptions"]["building_rules"][0]
    assert rule["minimum"] == rule["maximum"] == rule["selected_count"] == 1
    assert rule["satisfied"] and report["objective"] == pytest.approx(175)
    for invalid in (selected - {"two_temple"}, selected | {"one_temple"}):
        assert not economy.evaluate_layout(invalid)["assumptions"]["building_rules"][0]["satisfied"]


def test_minimum_is_shared_across_ids_and_omitting_it_preserves_choices(context):
    baseline, _ = _model(context, [{"buildings": ["temple"], "maximum": 1}])
    assert solve(baseline, "cp-sat", workers=1).objective == pytest.approx(200)
    shared, _ = _model(context, [{"buildings": ["farm", "temple"], "minimum": 3}])
    assert solve(shared, "cp-sat", workers=1).objective == pytest.approx(175)


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
@pytest.mark.parametrize("unavailable", [False, True])
def test_impossible_required_building_is_infeasible_not_silently_dropped(
    context, algorithm, unavailable
):
    rules = [{"buildings": ["temple"], "minimum": 1}]
    if not unavailable:
        rules.append({"buildings": ["temple"], "regions": []})
    model, _ = _model(context, rules, unavailable=unavailable)
    result = solve(model, algorithm, seconds=5, workers=1)
    assert result.status == "INFEASIBLE" and result.values is None


def test_compact_income_keeps_required_counts(context):
    model, economy = _model(
        context, [{"buildings": ["temple"], "minimum": 1, "maximum": 1}], cubic=True
    )
    result = solve(model, "cp-sat", seconds=5, workers=1)
    assert result.status == "OPTIMAL"
    assert result.model_stats["formulation"] == "factored_income"
    assert result.objective == pytest.approx(solve(model, "highs", workers=1).objective)
    assert result.values is not None
    selected = {name for name, value in zip(model.names, result.values, strict=True) if value > 0.5}
    rule = economy.evaluate_layout(selected)["assumptions"]["building_rules"][0]
    assert rule["selected_count"] == 1 and rule["satisfied"]


@pytest.mark.parametrize("minimum", [-1, True, 1.5, None, float("nan"), float("inf"), "1"])
def test_invalid_minimum_counts_are_rejected(minimum):
    with pytest.raises(ValueError, match="minimum must be a nonnegative integer"):
        Scenario({"building_rules": [{"buildings": ["temple"], "minimum": minimum}]})


def test_minimum_maximum_order_and_immutable_roundtrip():
    with pytest.raises(ValueError, match="minimum cannot exceed maximum"):
        Scenario({"building_rules": [{"buildings": ["temple"], "minimum": 2, "maximum": 1}]})
    data = {"building_rules": [{"buildings": ["temple"], "minimum": 0, "maximum": 0}]}
    scenario = Scenario(data)
    assert scenario.to_dict() == data
    data["building_rules"][0]["minimum"] = 10
    assert scenario.building_rules[0].minimum == 0
    assert Scenario(scenario.to_dict()).building_rules == scenario.building_rules
    maximum_only = {"building_rules": [{"buildings": ["temple"], "maximum": 1}]}
    assert Scenario(maximum_only).to_dict() == maximum_only
