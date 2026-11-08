"""Joint search keeps certified bounds and complete feasible seeds across interruption."""

from copy import deepcopy
from time import perf_counter
from types import SimpleNamespace

import pytest
from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.tw.cancellation import Cancellation
from games.tw.rome2 import bound_search, joint_search
from games.tw.rome2.backends import NativeCP
from games.tw.rome2.bound_search import BoundSearchResult
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site


def alternatives(*, tagged=True):
    """Three feasible layouts have income 1, 2 and 3; their optimum is explicit."""
    proto = linear_solver_pb2.MPModelProto(maximize=True)
    for index in range(3):
        proto.variable.add(
            name=f"choice_{index}",
            lower_bound=0,
            upper_bound=1,
            is_integer=True,
            objective_coefficient=(index + 1) * 10000,
        )
    proto.constraint.add(
        name="one_layout",
        lower_bound=1,
        upper_bound=1,
        var_index=[0, 1, 2],
        coefficient=[1, 1, 1],
    )
    proto.constraint.add(
        name="__realm_food" if tagged else "local_food",
        lower_bound=0,
        upper_bound=float("inf"),
        var_index=[0, 1, 2],
        coefficient=[2, 1, 0],
    )
    return NativeCP.from_linear(proto), proto


def prepared_bounds(*, upper=40000, seed=1):
    return BoundSearchResult(
        upper,
        None if seed is None else {index: int(index == seed) for index in range(3)},
        {"hint_income": None if seed is None else (seed + 1) * 10000, "cuts": 0},
    )


def supply_bounds(monkeypatch, bounds):
    monkeypatch.setattr(joint_search, "_strengthen", lambda *args: bounds)


def solve(problem, proto, **options):
    return joint_search.solve(
        problem,
        proto,
        **{"seconds": None, "workers": 1, "started": perf_counter(), **options},
    )


def native_response(monkeypatch, status, *, choice=0, bound=35000, observations=()):
    """Represent unfinished native outcomes without depending on search timing."""
    solver = SimpleNamespace(
        parameters=SimpleNamespace(),
        objective_value=(choice + 1) * 10000,
        best_objective_bound=bound,
        value=lambda variable: int(variable.index == choice),
        status_name=lambda value: cp_model.CpSolverStatus(value).name,
    )
    monkeypatch.setattr(joint_search.cp_model, "CpSolver", lambda: solver)

    def run(native, problem, observer, bounds, cancellation, *args):
        if observer is not None:
            for objective, upper in observations:
                observer(objective, upper, 0.1)
        return status

    monkeypatch.setattr(joint_search, "_native_solve", run)
    return solver


def test_complete_seed_survives_cancellation_before_final_native_search(monkeypatch):
    problem, proto = alternatives()
    token = Cancellation()
    token.cancel()
    supply_bounds(monkeypatch, prepared_bounds())
    report, values = solve(problem, proto, cancellation=token)
    assert report["status"] == "FEASIBLE" and report["native_status"] == "UNKNOWN"
    assert report["objective"] == 2 and report["bound"] == 4
    assert values == [0, 1, 0]
    assert (
        sum(
            value * variable.objective_coefficient
            for value, variable in zip(values, proto.variable, strict=True)
        )
        == 20000
    )


@pytest.mark.parametrize("choice,expected", [(0, [0, 1, 0]), (2, [0, 0, 1])])
def test_best_complete_assignment_survives_an_unfinished_native_search(
    monkeypatch, choice, expected
):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.FEASIBLE, choice=choice)
    report, values = solve(problem, proto)
    assert report["status"] == "FEASIBLE" and values == expected
    assert report["objective"] == max(2, choice + 1)
    assert report["bound"] == 3.5


def test_real_native_search_improves_seed_and_proves_the_original_optimum(monkeypatch):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    report, values = solve(problem, proto)
    assert report["status"] == "OPTIMAL"
    assert report["objective"] == report["bound"] == 3
    assert values == [0, 0, 1]


@pytest.mark.parametrize("status", [cp_model.INFEASIBLE, cp_model.OPTIMAL])
def test_native_proof_contradicting_a_valid_seed_is_rejected(monkeypatch, status):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, status, choice=0, bound=10000)
    with pytest.raises(AssertionError, match="proof contradicts"):
        solve(problem, proto)


