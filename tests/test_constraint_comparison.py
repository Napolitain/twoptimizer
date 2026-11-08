"""Requirement costs separate optimality proofs, incumbent changes and unknowns."""

import json
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from games.tw.attila.scenario import Scenario
from tests.support.ui import result
from twoptimizer.constraint_comparison import baseline_config, compare_results, has_requirements
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.models import AttilaOptions, BuildingSelection, CaseResult, RunConfig


def _case(config, income, *, status="OPTIMAL", upper=None, buildings=()):
    payload = result(config)
    payload.update(income=income, buildings=list(buildings), timings={})
    payload["solver"].update(status=status, objective=income, bound=upper)
    return CaseResult.from_dict(payload)


def _cases(base_income, required_income, *, base_status="OPTIMAL", required_status="OPTIMAL"):
    config = RunConfig(
        constraints=ConstraintOptions(required_buildings=("temple",)), compare_constraints=True
    )
    return (
        _case(baseline_config(config), base_income, status=base_status),
        _case(config, required_income, status=required_status),
    )


def test_baseline_removes_only_optional_requirements_and_preserves_scenario_physics():
    campaign = Scenario(
        {
            "building_rules": [{"buildings": ["campaign_temple"], "minimum": 1}],
            "targets": [{"metric": "research_percent", "scope": "faction", "value": 10}],
        }
    )
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        provinces=("att_prov_thracia", "att_prov_macedonia"),
        joint=True,
        adjacency=(("att_prov_thracia", "att_prov_macedonia"),),
        compare_constraints=True,
        constraints=ConstraintOptions(
            required_buildings=("temple",),
            forbidden_buildings=("market",),
            minimum_religious_influence=4,
        ),
        attila=AttilaOptions(campaign=campaign),
    )
    baseline = baseline_config(config)
    assert has_requirements(config) and not has_requirements(baseline)
    assert not baseline.compare_constraints and config.compare_constraints
    assert baseline.attila is config.attila and baseline.attila.campaign is campaign
    assert replace(baseline, constraints=config.constraints, compare_constraints=True) == config
    shogun = replace(
        config,
        game="shogun2",
        constraints=ConstraintOptions(
            required_buildings=("temple",), shogun_religion="christian", nanban_contact=True
        ),
    )
    assert baseline_config(shogun).constraints == ConstraintOptions(
        shogun_religion="christian", nanban_contact=True
    )
    assert not has_requirements(baseline_config(shogun))
    assert has_requirements(
        replace(config, constraints=ConstraintOptions(minimum_religious_influence=0))
    )


def test_rome_baseline_retains_required_candidates_without_requiring_them():
    config = RunConfig(
        compare_constraints=True,
        comparison_candidates=("existing", "temple"),
        constraints=ConstraintOptions(
            required_buildings=("temple", "lower_core"), forbidden_buildings=("market",)
        ),
    )
    baseline = baseline_config(config)
    assert baseline.comparison_candidates == ("existing", "lower_core", "temple")
    assert not has_requirements(baseline)
    assert baseline.constraints.required_buildings == baseline.constraints.forbidden_buildings == ()
    assert not baseline.compare_constraints
    assert baseline_config(baseline) == baseline
    permuted = replace(
        config,
        comparison_candidates=config.comparison_candidates[::-1],
        constraints=replace(config.constraints, required_buildings=("lower_core", "temple")),
    )
    assert baseline_config(permuted) == baseline


@pytest.mark.parametrize("game", ["attila", "shogun2"])
def test_other_games_do_not_need_candidate_retention(game):
    config = RunConfig(game=game, constraints=ConstraintOptions(required_buildings=("temple",)))
    assert baseline_config(config).comparison_candidates == ()


@pytest.mark.parametrize(
    "base, constrained, cost, percent", [(100, 80, 20, 20), (0, -5, 5, None), (-5, -10, 5, None)]
)
def test_exact_cost_requires_two_proven_optima(base, constrained, cost, percent):
    report = compare_results(*_cases(base, constrained))
    assert report["status"] == "exact"
    assert report["exact_cost"] == report["cost_lower"] == report["cost_upper"] == cost
    assert report["observed_income_difference"] == cost
    assert report["percent"] == percent


def test_incomplete_search_reports_bounds_without_turning_observed_difference_into_cost():
    baseline, constrained = _cases(80, 90, base_status="FEASIBLE", required_status="FEASIBLE")
    baseline = replace(baseline, solver=replace(baseline.solver, bound=120))
    constrained = replace(constrained, solver=replace(constrained.solver, bound=100))
    report = compare_results(baseline, constrained)
    assert report["status"] == "bounded" and report["exact_cost"] is None
    assert report["observed_income_difference"] == -10
    assert report["cost_lower"] == 0 and report["cost_upper"] == 30
    assert report["percent"] is None
    assert "unproved" in report["reason"]


def test_different_proof_bounds_can_establish_a_positive_minimum_cost():
    baseline, constrained = _cases(130, 80, base_status="FEASIBLE", required_status="FEASIBLE")
    baseline = replace(baseline, solver=replace(baseline.solver, bound=150))
    constrained = replace(constrained, solver=replace(constrained.solver, bound=90))
    report = compare_results(baseline, constrained)
    assert (report["cost_lower"], report["cost_upper"]) == (40, 70)
    assert report["exact_cost"] is None


