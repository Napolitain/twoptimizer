"""A graceful stop retains validated layouts; force stop keeps completed cases."""

import asyncio
import csv
import json

import pytest
from textual.widgets import Button, DataTable, Input, Select, Static, TabbedContent

from tests.support.ui import QuickRunner, result
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.province_picker import ProvinceSelection
from twoptimizer.screens import ExportScreen
from twoptimizer.tui import OptimizerApp


class ValidationRunner(QuickRunner):
    """Hold the active result until validation is explicitly allowed to finish."""

    def __init__(self, *, status="FEASIBLE", completed_before_active=0):
        super().__init__()
        self.status, self.completed_before_active = status, completed_before_active
        self.active, self.release, self.stop_requested = (
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
        )
        self.requests = []
        self.forced = self.running = False

    async def run(self, config, on_log, on_progress=None):
        self.requests.append(config)
        if len(self.requests) <= self.completed_before_active:
            return result(config)
        assert on_progress is not None
        on_progress("Solving and validating")
        on_progress(ModelStats("Native input", 80, 60, stage="solver"))
        if config.algorithm == "cp-sat":
            on_progress(
                SearchStats("CP-SAT", None if self.status == "UNKNOWN" else 98000, 100000, 2)
            )
        self.running = True
        self.active.set()
        try:
            await self.release.wait()
            return None if self.forced else self.completed(config)
        finally:
            self.running = False

    def completed(self, config):
        row = result(config)
        income = {"FEASIBLE": 98000, "OPTIMAL": 100000, "UNKNOWN": None}[self.status]
        bound = None if income is None else 100000
        row.update(income=income, gap_percent=None if income is None else (100000 - income) / 1000)
        row["solver"].update(status=self.status, objective=income, bound=bound)
        if income is None:
            row["buildings"] = []
        row["raw"]["cancellation"] = {
            "requested": self.stop_requested.is_set(),
            "incumbent_retained": income is not None,
        }
        return row

    async def request_stop(self):
        self.cancelled = True
        self.stop_requested.set()

    async def stop(self):
        await super().stop()
        if self.running:
            self.forced = True
            self.release.set()


def _select_batch(app, *, algorithm="cp-sat", count=2):
    app.province_selection = ProvinceSelection(("coastal", "inland", "grain")[:count])
    app.query_one("#algorithm", Select).value = algorithm
    app._refresh_preview()


async def _click_force_stop(app, pilot):
    button = app.query_one("#cancel", Button)
    assert str(button.label) == "Force stop"
    # Textual intentionally ignores clicks during a Button's active animation.
    async with asyncio.timeout(5):
        while button.has_class("-active"):
            await pilot.pause(0.02)
    assert await pilot.click("#cancel")


@pytest.mark.parametrize("size", [(80, 24), (110, 36)])
def test_cancel_waits_for_validation_then_displays_and_exports_best_layout(tmp_path, size):
    async def exercise():
        runner = ValidationRunner()
        app = OptimizerApp(runner_factory=lambda: runner)
        async with app.run_test(size=size) as pilot:
            _select_batch(app)
            await pilot.pause()
            assert await pilot.click("#run")
            await asyncio.wait_for(runner.active.wait(), 5)
            await pilot.pause()
            assert "98,000.000" in str(app.query_one("#search-progress", Static).content)
            assert "gap: 2.00%" in str(app.query_one("#search-progress", Static).content)
            assert not app.results and app.busy

            assert await pilot.click("#cancel")
            await asyncio.wait_for(runner.stop_requested.wait(), 5)
            assert app.busy and not runner.forced
            assert str(app.query_one("#cancel", Button).label) == "Force stop"
            assert app.query_one("#export", Button).disabled
            app.query_one("#tabs", TabbedContent).active = "runtime-pane"
            await pilot.pause()
            assert "validating the best layout" in str(
                app.query_one("#runtime-activity", Static).content
            )
            assert app.query_one("#cancel", Button).region.bottom <= size[1]

            runner.release.set()
            await asyncio.wait_for(app.workers.wait_for_complete(), 5)
            await pilot.pause()
            assert not app.busy and len(runner.requests) == len(app.results) == 1
            saved_result = app.results[0]
            assert saved_result["solver"]["status"] == "FEASIBLE"
            assert saved_result["income"] == 98000 and saved_result["gap_percent"] == 2
            assert saved_result["solver"]["bound"] == 100000
            assert saved_result["raw"]["cancellation"]["incumbent_retained"] is True
            assert str(app.query_one("#income", Static).content) == "98,000.000"
            assert str(app.query_one("#bound", Static).content) == "100,000.000"
            assert str(app.query_one("#status", Static).content) == "FEASIBLE"
            assert "validated layout retained" in str(
                app.query_one("#layout-summary", Static).content
            )
            assert app.query_one("#buildings", DataTable).row_count == 1
            assert not app.query_one("#export", Button).disabled

            assert await pilot.click("#export")
            await pilot.pause()
            assert isinstance(app.screen, ExportScreen)
            path = tmp_path / "cancelled.json"
            app.screen.query_one("#export-path", Input).value = str(path)
            assert await pilot.click("#save-file")
            await pilot.pause()
            exported = json.loads(path.read_text())
            assert exported["cases"] == [saved_result]
            with path.with_suffix(".csv").open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == 1 and rows[0]["status"] == "FEASIBLE"
            assert float(rows[0]["income"]) == 98000
            assert float(rows[0]["bound"]) == 100000 and float(rows[0]["gap_percent"]) == 2

    asyncio.run(exercise())