@pytest.mark.parametrize("choice,upper", [(0, 15000), (2, 25000)])
def test_upper_bound_below_retained_incumbent_is_rejected(monkeypatch, choice, upper):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(upper=upper))
    native_response(monkeypatch, cp_model.FEASIBLE, choice=choice)
    with pytest.raises(AssertionError, match="upper bound is below"):
        solve(problem, proto)


@pytest.mark.parametrize("upper", [None, 40000])
def test_unknown_without_candidate_never_uses_default_native_zero_bound(monkeypatch, upper):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(upper=upper, seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0)
    report, values = solve(problem, proto)
    assert report["status"] == "UNKNOWN" and report["objective"] is None and values is None
    assert report["bound"] == (None if upper is None else upper / 10000)


@pytest.mark.parametrize("preparation", ["none", "unbounded", "bounded"])
def test_unknown_retains_the_best_genuine_native_bound(monkeypatch, preparation):
    problem, proto = alternatives()
    bounds = (
        None
        if preparation == "none"
        else prepared_bounds(upper=40000 if preparation == "bounded" else None, seed=None)
    )
    supply_bounds(monkeypatch, bounds)
    native_response(
        monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, 35000), (None, 37500)]
    )
    report, values = solve(problem, proto)
    assert report["status"] == "UNKNOWN" and report["objective"] is None and values is None
    assert report["bound"] == 3.5


@pytest.mark.parametrize(
    "observation,expected", [(35000.1, 3.5001), (float("inf"), 4), (float(2**53), 4)]
)
def test_native_observed_bound_rounds_outward_and_rejects_unsafe_values(
    monkeypatch, observation, expected
):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, observation)])
    report, _ = solve(problem, proto)
    assert report["bound"] == expected


def test_large_negative_native_bound_is_not_corrupted_by_income_roundtrip(monkeypatch):
    problem, proto = alternatives()
    bound = -6498266171365257
    selection, certified = joint_search._selection, []

    def inspect_selection(*args):
        result = selection(*args)
        certified.append(result[2])
        return result

    monkeypatch.setattr(joint_search, "_selection", inspect_selection)
    supply_bounds(monkeypatch, prepared_bounds(upper=None, seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, bound)])
    report, values = solve(problem, proto)
    assert report["status"] == "UNKNOWN" and values is None
    assert report["bound"] == bound / 10000
    # Adjacent native integers alias when converted to display floats here;
    # inspect the certificate before that final presentation conversion.
    assert certified == [bound]


def test_invalid_native_model_is_not_relabelled_as_a_feasible_seed(monkeypatch):
    problem, proto = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.MODEL_INVALID)
    report, values = solve(problem, proto)
    assert report["status"] == "MODEL_INVALID"
    assert report["objective"] is None and values is None


def test_public_progress_combines_valid_seed_with_tightest_upper_bound_and_cut_counts(monkeypatch):
    problem, proto = alternatives()
    previous_constraints = len(problem.model.proto.constraints)

    def strengthen(problem, *args):
        problem.Add(
            sum((index + 1) * 10000 * value for index, value in enumerate(problem.variables))
            <= 40000
        )
        return prepared_bounds()

    monkeypatch.setattr(joint_search, "_strengthen", strengthen)
    native_response(monkeypatch, cp_model.FEASIBLE, observations=[(None, 50000), (10000, 35000)])
    observations, models, phases = [], [], []
    report, _ = solve(
        problem,
        proto,
        on_search=lambda *event: observations.append(event),
        on_model=models.append,
        on_phase=phases.append,
    )
    assert observations[0][:2] == (2.0, 4.0)
    assert observations[-1][:2] == (2.0, 3.5)
    assert models == [
        {
            "formulation": "linearized_income",
            "variables": 3,
            "constraints": previous_constraints + 1,
        }
    ]
    assert report["constraints"] == models[0]["constraints"]
    assert phases[-1] == "Searching the complete joint model"


def test_native_search_allowance_deducts_conversion_and_bound_preparation(monkeypatch):
    problem, proto = alternatives()
    clock = [100.0]
    monkeypatch.setattr(joint_search, "perf_counter", lambda: clock[0])

    def strengthen(*args):
        clock[0] += 6.0
        return prepared_bounds(seed=None)

    monkeypatch.setattr(joint_search, "_strengthen", strengthen)
    native = native_response(monkeypatch, cp_model.OPTIMAL, choice=2, bound=30000)
    report, _ = solve(problem, proto, seconds=30, started=90.0)
    assert native.parameters.max_time_in_seconds == 14
    assert report["timings"]["model_conversion_seconds"] == 10
    assert report["timings"]["bound_strengthening_seconds"] == 6
    assert report["seconds"] == 16