@pytest.mark.parametrize("bad_bound", [None, float("nan"), float("inf"), float("-inf")])
def test_missing_or_nonfinite_upper_bound_does_not_invent_a_finite_maximum_loss(bad_bound):
    baseline, constrained = _cases(100, 90, base_status="FEASIBLE", required_status="FEASIBLE")
    baseline = replace(baseline, solver=replace(baseline.solver, bound=bad_bound))
    report = compare_results(baseline, constrained)
    assert report["status"] == "bounded"
    assert report["cost_upper"] is None and report["cost_lower"] == 0
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("status", ["UNKNOWN", "INFEASIBLE", "ERROR", "MODEL_INVALID"])
def test_missing_or_invalid_solution_is_not_reported_as_zero_cost(status):
    baseline, constrained = _cases(100, 80)
    constrained = replace(constrained, solver=replace(constrained.solver, status=status))
    report = compare_results(baseline, constrained)
    assert report["status"] == "unavailable"
    assert report["exact_cost"] is report["cost_lower"] is report["cost_upper"] is None
    assert report["observed_income_difference"] is None
    assert report["added_buildings"] == report["removed_buildings"] == []


def test_lp_relaxation_cannot_be_treated_as_a_feasible_integer_layout():
    baseline, constrained = _cases(100, 80)
    baseline = replace(baseline, solver=replace(baseline.solver, details={"relaxation": True}))
    assert compare_results(baseline, constrained)["status"] == "unavailable"


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), True])
def test_income_must_be_finite_numeric_data(value):
    baseline, constrained = _cases(100, value)
    report = compare_results(baseline, constrained)
    assert report["status"] == "unavailable" and report["constrained_income"] is None
    json.dumps(report, allow_nan=False)


def test_inconsistent_bound_or_optima_cannot_create_a_claimed_saving():
    baseline, constrained = _cases(100, 110)
    report = compare_results(baseline, constrained)
    assert report["status"] == "unavailable" and "inconsistent" in report["reason"]
    baseline, constrained = _cases(100, 80, base_status="FEASIBLE")
    baseline = replace(baseline, solver=replace(baseline.solver, bound=90))
    report = compare_results(baseline, constrained)
    assert report["status"] == "unavailable" and "upper bound" in report["reason"]


def test_rounding_tolerance_does_not_reverse_the_cost_interval():
    baseline, constrained = _cases(100, 100 + 1e-7, base_status="FEASIBLE")
    baseline = replace(baseline, solver=replace(baseline.solver, bound=100))
    report = compare_results(baseline, constrained)
    assert report["status"] == "bounded"
    assert report["cost_lower"] == report["cost_upper"] == 0


def test_changed_faith_or_source_snapshot_is_not_a_constraint_cost_comparison():
    baseline, constrained = _cases(100, 80)
    changed = replace(baseline, request=replace(baseline.request, religion="CHRIST_EAST"))
    report = compare_results(changed, constrained)
    assert report["status"] == "unavailable" and "same scenario" in report["reason"]
    changed = replace(baseline, source_files={"model.py": "first"})
    constrained = replace(constrained, source_files={"model.py": "second"})
    report = compare_results(changed, constrained)
    assert report["status"] == "unavailable" and "snapshots" in report["reason"]


def test_building_changes_compare_multisets_by_location_and_id():
    baseline, constrained = _cases(100, 80)
    market = BuildingSelection("Capital", "Market", "market")
    temple = BuildingSelection("Capital", "Temple", "temple")
    moved = BuildingSelection("Town", "Market", "market")
    baseline = replace(baseline, buildings=[market, market, temple])
    constrained = replace(constrained, buildings=[market, moved, temple, temple])
    report = compare_results(baseline, constrained)
    assert report["removed_buildings"] == [
        {"region": "Capital", "building": "Market", "id": "market"}
    ]
    assert report["added_buildings"] == [
        {"region": "Capital", "building": "Temple", "id": "temple"},
        {"region": "Town", "building": "Market", "id": "market"},
    ]


@given(
    required_optimum=st.integers(-1000, 1000),
    loss=st.integers(0, 1000),
    base_slack=st.integers(0, 1000),
    required_slack=st.integers(0, 1000),
    base_gap=st.integers(0, 1000),
    required_gap=st.integers(0, 1000),
)
def test_certified_interval_contains_true_loss_for_any_valid_nested_maximization_results(
    required_optimum, loss, base_slack, required_slack, base_gap, required_gap
):
    base_optimum = required_optimum + loss
    baseline, constrained = _cases(
        base_optimum - base_gap,
        required_optimum - required_gap,
        base_status="FEASIBLE",
        required_status="FEASIBLE",
    )
    baseline = replace(baseline, solver=replace(baseline.solver, bound=base_optimum + base_slack))
    constrained = replace(
        constrained, solver=replace(constrained.solver, bound=required_optimum + required_slack)
    )
    report = compare_results(baseline, constrained)
    assert report["status"] == "bounded"
    assert 0 <= report["cost_lower"] <= loss <= report["cost_upper"]
    assert report["exact_cost"] is None
