"""CP-SAT progress preserves objective units, status and callback ownership."""

import math
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from ortools.sat.python import cp_model

from games.tw import search_progress
from games.tw.search_progress import solve_with_progress


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    result = Clock()
    monkeypatch.setattr(search_progress, "monotonic", result)
    return result


def solver_stub(*, status=cp_model.OPTIMAL, objective=12.0, bound=12.0, run=None, previous=None):
    solver = SimpleNamespace(
        best_bound_callback=previous, objective_value=objective, best_objective_bound=bound
    )

    def solve(model, callback=None):
        if run is not None:
            run(solver, callback)
        return status

    solver.solve = Mock(side_effect=solve)
    return solver


def solve_stub(solver, observer=None, **kwargs):
    return solve_with_progress(
        cast(cp_model.CpSolver, solver),
        cast(cp_model.CpModel, object()),
        on_search=observer,
        **kwargs,
    )


def test_without_observer_calls_plain_solve_without_callback_or_attribute_changes():
    previous = Mock()
    solver = solver_stub(status=cp_model.FEASIBLE, previous=previous)
    assert solve_stub(solver) == cp_model.FEASIBLE
    assert len(solver.solve.call_args.args) == 1
    assert solver.solve.call_args.kwargs == {}
    assert solver.best_bound_callback is previous
    previous.assert_not_called()


@pytest.mark.parametrize("scale", [0, -1, math.inf, -math.inf, math.nan, True, "1"])
def test_invalid_scale_is_rejected_before_touching_solver(scale):
    solver = solver_stub()
    with pytest.raises(ValueError, match="scale"):
        solve_stub(solver, Mock(), scale=scale)
    solver.solve.assert_not_called()
    assert solver.best_bound_callback is None


@pytest.mark.parametrize("offset", [math.inf, -math.inf, math.nan, True, "1"])
def test_invalid_offset_is_rejected_before_touching_solver(offset):
    solver = solver_stub()
    with pytest.raises(ValueError, match="offset"):
        solve_stub(solver, Mock(), offset=offset)
    solver.solve.assert_not_called()


def test_bound_arrives_before_any_incumbent_and_old_callback_receives_raw_units(clock):
    old_bounds, reports = [], []

    def run(solver, callback):
        assert isinstance(callback, cp_model.CpSolverSolutionCallback)
        solver.best_bound_callback(100)
        clock.now += 0.1
        solver.best_bound_callback(90)

    solver = solver_stub(
        status=cp_model.FEASIBLE, objective=40, bound=90, run=run, previous=old_bounds.append
    )
    previous = solver.best_bound_callback
    assert (
        solve_stub(solver, lambda *row: reports.append(row), scale=0.01, offset=7)
        == cp_model.FEASIBLE
    )
    assert old_bounds == [100, 90]
    assert reports == [(None, 8, 0), (0.4 + 7, 0.9 + 7, pytest.approx(0.1))]
    assert solver.best_bound_callback is previous


def test_solution_observer_forwards_its_live_values_not_the_solver_response(clock, monkeypatch):
    reports = []
    monkeypatch.setattr(search_progress._SolutionObserver, "objective_value", property(lambda _: 3))
    monkeypatch.setattr(
        search_progress._SolutionObserver, "best_objective_bound", property(lambda _: 5)
    )

    def run(solver, callback):
        callback.on_solution_callback()

    solver = solver_stub(objective=4, bound=4, run=run)
    solve_stub(solver, lambda *row: reports.append(row), scale=2, offset=-1)
    assert reports == [(5, 9, 0), (7, 7, 0)]


def test_throttle_keeps_latest_incumbent_and_bound_and_forces_final(clock):
    reports = []
    progress = search_progress._Progress(lambda *row: reports.append(row), 1, 0)
    progress.best_bound(100)
    clock.now += 0.1
    progress.solution(20, 90)
    clock.now += 0.2
    progress.best_bound(80)
    clock.now = 100.9
    progress.best_bound(70)
    clock.now = 100.95
    progress.solution(30, 60)
    progress.final(cast(cp_model.CpSolver, solver_stub(objective=40, bound=50)), cp_model.FEASIBLE)
    assert reports == [
        (None, 100, 0),
        (20, 90, pytest.approx(0.1)),
        (20, 70, pytest.approx(0.9)),
        (40, 50, pytest.approx(0.95)),
    ]


def test_clock_regression_cannot_make_elapsed_time_decrease(clock):
    reports = []
    progress = search_progress._Progress(lambda *row: reports.append(row), 1, 0)
    clock.now = 101
    progress.solution(1, 2)
    clock.now = 99
    progress.final(cast(cp_model.CpSolver, solver_stub(objective=2, bound=2)), cp_model.OPTIMAL)
    assert [row[2] for row in reports] == [1, 1]


def test_unknown_does_not_publish_default_response_zero_as_an_incumbent_or_bound(clock):
    reports = []
    solver = solver_stub(status=cp_model.UNKNOWN, objective=0, bound=0)
    solve_stub(solver, lambda *row: reports.append(row))
    assert reports == [(None, None, 0)]


def test_unknown_keeps_only_a_bound_certified_by_the_bound_callback(clock):
    reports = []

    def run(solver, callback):
        solver.best_bound_callback(9)

    solver = solver_stub(status=cp_model.UNKNOWN, objective=0, bound=0, run=run)
    solve_stub(solver, lambda *row: reports.append(row), scale=3, offset=-4)
    assert reports == [(None, 23, 0), (None, 23, 0)]


