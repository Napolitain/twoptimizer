"""Observed milestones survive bounded traces without becoming layout certificates."""

import json

import pytest

from tests.support.ui import result
from twoptimizer import progress, service
from twoptimizer.adapters.search import search_observers
from twoptimizer.models import EngineResult
from twoptimizer.presentation import bound_preparation_summary, search_measurement_summary
from twoptimizer.progress import PhaseTimer, SearchStats
from twoptimizer.requests import default_config
from twoptimizer.runtime_view import RuntimeView
from twoptimizer.search_measurements import SearchMeasurements


def test_milestones_include_preparation_and_keep_native_clocks_separate():
    measurements = SearchMeasurements()
    measurements.observe(SearchStats("CP-SAT", None, 100, 0), 12)
    measurements.observe(SearchStats("CP-SAT", 90, 100, 2), 14)
    measurements.observe(SearchStats("CP-SAT", 98, 100, 0), 20)
    measurements.observe(SearchStats("CP-SAT", 99, 100, 1), 21)
    report = measurements.to_dict()
    stream = report["streams"][0]
    assert stream["first_candidate_seconds"] == 14
    assert stream["gap_reached_seconds"] == {"10": 14, "5": 20, "2": 20, "1": 21}
    assert report["samples"][2]["elapsed_seconds"] == 0
    assert report["samples"][2]["case_elapsed_seconds"] == 20
    assert report["final"] is None
    assert "precede independent" in report["validation"]
    json.dumps(report, allow_nan=False)


def test_thinning_preserves_first_latest_and_milestones_with_bounded_memory():
    measurements = SearchMeasurements(max_samples=8)
    for index in range(101):
        measurements.observe(SearchStats("Search", index, 100, index), index + 10)
    report = measurements.to_dict()
    assert len(report["samples"]) <= 8
    assert report["samples"][0]["objective"] == 0
    assert report["samples"][-1]["objective"] == 100
    assert report["observations"] == 101
    assert report["dropped_samples"] == 101 - len(report["samples"])
    assert report["streams"][0]["gap_reached_seconds"] == {"10": 100, "5": 105, "2": 108, "1": 109}
    report["samples"].clear()
    report["streams"][0]["gap_reached_seconds"].clear()
    assert measurements.to_dict()["samples"]
    assert measurements.to_dict()["streams"][0]["gap_reached_seconds"]


def test_different_objectives_remain_separate_and_stream_growth_is_bounded():
    measurements = SearchMeasurements(max_streams=2)
    measurements.observe(SearchStats("One", 99, 100, 1), 1)
    measurements.observe(SearchStats("Cost", 105, 100, 1, sense="minimize", unit="points"), 2)
    measurements.observe(SearchStats("Other", 100, 100, 0), 3)
    report = measurements.to_dict()
    assert len(report["streams"]) == 2
    assert report["streams"][1]["gap_reached_seconds"] == {"10": 2, "5": 2}
    assert report["untracked_observations"] == 1
    assert report["streams"][1]["unit"] == "points"


def test_missing_or_inconsistent_bounds_never_record_an_exact_gap():
    measurements = SearchMeasurements()
    for elapsed, (income, bound) in enumerate(((None, 100), (90, None), (110, 100))):
        measurements.observe(SearchStats("Search", income, bound, elapsed), elapsed)
    assert measurements.to_dict()["streams"][0]["gap_reached_seconds"] == {}


@pytest.mark.parametrize("kwargs", [{"max_samples": 3}, {"max_streams": 0}])
def test_invalid_collection_limits_are_rejected(kwargs):
    with pytest.raises(ValueError, match="four samples"):
        SearchMeasurements(**kwargs)


