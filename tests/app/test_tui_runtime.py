"""Runtime evidence and quiet-search clocks remain usable in small terminals."""

import asyncio

import pytest
from textual.widgets import Button, Static, TabbedContent

from tests.support.paths import REPO_ROOT
from tests.support.ui import QuickRunner
from twoptimizer import tui
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.tui import OptimizerApp


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
def test_runtime_tab_tracks_silent_search_and_cancelled_case_history(monkeypatch, size):
    clock = [100.0]
    monkeypatch.setattr(tui, "perf_counter", lambda: clock[0])

    async def exercise():
        started, stopped = asyncio.Event(), asyncio.Event()

        class ControlledRunner(QuickRunner):
            async def run(self, config, on_log, on_progress=None):
                assert on_progress is not None
                on_progress("Solving and validating")
                on_progress(ModelStats("Native input", 80, 60, stage="solver"))
                clock[0] = 102
                on_progress(SearchStats("CP-SAT", 80, 100, 2))
                started.set()
                await stopped.wait()
                return None

            async def stop(self):
                await super().stop()
                stopped.set()

        app = OptimizerApp(runner_factory=ControlledRunner)
        async with app.run_test(size=size) as pilot:
            assert "Runtime:" in str(app.query_one("#intro", Static).content)
            app.action_run()
            await asyncio.wait_for(started.wait(), 5)
            app.query_one("#tabs", TabbedContent).active = "runtime-pane"
            clock[0] = 225
            app._tick()
            await pilot.pause()
            detail = str(app.query_one("#runtime-activity", Static).content)
            assert "2m 5s elapsed" in detail and "Candidate found at 2s" in detail
            assert "layout 2m 3s ago" in detail and "bound 2m 3s ago" in detail
            assert app.query_one("#runtime-scroll").region.height >= 6
            assert not app.query_one("#search-progress").display
            assert "Search 125.0s" in str(app.query_one("#search-progress", Static).content)
            assert "2m 5s elapsed" in str(app.query_one("#run-status", Static).content)
            assert str(app.query_one("#income", Static).content) == "—"
            assert app.query_one("#cancel", Button).region.bottom <= size[1]
            assert app.query_one("#export", Button).region.bottom <= size[1]
            app.query_one("#tabs", TabbedContent).active = "results-pane"
            await pilot.pause()
            assert app.query_one("#search-progress").display
            assert app.query_one("#model-size").display
            app.query_one("#tabs", TabbedContent).active = "runtime-pane"
            await pilot.pause()
            await app.action_cancel()
            await app.workers.wait_for_complete()
            assert not app.busy and not app.results
            assert "stopped without proof" in str(app.query_one("#intro", Static).content)
            assert "Cancelled" in str(app.query_one("#runtime-activity", Static).content)
            assert not app.query_one("#search-progress").display
            app._phase_changed(SearchStats("late", 100, 100, 1000))
            assert not app.query_one("#search-progress").display

    asyncio.run(exercise())


def test_completed_run_supplies_history_before_next_run_and_after_clear():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 32)) as pilot:
            app.action_run()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert "previously proved" in str(app.query_one("#intro", Static).content)
            assert "Optimality proved" in str(app.query_one("#runtime-activity", Static).content)
            app.action_clear()
            assert "previously proved" in str(app.query_one("#intro", Static).content)
            assert not app.results

    asyncio.run(exercise())


def test_late_settings_event_does_not_refresh_the_closed_runtime_view():
    class ClosingApp(OptimizerApp):
        CSS_PATH = REPO_ROOT / "twoptimizer" / "workspace.tcss"
        delivered_after_close = False

        async def _close_all(self):
            await super()._close_all()
            assert not self.is_running and self._ui_ready and not self._loading_settings
            self.settings_changed()
            self.delivered_after_close = True

    async def exercise():
        app = ClosingApp(runner_factory=QuickRunner)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
        assert app.delivered_after_close

    asyncio.run(exercise())