@pytest.mark.parametrize("status", [cp_model.INFEASIBLE, cp_model.MODEL_INVALID])
def test_non_solution_status_never_reads_stale_objective_fields(clock, status):
    class NoResponse:
        best_bound_callback = None

        def solve(self, model, callback=None):
            return status

        @property
        def objective_value(self):
            raise AssertionError("No incumbent exists")

        @property
        def best_objective_bound(self):
            raise AssertionError("No certified response bound exists")

    reports = []
    assert solve_stub(NoResponse(), lambda *row: reports.append(row)) == status
    assert reports == [(None, None, 0)]


@pytest.mark.parametrize("value", [math.inf, -math.inf, math.nan])
def test_nonfinite_solver_values_never_reach_progress_observer(clock, value):
    reports = []

    def run(solver, callback):
        solver.best_bound_callback(value)

    solver = solver_stub(objective=value, bound=value, run=run)
    solve_stub(solver, lambda *row: reports.append(row))
    assert reports == [(None, None, 0), (None, None, 0)]


def test_conversion_overflow_is_reported_as_unknown_not_infinity(clock):
    reports = []
    solve_stub(
        solver_stub(objective=1e308, bound=1e308), lambda *row: reports.append(row), scale=10
    )
    assert reports == [(None, None, 0)]


def test_existing_bound_callback_failure_is_preserved_and_callback_restored(clock):
    failure = RuntimeError("existing callback failed")
    previous = Mock(side_effect=failure)
    observer = Mock()

    def run(solver, callback):
        solver.best_bound_callback(12)

    solver = solver_stub(run=run, previous=previous)
    with pytest.raises(RuntimeError) as raised:
        solve_stub(solver, observer)
    assert raised.value is failure
    assert solver.best_bound_callback is previous
    observer.assert_not_called()


def test_solve_failure_is_not_masked_by_final_progress_or_stale_response(clock):
    failure = RuntimeError("native solve failed")
    previous, observer = Mock(), Mock()
    solver = solver_stub(previous=previous)
    solver.solve.side_effect = failure
    with pytest.raises(RuntimeError) as raised:
        solve_stub(solver, observer)
    assert raised.value is failure
    assert solver.best_bound_callback is previous
    observer.assert_not_called()


@pytest.mark.parametrize("during_search", [True, False])
def test_observer_exception_propagates_and_restores_existing_callback(clock, during_search):
    failure = ValueError("observer failed")
    previous = Mock()

    def run(solver, callback):
        if during_search:
            solver.best_bound_callback(12)

    solver = solver_stub(previous=previous, run=run)
    observer = Mock(side_effect=failure)
    with pytest.raises(ValueError) as raised:
        solve_stub(solver, observer)
    assert raised.value is failure
    assert solver.best_bound_callback is previous
    assert observer.call_count == 1


def test_concurrent_bound_events_have_one_initial_report_and_no_overlapping_delivery(clock):
    reports = []
    barrier = Barrier(8)
    progress = search_progress._Progress(lambda *row: reports.append(row), 1, 0)

    def update(value):
        barrier.wait()
        progress.best_bound(value)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(update, range(8)))
    assert len(reports) == 1
    assert reports[0][0] is None and reports[0][1] in range(8)
    progress.final(cast(cp_model.CpSolver, solver_stub(objective=1, bound=1)), cp_model.OPTIMAL)
    assert reports[-1] == (1, 1, 0)


@pytest.mark.parametrize("maximize", [True, False])
def test_native_solution_and_final_bounds_use_original_units_without_model_changes(maximize):
    model = cp_model.CpModel()
    value = model.new_int_var(-3, 7, "value")
    if maximize:
        model.maximize(4 * value + 2)
    else:
        model.minimize(4 * value + 2)
    original = str(model.proto)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    reports, old_bounds = [], []
    solver.best_bound_callback = old_bounds.append
    previous = solver.best_bound_callback
    status = solve_with_progress(
        solver, model, on_search=lambda *row: reports.append(row), scale=0.5, offset=9
    )
    expected = (30 if maximize else -10) * 0.5 + 9
    assert status == cp_model.OPTIMAL
    assert reports[-1][:2] == (expected, expected)
    assert str(model.proto) == original
    assert solver.parameters.num_search_workers == 1
    assert solver.best_bound_callback is previous
    assert old_bounds
    assert all(row[2] >= 0 for row in reports)
    assert [row[2] for row in reports] == sorted(row[2] for row in reports)


def test_native_zero_time_limit_reports_unknown_without_fabricated_zero_bound():
    model = cp_model.CpModel()
    value = model.new_int_var(0, 100, "value")
    model.maximize(value)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 0
    reports = []
    status = solve_with_progress(solver, model, on_search=lambda *row: reports.append(row))
    assert status == cp_model.UNKNOWN
    assert reports[-1][:2] == (None, None)


def test_native_callback_exception_is_rethrown_and_existing_callback_restored():
    model = cp_model.CpModel()
    value = model.new_int_var(0, 10, "value")
    model.maximize(value)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    previous = Mock()
    solver.best_bound_callback = previous
    failure = RuntimeError("delivery failed")
    with pytest.raises(RuntimeError) as raised:
        solve_with_progress(solver, model, on_search=Mock(side_effect=failure))
    assert raised.value is failure
    assert solver.best_bound_callback is previous