@pytest.mark.parametrize("incumbent_income", [1, 2, 3])
def test_seed_replaces_existing_hints_only_if_it_improves_income(monkeypatch, incumbent_income):
    problem, proto = alternatives()
    problem.model.add_hint(problem.variables[2], 1)
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.OPTIMAL, choice=2, bound=30000)
    solve(problem, proto, incumbent_income=incumbent_income)
    hints = problem.model.proto.solution_hint
    actual = dict(zip(hints.vars, hints.values, strict=True))
    assert actual == ({0: 0, 1: 1, 2: 0} if incumbent_income < 2 else {2: 1})


@pytest.mark.parametrize("tagged,seconds", [(False, None), (True, 4), (True, 30), (True, 44)])
def test_untagged_or_short_search_skips_preparation_and_solves_original_model(
    monkeypatch, tagged, seconds
):
    problem, proto = alternatives(tagged=tagged)
    original = proto.SerializeToString()

    def unexpected(*args, **kwargs):
        raise AssertionError("Bound preparation should be skipped")

    monkeypatch.setattr(bound_search, "strengthen", unexpected)
    report, values = solve(problem, proto, seconds=seconds)
    assert report["status"] == "OPTIMAL" and report["objective"] == report["bound"] == 3
    assert values == [0, 0, 1] and "joint_bound_search" not in report
    assert proto.SerializeToString() == original


@pytest.mark.parametrize(
    "seconds,elapsed,expected", [(None, 0, 40), (60, 10, 100 / 3), (55, 10, 30)]
)
def test_preparation_allowance_uses_only_remaining_overall_budget(
    monkeypatch, seconds, elapsed, expected
):
    problem, proto = alternatives()
    captured = []
    monkeypatch.setattr(joint_search, "perf_counter", lambda: 100.0)

    def strengthen(problem, proto, row, allowance, workers, **kwargs):
        captured.append((row, allowance, workers))
        return prepared_bounds()

    monkeypatch.setattr(bound_search, "strengthen", strengthen)
    native_response(monkeypatch, cp_model.OPTIMAL, choice=2, bound=30000)
    solve(problem, proto, seconds=seconds, started=100.0 - elapsed)
    assert captured == [(1, pytest.approx(expected), 1)]


@pytest.mark.parametrize("outcome", ["unknown", "cancel"])
def test_engine_retains_previously_validated_incumbent_after_unfinished_search(
    monkeypatch, tiny, outcome
):
    scenario = Scenario(
        "rom_rome",
        (Site("capital", major=True, slots=1), Site("town", slots=1)),
        external_food=4,
        minimum_order=-10,
    )
    previous = Economy(scenario, tiny).optimize("cp-sat", workers=1, seconds=3)
    assert previous["solver"]["status"] == "OPTIMAL"
    incumbent = deepcopy(previous)
    incumbent["solver"].update(status="FEASIBLE", bound=None)
    token = Cancellation()

    def prepare(*args):
        if outcome == "cancel":
            token.cancel()
        return None

    monkeypatch.setattr(joint_search, "_strengthen", prepare)
    if outcome == "unknown":
        monkeypatch.setattr(
            joint_search, "solve_with_progress", lambda *args, **kwargs: cp_model.UNKNOWN
        )
    economy = Economy(scenario, tiny)
    result = economy.optimize("cp-sat", workers=1, incumbent=incumbent, cancellation=token)
    assert result["solver"]["status"] == "FEASIBLE"
    assert (
        result["solver"]["objective"]
        == result["domestic_net_income"]
        == previous["domestic_net_income"]
    )
    assert result["sites"] == previous["sites"]
    assert result["party_index"] == previous["party_index"]
    assert result["selected_decision_indices"] == previous["selected_decision_indices"]
    checked = economy.evaluate(
        {name: site["buildings"] for name, site in result["sites"].items()}, result["party_index"]
    )
    assert checked["domestic_net_income"] == result["domestic_net_income"]
    assert checked["food_surplus"] >= 0
