"""Cooperative stop preserves native bounds and independently checked candidates."""

from threading import Event, current_thread
from unittest.mock import Mock

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.tw import competition
from games.tw.attila.model import ModelSnapshot
from games.tw.cancellation import Cancellation, Cancelled
from games.tw.competition import BinaryModel, Result, solve
from games.tw.enums import ProblemState
from games.tw.problem import Problem
from games.tw.region import Region
from games.tw.rome2.model import Economy as RomeEconomy
from games.tw.rome2.scenario import Scenario as RomeScenario
from games.tw.rome2.scenario import Site
from games.tw.search_progress import solve_with_progress
from games.tw.shogun2.catalog import load_data
from games.tw.shogun2.model import Economy as ShogunEconomy
from games.tw.shogun2.scenario import Province
from games.tw.shogun2.scenario import Scenario as ShogunScenario
from games.tw.solver_ortools import SolverOrTools
from tests.support.attila import building, province
from tests.support.rome2 import tiny_catalog
from twoptimizer.attila_session import AttilaSession, PreparedAttila, signature
from twoptimizer.models import RunConfig


def binary_model():
    return BinaryModel(
        ("a", "b"),
        np.array([0.25, 0.375]),
        np.array([[1.0, 1.0]]),
        np.array([0.0]),
        np.array([1.0]),
        offset=-7.125,
    )


def test_external_request_latches_and_does_not_poll_again():
    checker = Mock(side_effect=[False, True])
    cancellation = Cancellation(checker)
    assert not cancellation.requested
    assert cancellation.requested
    assert cancellation.requested
    assert checker.call_count == 2
    with pytest.raises(Cancelled):
        cancellation.checkpoint()


def test_precancelled_context_never_starts_native_work():
    cancellation = Cancellation()
    cancellation.cancel()
    stop = Mock()
    with pytest.raises(Cancelled), cancellation.interrupt(stop):
        pytest.fail("A cancelled token must not enter native search")
    stop.assert_not_called()


def test_stop_is_repeated_until_native_search_is_ready_and_watcher_is_joined():
    cancellation = Cancellation()
    first_request, native_ready, stopped = Event(), Event(), Event()
    watchers = []

    def stop():
        watchers.append(current_thread())
        first_request.set()
        if native_ready.is_set():
            stopped.set()

    with cancellation.interrupt(stop):
        cancellation.cancel()
        assert first_request.wait(2)
        assert not stopped.is_set()
        native_ready.set()
        assert stopped.wait(2)
    assert len(watchers) >= 2
    assert all(not watcher.is_alive() for watcher in watchers)


def test_checker_error_stops_native_work_and_then_propagates():
    check_now, stopped = Event(), Event()

    def checker():
        if check_now.is_set():
            raise OSError("Cannot check cancellation marker")
        return False

    cancellation = Cancellation(checker)
    with (
        pytest.raises(OSError, match="Cannot check cancellation marker"),
        cancellation.interrupt(stopped.set),
    ):
        check_now.set()
        assert stopped.wait(2)
    assert cancellation.requested


@pytest.mark.parametrize("body_fails", [False, True])
def test_watcher_failure_retries_stop_but_original_native_exception_wins(body_fails):
    cancellation, stopped = Cancellation(), Event()
    attempts = []

    def stop():
        attempts.append(current_thread())
        if len(attempts) == 1:
            raise RuntimeError("Native interrupt failed")
        stopped.set()

    error = LookupError if body_fails else RuntimeError
    message = "Native search failed" if body_fails else "Native interrupt failed"
    with pytest.raises(error, match=message), cancellation.interrupt(stop):
        cancellation.cancel()
        assert stopped.wait(2)
        if body_fails:
            raise LookupError("Native search failed")
    assert all(not watcher.is_alive() for watcher in attempts)


