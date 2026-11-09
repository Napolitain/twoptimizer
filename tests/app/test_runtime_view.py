"""Runtime context preserves proof boundaries and case/phase lifecycle."""

from dataclasses import replace

import pytest

from tests.support.ui import result
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.runtime_view import RuntimeView, case_status


@pytest.mark.parametrize(
    ("constrained", "baseline", "expected"),
    [
        ("OPTIMAL", "OPTIMAL", "OPTIMAL"),
        ("INFEASIBLE", "OPTIMAL", "INFEASIBLE"),
        ("OPTIMAL", "UNKNOWN", "FEASIBLE"),
        ("FEASIBLE", "OPTIMAL", "FEASIBLE"),
        ("INFEASIBLE", "UNKNOWN", "UNKNOWN"),
        ("UNKNOWN", "UNKNOWN", "UNKNOWN"),
        ("OPTIMAL", "ERROR", "ERROR"),
    ],
)
def test_comparison_runtime_needs_both_proofs(constrained, baseline, expected):
    report = result()
    report["solver"]["status"] = constrained
    report["raw"]["constraint_comparison"] = {"baseline": {"solver": {"status": baseline}}}
    assert case_status(report) == expected


def test_live_runtime_distinguishes_preparation_no_candidate_and_quiet_feasible_search():
    view = RuntimeView()
    assert "No active case" in view.details(0)
    view.begin(RunConfig(), 100)
    view.observe("Building income model", 101)
    assert "Preparation or validation" in view.details(110)
    view.observe(ModelStats("Native", 3, 2, stage="solver"), 110)
    assert "No candidate observed" in view.details(112)
    view.observe(SearchStats("CP-SAT", 80, 100, 5), 115)
    text = view.details(245)
    assert "2m 25s elapsed" in text  # Total case time includes preparation.
    assert "Candidate found at 5s" in text
    assert "layout 2m 10s ago" in text and "bound 2m 10s ago" in text
    assert "proof pending" in text and "20.00%" in text
    view.observe("With requirements: Solving and validating", 246)
    assert "solver candidate" not in view.details(246)
    view.observe(ModelStats("With requirements: Native", 3, 2, stage="solver"), 247)
    assert "No candidate observed" in view.details(250)
    assert "80.000" not in view.details(250)


def test_highs_never_implies_that_no_candidate_exists_without_telemetry():
    view = RuntimeView()
    view.begin(RunConfig(algorithm="highs"), 0)
    view.observe(ModelStats("Input", 3, 2, stage="solver"), 2)
    text = view.details(60)
    assert "does not stream" in text and "completion unknown" in text
    assert "No candidate" not in text


@pytest.mark.parametrize("report", [None, result()])
def test_finish_freezes_elapsed_and_retains_exact_session_history(report):
    view, config = RuntimeView(), RunConfig()
    view.begin(config, 10)
    view.finish(report, 75)
    first = view.details(100)
    assert "1m 5s elapsed" in first
    assert view.details(10000) == first
    view.observe(SearchStats("late", 100, 100, 1000), 10000)
    view.finish(report, 20000)
    assert view.details(20000) == first
    summary, details = view.preview(config, [config])
    expected = "stopped without proof" if report is None else "previously proved"
    assert expected in summary and "1 retained observations" in details
    changed = replace(config, seconds=1)
    assert "This session" not in view.preview(changed, [changed])[0]
    view.begin(changed, 20001)
    assert "Last case" not in view.details(20002)
    assert "previously" not in view.details(20002)


def test_execution_errors_do_not_become_solver_runtime_evidence():
    view, config = RuntimeView(), RunConfig()
    report = result(config)
    report["solver"]["status"] = "ERROR"
    view.begin(config, 0)
    view.finish(report, 3)
    assert "Case or comparison failed" in view.details(3)
    assert "This session" not in view.preview(config, [config])[0]


def test_incompatible_comparison_is_not_remembered_as_a_complete_proof():
    report = result()
    report["raw"]["constraint_comparison"] = {
        "status": "unavailable",
        "baseline": {"solver": {"status": "OPTIMAL"}},
        "reason": "The results use different model or data snapshots.",
    }
    assert case_status(report) == "ERROR"
