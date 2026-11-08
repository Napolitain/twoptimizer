"""LP resource prices are optional heuristics, never integer bound certificates."""

import math
from types import SimpleNamespace

import pytest
from ortools.linear_solver import linear_solver_pb2
from ortools.math_opt.python import mathopt

from games.tw import highs_backend
from games.tw.cancellation import Cancellation, Cancelled


def resource_model():
    proto = linear_solver_pb2.MPModelProto(maximize=True, objective_offset=7)
    for name, profit in (("factory", 10.25), ("market", 3.6)):
        proto.variable.add(
            name=name, lower_bound=0, upper_bound=1, is_integer=True, objective_coefficient=profit
        )
    # Two resources per factory, one per market, with 2.5 available. The LP
    # chooses one factory and half a market: the next resource unit costs 3.6.
    proto.constraint.add(
        name="food", var_index=[0, 1], coefficient=[-2, -1], lower_bound=-2.5, upper_bound=math.inf
    )
    return proto


def no_solution(reason=mathopt.TerminationReason.NO_SOLUTION_FOUND):
    return SimpleNamespace(
        termination=SimpleNamespace(reason=reason, detail="Synthetic native termination"),
        has_primal_feasible_solution=lambda: False,
    )


def unexpected_search(*args, **kwargs):
    pytest.fail("Price estimation must not start native search")


def test_native_relaxation_returns_rounded_opportunity_cost_and_preserves_input():
    proto = resource_model()
    original = proto.SerializeToString()
    result = highs_backend.estimate_lower_bound_price(proto, 0, 5, 1)
    assert result["status"] == "OPTIMAL"
    assert result["price"] == 4
    assert proto.SerializeToString() == original
    assert "bound" not in result and "objective" not in result
    assert result["seconds"] >= result["timings"]["search_seconds"] >= 0


def test_native_nonbinding_resource_has_zero_price():
    proto = resource_model()
    proto.constraint[0].lower_bound = -4
    result = highs_backend.estimate_lower_bound_price(proto, 0, 5, 1)
    assert result["status"] == "OPTIMAL" and result["price"] == 0


def test_native_infeasible_relaxation_cannot_provide_price():
    proto = resource_model()
    proto.constraint[0].lower_bound = 1
    result = highs_backend.estimate_lower_bound_price(proto, 0, 5, 1)
    assert result["status"] == "INFEASIBLE" and result["price"] is None


@pytest.mark.parametrize("seconds", [0, -1, math.inf, math.nan, None, True, "10"])
def test_invalid_price_allowance_is_rejected(seconds):
    with pytest.raises(ValueError, match="seconds"):
        highs_backend.estimate_lower_bound_price(resource_model(), 0, seconds, 1)


@pytest.mark.parametrize("row_index", [-1, 1, 0.0, True])
def test_invalid_resource_row_index_is_rejected(row_index):
    with pytest.raises(ValueError, match="row index"):
        highs_backend.estimate_lower_bound_price(resource_model(), row_index, 1, 1)


@pytest.mark.parametrize("lower,upper", [(-math.inf, math.inf), (-2, 0), (math.nan, math.inf)])
def test_row_requires_finite_lower_bound_and_unbounded_upper(lower, upper):
    proto = resource_model()
    proto.constraint[0].lower_bound, proto.constraint[0].upper_bound = lower, upper
    with pytest.raises(ValueError, match="finite lower bound"):
        highs_backend.estimate_lower_bound_price(proto, 0, 1, 1)


def test_minimization_cannot_use_maximization_price_convention():
    proto = resource_model()
    proto.maximize = False
    with pytest.raises(ValueError, match="maximization"):
        highs_backend.estimate_lower_bound_price(proto, 0, 1, 1)


@pytest.mark.parametrize("dual,feasible", [(math.nan, True), (math.inf, True), (-3.6, False)])
def test_optimal_lp_requires_finite_feasible_dual(monkeypatch, dual, feasible):
    result = no_solution(mathopt.TerminationReason.OPTIMAL)
    result.has_dual_feasible_solution = lambda: feasible
    result.dual_values = lambda row: dual
    monkeypatch.setattr(highs_backend.mathopt, "solve", lambda *args, **kwargs: result)
    report = highs_backend.estimate_lower_bound_price(resource_model(), 0, 1, 1)
    assert report["price"] is None


