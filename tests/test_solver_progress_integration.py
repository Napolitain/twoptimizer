"""Engine observations and application events preserve original income units."""

import numpy as np
import pytest

from games.tw.competition import BinaryModel, solve
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import tiny_catalog
from twoptimizer import progress as progress_module
from twoptimizer.adapters.search import search_observers
from twoptimizer.progress import ModelStats, PhaseTimer, SearchStats


@pytest.mark.parametrize("offset", [7.125, -7.125])
def test_binary_progress_restores_fractional_coefficients_and_objective_offset(offset):
    model = BinaryModel(
        ("a", "b"),
        np.array([0.25, 0.375]),
        np.array([[1.0, 1.0]]),
        np.array([0.0]),
        np.array([1.0]),
        offset=offset,
    )
    observations, models = [], []
    result = solve(
        model,
        "cp-sat",
        workers=1,
        on_search=lambda *row: observations.append(row),
        on_model=models.append,
    )
    expected = offset + 0.375
    assert result.status == "OPTIMAL"
    assert result.objective == result.bound == pytest.approx(expected)
    assert models == [result.model_stats]
    assert models[0]["formulation"] == "expanded_boolean"
    assert observations[-1][:2] == pytest.approx((expected, expected))
    feasible_incomes = (offset, offset + 0.25, expected)
    for objective, bound, _ in observations:
        if objective is not None:
            assert any(objective == pytest.approx(income) for income in feasible_incomes)
        if bound is not None:
            assert bound >= expected - 1e-9


def test_rome_native_progress_reaches_adapter_in_income_units_without_double_throttling(
    monkeypatch,
):
    # Even an entire solve inside one application throttle interval must deliver
    # the first actual candidate and final solver observation separately.
    monkeypatch.setattr(progress_module, "perf_counter", lambda: 0.0)
    economy = Economy(
        Scenario(
            "rom_rome",
            (Site("a", major=True, slots=0),),
            party=0,
            tax_points=7,
            corruption_points=3,
        ),
        tiny_catalog(),
    )
    events = []
    phase = PhaseTimer(events.append)
    report = economy.optimize(
        "cp-sat",
        workers=1,
        **search_observers(phase, "Rome: CP-SAT", lambda: len(economy.decisions)),
    )
    # 100 base wealth, +10% wealth, and +14% net tax: native units are 1/10000 income.
    expected = 125.4
    assert report["solver"]["status"] == "OPTIMAL"
    assert report["domestic_net_income"] == pytest.approx(expected)
    assert isinstance(events[0], ModelStats)
    assert events[0].formulation == "linearized_income"
    observations = [event for event in events if isinstance(event, SearchStats)]
    candidates = [event for event in observations if event.objective is not None]
    assert len(candidates) >= 2
    assert candidates[0].objective == pytest.approx(expected)
    assert observations[-1].objective == observations[-1].bound == pytest.approx(expected)
    assert all(event.label == "Rome: CP-SAT" for event in observations)
    assert all(event.unit == "income/turn" for event in observations)
    assert phase.models[0].variables == report["solver"]["variables"]
    assert phase.models[0].constraints == report["solver"]["constraints"]


def test_search_adapter_without_progress_adds_no_observers_or_decision_count_work():
    def unexpected_count():
        raise AssertionError("Decision counting should stay lazy without progress")

    assert search_observers(PhaseTimer(), "CP-SAT", unexpected_count) == {}


def test_search_adapter_preserves_bound_only_and_final_events_inside_one_interval(monkeypatch):
    monkeypatch.setattr(progress_module, "perf_counter", lambda: 0.0)
    events = []
    observers = search_observers(PhaseTimer(events.append), "CP-SAT", lambda: 2)
    observers["on_search"](None, 100, 0)
    observers["on_search"](80, 80, 0.1)
    assert events == [SearchStats("CP-SAT", None, 100, 0), SearchStats("CP-SAT", 80, 80, 0.1)]