def test_actual_cpsat_stop_keeps_suboptimal_feasible_candidate_and_upper_bound(monkeypatch):
    model = cp_model.CpModel()
    variables = [model.new_bool_var(f"x{i}") for i in range(20)]
    model.add(sum(variables) <= 10)
    model.maximize(sum((i + 1) * variable for i, variable in enumerate(variables)))
    model.add_decision_strategy(variables, cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.cp_model_presolve = False
    solver.parameters.linearization_level = 0
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    solver.parameters.max_time_in_seconds = 5  # Bound test failures, not production solving.
    cancellation, stopped = Cancellation(), Event()
    native_stop = solver.stop_search
    previous = Mock()
    solver.best_bound_callback = previous
    observations = []

    def stop():
        native_stop()
        stopped.set()

    def observe(objective, bound, elapsed):
        observations.append((objective, bound))
        if objective is not None and not cancellation.requested:
            cancellation.cancel()
            assert stopped.wait(2)

    monkeypatch.setattr(solver, "stop_search", stop)
    status = solve_with_progress(
        solver,
        model,
        on_search=observe,
        scale=0.25,
        offset=-7.125,
        cancellation=cancellation,
    )
    assert status == cp_model.FEASIBLE
    values = [solver.value(variable) for variable in variables]
    assert all(value in (0, 1) for value in values) and sum(values) <= 10
    actual_income = sum((i + 1) * value for i, value in enumerate(values)) * 0.25 - 7.125
    optimum = sum(range(11, 21)) * 0.25 - 7.125
    objective, bound = observations[-1]
    assert objective == actual_income < optimum <= bound
    assert solver.best_bound_callback is previous
    previous.assert_called()


def test_precancelled_solver_has_no_response_or_fake_bound():
    solver, model = cp_model.CpSolver(), cp_model.CpModel()
    cancellation = Cancellation()
    cancellation.cancel()
    observations = []
    with pytest.raises(Cancelled):
        solve_with_progress(
            solver,
            model,
            on_search=lambda *row: observations.append(row),
            cancellation=cancellation,
        )
    assert observations == []
    with pytest.raises(RuntimeError, match=r"solve.*has not been called"):
        _ = solver.response_proto


def test_native_stop_before_any_candidate_returns_unknown_without_invented_solution(monkeypatch):
    cancellation, stopped = Cancellation(), Event()
    solver = cp_model.CpSolver()
    solver.parameters.cp_model_presolve = False
    solver.parameters.max_time_in_seconds = 5
    native_stop = solver.stop_search

    def stop():
        native_stop()
        stopped.set()

    def before_candidate(bound):
        cancellation.cancel()
        assert stopped.wait(2)

    solver.best_bound_callback = before_candidate
    monkeypatch.setattr(solver, "stop_search", stop)
    monkeypatch.setattr(competition.cp_model, "CpSolver", lambda: solver)
    result = solve(binary_model(), "cp-sat", workers=1, cancellation=cancellation)
    assert cancellation.requested
    assert result.status == "UNKNOWN"
    assert result.values is result.objective is result.bound is None
    assert solver.best_bound_callback is before_candidate


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_cancelled_comparison_token_cannot_start_another_solver(algorithm):
    cancellation = Cancellation()
    cancellation.cancel()
    with pytest.raises(Cancelled):
        solve(binary_model(), algorithm, workers=1, cancellation=cancellation)


def test_cancellation_during_independent_validation_keeps_native_optimum(monkeypatch):
    model, cancellation = binary_model(), Cancellation()
    feasible = model.feasible

    def validate(values):
        cancellation.cancel()
        return feasible(values)

    monkeypatch.setattr(model, "feasible", validate)
    result = solve(model, "cp-sat", workers=1, cancellation=cancellation)
    assert cancellation.requested
    assert result.status == "OPTIMAL"
    assert result.values == [0, 1]
    assert result.objective == result.bound == -6.75


def test_cancelled_native_candidate_still_must_pass_independent_validation(monkeypatch):
    cancellation = Cancellation()

    def invalid_candidate(*args, **kwargs):
        cancellation.cancel()
        return Result("cp-sat", "FEASIBLE", values=[1, 1], bound=100)

    monkeypatch.setattr(competition, "sat_solve", invalid_candidate)
    result = solve(binary_model(), "cp-sat", workers=1, cancellation=cancellation)
    assert result.status == "INVALID_SOLUTION"
    assert result.values is result.objective is result.bound is None


def test_cancelled_attila_incumbent_is_not_reused_as_a_completed_proof(monkeypatch):
    model = BinaryModel(
        tuple(f"x{i}" for i in range(20)),
        np.arange(1, 21, dtype=float),
        np.ones((1, 20)),
        np.array([0.0]),
        np.array([10.0]),
    )
    prepared = PreparedAttila(ModelSnapshot(model, 0, None), ("p",), ("Province",))
    state = AttilaSession(reuse_proofs=True)
    config = RunConfig(game="attila", workers=1)
    cancellation, stopped = Cancellation(), Event()
    original_factory = cp_model.CpSolver
    solver = original_factory()
    solver.parameters.cp_model_presolve = False
    solver.parameters.linearization_level = 0
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    solver.parameters.max_time_in_seconds = 5
    native_stop = solver.stop_search
    calls = []

    def factory():
        calls.append(True)
        return solver if len(calls) == 1 else original_factory()

    def stop():
        native_stop()
        stopped.set()

    def observe(objective, bound, elapsed):
        if objective is not None and not cancellation.requested:
            cancellation.cancel()
            assert stopped.wait(2)

    monkeypatch.setattr(solver, "stop_search", stop)
    monkeypatch.setattr(competition.cp_model, "CpSolver", factory)
    partial, key, reused = state.solve(
        config, prepared, cancellation=cancellation, on_search=observe
    )
    assert cancellation.requested and not reused
    assert partial.status == "FEASIBLE"
    assert model.feasible(partial.values)
    assert partial.objective is not None and partial.bound is not None
    assert partial.objective < 155 <= partial.bound
    assert key not in state.proofs

    optimum, _, reused = state.solve(config, prepared, cancellation=Cancellation())
    assert not reused and calls == [True, True]
    assert optimum.status == "OPTIMAL"
    assert optimum.objective == optimum.bound == 155
    replay, _, reused = state.solve(config, prepared, cancellation=Cancellation())
    assert reused and calls == [True, True]
    assert replay.objective == optimum.objective
    assert model.feasible(replay.values)


@pytest.mark.parametrize("status", ["FEASIBLE", "UNKNOWN", "INFEASIBLE"])
def test_attila_drops_preexisting_nonoptimal_cache_entries(status):
    model = binary_model()
    prepared = PreparedAttila(ModelSnapshot(model, 0, None), ("p",), ("Province",))
    key = signature(model)
    state = AttilaSession(reuse_proofs=True, proofs={key: Result("cp-sat", status)})
    result, _, reused = state.solve(RunConfig(game="attila", workers=1), prepared)
    assert not reused
    assert result.status == state.proofs[key].status == "OPTIMAL"
    assert result.objective == result.bound == -6.75


def test_rome_cancellation_at_compilation_boundary_skips_native_search():
    cancellation = Cancellation()
    economy = RomeEconomy(
        RomeScenario("rom_rome", (Site("a", major=True, slots=0),)), tiny_catalog()
    )
    with pytest.raises(Cancelled):
        economy.optimize(
            workers=1,
            cancellation=cancellation,
            on_model=lambda _: cancellation.cancel(),
        )


def test_shogun_cancellation_at_compilation_boundary_skips_native_search():
    cancellation = Cancellation()
    economy = ShogunEconomy(ShogunScenario("oda", (Province("jap_sado"),)), *load_data())
    with pytest.raises(Cancelled):
        economy.optimize(
            workers=1,
            cancellation=cancellation,
            on_model=lambda _: cancellation.cancel(),
        )


def test_attila_compact_cancellation_is_not_treated_as_a_formulation_fallback(context):
    region = Region("r", context=context)
    problem = Problem(
        objective="income", scenario={"regions": {"r": {"minimum_sanitation": 0}}}, context=context
    )
    assert isinstance(problem.problem, SolverOrTools)
    problem.add_province(province("p", region))
    candidates = [
        building(region, "factory", ("economy_gdp_industry", "building_to_building_own", 100)),
        building(region, "bonus", ("economy_gdp_mod_industry", "faction_to_region_own", 25)),
        building(region, "tax", ("province_tax_rate", "province_to_province_own", 20)),
    ]
    for candidate in candidates:
        candidate.lp_variable = problem.problem.solver.BoolVar(candidate.get_name())
    problem.state = ProblemState.CONSTRAINTS_ADDED
    problem.add_objective()
    cancellation, models = Cancellation(), []

    def compiled(stats):
        models.append(stats)
        cancellation.cancel()

    with pytest.raises(Cancelled):
        solve(
            problem.problem.binary_model(),
            "cp-sat",
            workers=1,
            cancellation=cancellation,
            on_model=compiled,
        )
    assert len(models) == 1
    assert models[0]["formulation"] == "factored_income"