def test_nonoptimal_native_result_is_not_used_for_price(monkeypatch):
    monkeypatch.setattr(highs_backend.mathopt, "solve", lambda *args, **kwargs: no_solution())
    report = highs_backend.estimate_lower_bound_price(resource_model(), 0, 1, 1)
    assert report["status"] == "UNKNOWN" and report["price"] is None


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class Scheduler:
    def __init__(self, clock, *, acquire=True):
        self.clock = clock
        self.acquired = acquire
        self.released = False
        self.timeout = None

    def acquire(self, *, timeout):
        self.timeout = timeout
        self.clock.now += 2 if self.acquired else timeout
        return self.acquired

    def release(self):
        self.released = True


@pytest.fixture
def timed_preparation(monkeypatch):
    clock = Clock()
    convert = highs_backend._native_model

    def convert_with_elapsed_time(proto):
        model = convert(proto)
        clock.now += 3
        return model

    monkeypatch.setattr(highs_backend, "perf_counter", clock)
    monkeypatch.setattr(highs_backend, "_native_model", convert_with_elapsed_time)
    monkeypatch.setattr(
        highs_backend,
        "_native_library",
        lambda: SimpleNamespace(Highs_resetGlobalScheduler=lambda _: None),
    )
    return clock


def test_native_allowance_includes_conversion_waiting_and_ten_second_cap(
    monkeypatch, timed_preparation
):
    clock = timed_preparation
    scheduler = Scheduler(clock)
    monkeypatch.setattr(highs_backend, "_SCHEDULER", scheduler)
    allowances = []

    def search(model, solver, *, params):
        allowances.append(params.time_limit.total_seconds())
        clock.now += 1
        return no_solution()

    monkeypatch.setattr(highs_backend.mathopt, "solve", search)
    report = highs_backend.estimate_lower_bound_price(resource_model(), 0, 100, 1)
    assert allowances == [5]
    assert scheduler.timeout == 7 and scheduler.released
    assert report["seconds"] == 6
    assert report["timings"] == {
        "model_conversion_seconds": 3,
        "scheduler_wait_seconds": 2,
        "search_seconds": 1,
    }


@pytest.mark.parametrize("seconds,acquire", [(2, True), (4, False), (4, True)])
def test_exhausted_preparation_allowance_never_starts_search(
    monkeypatch, timed_preparation, seconds, acquire
):
    scheduler = Scheduler(timed_preparation, acquire=acquire)
    monkeypatch.setattr(highs_backend, "_SCHEDULER", scheduler)
    monkeypatch.setattr(highs_backend.mathopt, "solve", unexpected_search)
    report = highs_backend.estimate_lower_bound_price(resource_model(), 0, seconds, 1)
    assert report["status"] == "UNKNOWN" and report["price"] is None
    assert report["timings"]["search_seconds"] == 0
    assert scheduler.released == (seconds > 3 and acquire)


@pytest.mark.parametrize("phase", ["before", "conversion", "search"])
def test_price_prepass_cancellation_skips_following_work(monkeypatch, phase):
    cancellation = Cancellation()
    convert = highs_backend._native_model

    def conversion(proto):
        model = convert(proto)
        if phase == "conversion":
            cancellation.cancel()
        return model

    def search(*args, **kwargs):
        assert phase == "search"
        cancellation.cancel()
        return no_solution()

    if phase == "before":
        cancellation.cancel()
    monkeypatch.setattr(highs_backend, "_native_model", conversion)
    monkeypatch.setattr(highs_backend.mathopt, "solve", search)
    with pytest.raises(Cancelled):
        highs_backend.estimate_lower_bound_price(
            resource_model(), 0, 1, 1, cancellation=cancellation
        )
    assert highs_backend._SCHEDULER.acquire(blocking=False)
    highs_backend._SCHEDULER.release()


def test_native_failure_preserves_error_and_releases_scheduler(monkeypatch):
    failure = RuntimeError("native failure")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(highs_backend.mathopt, "solve", fail)
    with pytest.raises(RuntimeError) as error:
        highs_backend.estimate_lower_bound_price(resource_model(), 0, 1, 1)
    assert error.value is failure
    assert highs_backend._SCHEDULER.acquire(blocking=False)
    highs_backend._SCHEDULER.release()
