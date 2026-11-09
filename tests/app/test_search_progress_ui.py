"""Live solver observations remain unfinished, bounded, and separate from results."""

import asyncio
import json

import pytest
from textual.widgets import Button, ProgressBar, Select, Static

from tests.support.ui import QuickRunner, result
from twoptimizer import progress as progress_module
from twoptimizer import service
from twoptimizer.models import RunConfig
from twoptimizer.presentation import search_summary
from twoptimizer.progress import (
    PREFIX,
    ModelStats,
    PhaseTimer,
    SearchStats,
    decode_progress,
    encode_progress,
)
from twoptimizer.runner import CaseRunner
from twoptimizer.tui import OptimizerApp


@pytest.mark.parametrize(
    "event",
    [
        "Building income model",
        ModelStats("Native input", 80, 60, stage="solver"),
        SearchStats("CP-SAT", None, 100, 0),
        SearchStats("CP-SAT", 90, 100, 1.25),
        SearchStats("Cost", 30, 20, 2, sense="minimize", unit="construction points"),
    ],
)
def test_progress_protocol_roundtrips_all_event_types_without_relabeling_units(event):
    encoded = json.loads(json.dumps(encode_progress(event), allow_nan=False))
    assert decode_progress(encoded) == event


@pytest.mark.parametrize(
    ("objective", "bound", "sense", "expected"),
    [(90, 100, "maximize", 10), (30, 20, "minimize", 50), (-10, -5, "maximize", 100)],
)
def test_reported_gap_respects_objective_direction(objective, bound, sense, expected):
    stats = SearchStats("Search", objective, bound, 3, sense=sense, unit="points")
    assert stats.gap_percent == expected
    text = search_summary(stats)
    assert ("Upper bound" in text) == (sense == "maximize")
    assert ("Lower bound" in text) == (sense == "minimize")
    assert "points" in text and "unfinished; validation pending" in text
    assert "OPTIMAL" not in text


@pytest.mark.parametrize(("objective", "bound"), [(None, 100), (10, None), (20, 10)])
def test_absent_or_inconsistent_bounds_do_not_claim_a_zero_gap(objective, bound):
    stats = SearchStats("CP-SAT", objective, bound, 0)
    assert stats.gap_percent is None
    assert "gap: unknown" in search_summary(stats)
    if objective is None:
        assert "candidate: not found" in search_summary(stats)


@pytest.mark.parametrize(
    "change",
    [
        {"objective": float("nan")},
        {"bound": float("inf")},
        {"bound": True},
        {"elapsed_seconds": -1},
        {"elapsed_seconds": None},
        {"sense": "unknown"},
    ],
)
def test_search_stats_reject_nonfinite_or_invalid_observations(change):
    values = {"label": "Search", "objective": 5, "bound": 10, "elapsed_seconds": 0, **change}
    with pytest.raises(ValueError):
        SearchStats.from_dict(values)


def test_search_updates_are_throttled_without_hiding_first_final_or_phase_events(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(progress_module, "perf_counter", lambda: clock[0])
    events = []
    timer = PhaseTimer(events.append)
    timer("solve", "Searching")
    first = SearchStats("CP-SAT", None, 100, 0)
    timer.record_search(first)
    clock[0] = 0.5
    timer.record_search(SearchStats("CP-SAT", 50, 100, 0.5))
    assert events == ["Searching", first]
    clock[0] = 0.75
    second = SearchStats("CP-SAT", 75, 90, 0.75)
    timer.record_search(second)
    final = SearchStats("CP-SAT", 80, 80, 0.8)
    clock[0] = 0.8
    timer.record_search(final, force=True)
    other = SearchStats("Other case", None, None, 0)
    timer.record_search(other)
    timer.record_model(ModelStats("Input", 5, 3, stage="solver"))
    timer()
    assert events[2:5] == [second, final, other]
    assert isinstance(events[-1], ModelStats)
    assert timer.timings == {"solve": 0.8}
    assert "OPTIMAL" not in search_summary(final)
    PhaseTimer().record_search(first)


def test_worker_pipe_decodes_search_and_keeps_models_and_phase_messages():
    async def exercise():
        events = [
            "Compiling",
            ModelStats("Native input", 80, 60, stage="solver"),
            "Searching",
            SearchStats("CP-SAT", 90, 100, 1.25),
        ]
        stream = asyncio.StreamReader()
        for event in events:
            stream.feed_data((PREFIX + json.dumps(encode_progress(event)) + "\n").encode())
        stream.feed_eof()

        class Process:
            stdout = stream

        received, logs = [], []
        await CaseRunner()._read_output(Process(), logs.append, received.append, 0)
        assert received == events
        assert logs[0] == "Phase: Compiling" and logs[2] == "Phase: Searching"
        assert "80 variables, 60 constraints (solver)" in logs[1]
        assert "candidate: 90.000 income/turn" in logs[3]
        assert "Upper bound: 100.000" in logs[3] and "gap: 10.00%" in logs[3]

    asyncio.run(exercise())


def test_constraint_comparison_preserves_search_units_and_side_label(monkeypatch):
    stats = SearchStats("CP-SAT", 90, 100, 1.25, unit="income/turn")
    completed = object()

    def solve(config, progress, session, cancellation):
        progress(stats)
        return completed

    monkeypatch.setattr(service, "solve_case", solve)
    events = []
    returned = service._comparison_side(
        RunConfig(), "Without requirements", events.append, None, None
    )
    assert returned is completed
    assert events == [SearchStats("Without requirements: CP-SAT", 90, 100, 1.25)]


@pytest.mark.parametrize("terminal_size", [(80, 24), (100, 32)])
def test_live_search_keeps_completed_results_and_resets_after_cancellation(terminal_size):
    async def exercise():
        active, stopped = asyncio.Event(), asyncio.Event()
        stats = SearchStats("CP-SAT", 1234, 1500, 12.5)

        class ControlledRunner(QuickRunner):
            async def run(self, config, on_log, on_progress=None):
                assert on_progress is not None
                if config.algorithm == "cp-sat":
                    return result(config)
                on_progress("Searching current case")
                on_progress(ModelStats("Native input", 80, 60, stage="solver"))
                on_progress(stats)
                active.set()
                await stopped.wait()
                return None

            async def stop(self):
                await super().stop()
                stopped.set()

        app = OptimizerApp(runner_factory=ControlledRunner)
        async with app.run_test(size=terminal_size) as pilot:
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(active.wait(), 5)
            await pilot.pause()
            completed = app.results[0]
            assert app.busy and len(app.results) == 1
            assert app.current_search == stats and app.current_phase == "Searching current case"
            assert str(app.query_one("#income", Static).content) == "4,182.700"
            assert "80 vars" in str(app.query_one("#model-size", Static).content)
            progress = app.query_one("#search-progress", Static)
            assert progress.display and "candidate: 1,234.000" in str(progress.content)
            assert "validation pending" in str(progress.content)
            assert app.query_one("#progress", ProgressBar).progress == 1
            assert app.query_one("#cancel", Button).region.bottom <= app.size.height
            assert app.query_one("#export", Button).region.bottom <= app.size.height
            await app.action_cancel()
            await app.workers.wait_for_complete()
            assert app.results == [completed]
            assert app.current_search is None and not progress.display
            app._phase_changed(stats)
            assert not progress.display
            app.action_clear()
            assert not app.results and not progress.display

    asyncio.run(exercise())