def test_second_cancel_discards_only_active_candidate_and_stops_later_jobs():
    async def exercise():
        runner = ValidationRunner(completed_before_active=1)
        app = OptimizerApp(runner_factory=lambda: runner)
        async with app.run_test(size=(110, 36)) as pilot:
            _select_batch(app, count=3)
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(runner.active.wait(), 5)
            await pilot.pause()
            completed = app.results[0]
            assert len(app.results) == 1 and app.current_search is not None
            assert await pilot.click("#cancel")
            await asyncio.wait_for(runner.stop_requested.wait(), 5)
            assert app.busy and not runner.forced
            await _click_force_stop(app, pilot)
            await asyncio.wait_for(app.workers.wait_for_complete(), 5)
            await pilot.pause()
            assert runner.forced and len(runner.requests) == 2
            assert not app.busy and app.results == [completed]
            assert app.query_one("#results", DataTable).row_count == 1
            assert str(app.query_one("#income", Static).content) == "4,182.700"
            assert app.current_search is None and not app.query_one("#search-progress").display
            assert not app.query_one("#export", Button).disabled

    asyncio.run(exercise())


@pytest.mark.parametrize("status", ["UNKNOWN", "OPTIMAL"])
def test_cancel_preserves_solver_outcome_without_inventing_proof_or_layout(status):
    async def exercise():
        runner = ValidationRunner(status=status)
        app = OptimizerApp(runner_factory=lambda: runner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.action_run()
            await asyncio.wait_for(runner.active.wait(), 5)
            await pilot.pause()
            assert await pilot.click("#cancel")
            await asyncio.wait_for(runner.stop_requested.wait(), 5)
            runner.release.set()
            await asyncio.wait_for(app.workers.wait_for_complete(), 5)
            await pilot.pause()
            assert len(app.results) == 1
            row = app.results[0]
            assert row["solver"]["status"] == status
            assert str(app.query_one("#status", Static).content) == status
            layout = str(app.query_one("#layout-summary", Static).content)
            if status == "UNKNOWN":
                assert row["income"] is None and row["gap_percent"] is None
                assert not row["buildings"] and not row["raw"]["cancellation"]["incumbent_retained"]
                assert "no validated layout retained" in layout
                assert str(app.query_one("#income", Static).content) == "—"
            else:
                assert row["income"] == row["solver"]["bound"] == 100000
                assert row["gap_percent"] == 0 and row["buildings"]
                assert "validated layout retained" in layout
                assert "Optimality proved" in str(
                    app.query_one("#runtime-activity", Static).content
                )

    asyncio.run(exercise())


def test_highs_cancel_explains_pending_native_search_and_force_stop():
    async def exercise():
        runner = ValidationRunner()
        app = OptimizerApp(runner_factory=lambda: runner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.query_one("#algorithm", Select).value = "highs"
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(runner.active.wait(), 5)
            app.query_one("#tabs", TabbedContent).active = "runtime-pane"
            await pilot.pause()
            assert await pilot.click("#cancel")
            await asyncio.wait_for(runner.stop_requested.wait(), 5)
            detail = str(app.query_one("#runtime-activity", Static).content)
            assert "HiGHS cannot interrupt native search" in detail
            assert "wait for its result or use Force stop" in detail
            assert app.busy and not runner.forced and not app.results
            await _click_force_stop(app, pilot)
            await asyncio.wait_for(app.workers.wait_for_complete(), 5)
            assert runner.forced and not app.busy and not app.results

    asyncio.run(exercise())