def test_collection_survives_ipc_throttling_and_absent_progress_listener(monkeypatch):
    clock, events = [0.0], []
    monkeypatch.setattr(progress, "perf_counter", lambda: clock[0])
    phase = PhaseTimer(events.append, collect_search=True)
    phase.record_search(SearchStats("Search", None, 100, 0))
    clock[0] = 0.1
    phase.record_search(SearchStats("Search", 98, 100, 0.1))
    assert len(events) == 1
    assert phase.search_report()["streams"][0]["first_candidate_seconds"] == 0.1
    assert phase.search_report()["streams"][0]["gap_reached_seconds"]["2"] == 0.1
    hidden = PhaseTimer(collect_search=True)
    search_observers(hidden, "Search", lambda: 1)["on_search"](98, 100, 0)
    assert hidden.search_report()["observations"] == 1


def test_service_persists_observations_and_separate_validated_final_result(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(progress, "perf_counter", lambda: clock[0])

    def adapter(config, phase, session):
        clock[0] = 5
        phase.record_search(SearchStats("CP-SAT", 90, 100, 1))
        clock[0] = 8
        return EngineResult(
            raw={
                "solver": {
                    "algorithm": "cp-sat",
                    "status": "FEASIBLE",
                    "seconds": 3,
                    "workers": 1,
                    "bound": 100,
                    "objective": 90,
                }
            },
            income=90,
            buildings=[],
            metrics={},
        )

    monkeypatch.setattr(
        "twoptimizer.service.solve_adapter",
        lambda identifier: {"three_kingdoms": adapter}[identifier],
    )
    solved = service.solve_case(default_config("three_kingdoms"))
    report = solved.raw["search_measurements"]
    assert report["streams"][0]["first_candidate_seconds"] == 5
    assert report["final"] == {
        "status": "FEASIBLE",
        "income": 90,
        "bound": 100,
        "gap_percent": 10,
        "validated_layout": True,
        "case_elapsed_seconds": 8,
    }
    assert solved.to_dict()["raw"]["search_measurements"] == report


def test_runtime_finished_details_keep_observed_and_validated_milestones_distinct():
    config = default_config("three_kingdoms")
    payload = result(config)
    measurements = SearchMeasurements()
    measurements.observe(SearchStats("Search", 98, 100, 1), 5)
    payload["raw"]["search_measurements"] = measurements.to_dict(
        {"status": "FEASIBLE", "income": 98, "validated_layout": True, "case_elapsed_seconds": 8}
    )
    payload["solver"]["joint_bound_search"] = {"components": 70, "largest_component_variables": 450}
    view = RuntimeView()
    view.begin(config, 100)
    view.finish(payload, 110)
    rendered = view.details(1000)
    assert "first solver candidate observed at 5.00s" in rendered
    assert "Final independently validated income: 98.000 at 8.00s" in rendered
    assert "70 connected groups; largest has 450 variables" in rendered
    assert "Search milestones precede independent validation" in rendered
    view.begin(config, 2000)
    assert "5.00s" not in view.details(2001)


def test_no_streamed_observations_does_not_claim_no_candidate_exists():
    measurements = SearchMeasurements().to_dict(
        {"validated_layout": True, "income": 10, "case_elapsed_seconds": 2}
    )
    text = search_measurement_summary(measurements)
    assert "No streamed search observations" in text
    assert "Final independently validated income: 10.000" in text
    assert "first solver candidate" not in text
    assert search_measurement_summary({}) == ""
    assert bound_preparation_summary({}) == ""


def test_cancelled_result_keeps_observations_without_publishing_unvalidated_income():
    phase = PhaseTimer(collect_search=True)
    phase.record_search(SearchStats("Search", 98, 100, 1))
    cancelled = service._cancelled_result(default_config("three_kingdoms"), phase, "Stopped")
    report = cancelled.raw["search_measurements"]
    assert report["streams"][0]["first_candidate_seconds"] is not None
    assert report["final"]["validated_layout"] is False
    assert report["final"]["income"] is None
    assert cancelled.income is None and cancelled.solver.status == "UNKNOWN"
