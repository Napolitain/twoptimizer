"""Exercise optional multi-province controls without changing the normal flow."""

import asyncio

from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from tests.support.ui import QuickRunner, result
from twoptimizer.catalog import choices
from twoptimizer.province_picker import BorderPicker, ProvincePicker, ProvinceSelection
from twoptimizer.tui import OptimizerApp


def test_border_knowledge_is_pruned_on_removal_and_invalidated_on_addition():
    state = ProvinceSelection(("a", "b", "c"), True, (("a", "b"), ("b", "c")))
    assert state.with_provinces(("a", "b"), True).adjacency == (("a", "b"),)
    assert state.with_provinces(("a",), True).adjacency == ()
    assert state.with_provinces(("a", "b", "c", "d"), True).adjacency is None
    unknown = ProvinceSelection(("a", "b"), True)
    assert unknown.with_provinces(("a",), True).adjacency is None
    assert state.adjacency == (("a", "b"), ("b", "c"))


def test_search_preserves_hidden_selections_and_runs_the_complete_batch():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            await pilot.click("#choose-provinces")
            await pilot.pause()
            assert isinstance(app.screen, ProvincePicker)
            await pilot.click("#provinces-all")
            assert len(app.screen.selected) == len(choices("rome2")["provinces"])
            await pilot.click("#provinces-none")
            assert app.screen.selected == set()
            for query, key in [("Italia", "rome_main_italia"), ("Africa", "rome_main_africa")]:
                app.screen.query_one("#province-search", Input).value = query
                await pilot.pause()
                widget = app.screen.query_one("#province-list", SelectionList)
                widget.focus()
                widget.highlighted = 0
                await pilot.press("space")
                await pilot.pause()
                assert key in app.screen.selected
            await pilot.click("#provinces-apply")
            await pilot.pause()
            assert set(app._config().provinces) == {"rome_main_italia", "rome_main_africa"}
            assert not app.query_one("#province").display
            await pilot.press("ctrl+r")
            await app.workers.wait_for_complete()
            assert len(app.results) == 2
            assert {row["request"]["province"] for row in app.results} == {
                "rome_main_italia",
                "rome_main_africa",
            }
            assert not app.busy

    asyncio.run(exercise())


def test_no_selection_does_not_clear_results_and_single_mode_can_be_restored():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            app.results.append(result())
            await pilot.click("#choose-provinces")
            await pilot.click("#provinces-none")
            await pilot.click("#provinces-apply")
            await pilot.pause()
            assert app._config().provinces == ()
            assert app.query_one("#run", Button).disabled
            app.action_run()
            assert len(app.results) == 1 and not app.busy
            await pilot.click("#choose-provinces")
            await pilot.click("#provinces-all")
            await pilot.press("escape")
            await pilot.pause()
            assert app._config().provinces == ()
            await pilot.click("#choose-provinces")
            await pilot.click("#provinces-single")
            await pilot.pause()
            assert app._config().provinces is None
            assert app.query_one("#province").display
            assert not app.query_one("#run", Button).disabled

    asyncio.run(exercise())


def test_joint_attila_requires_borders_and_supports_explicit_no_neighbors():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            app.query_one("#game", Select).value = "attila"
            await pilot.pause()
            await pilot.click("#choose-provinces")
            await pilot.click("#provinces-none")
            widget = app.screen.query_one("#province-list", SelectionList)
            widget.select("att_prov_thracia")
            widget.select("att_prov_macedonia")
            app.screen.query_one("#joint-provinces", Checkbox).value = True
            await pilot.pause()
            await pilot.click("#provinces-apply")
            await pilot.pause()
            assert app._config().joint
            assert app.query_one("#run", Button).disabled
            await pilot.click("#choose-borders")
            await pilot.pause()
            assert isinstance(app.screen, BorderPicker)
            second = app.screen.query_one("#border-second", Select)
            second.value = app.screen.query_one("#border-first", Select).value
            await pilot.click("#border-add")
            assert "different" in str(app.screen.query_one("#border-error", Static).render())
            second.value = "att_prov_thracia"
            await pilot.pause(0.3)
            await pilot.click("#border-add")
            await pilot.pause(0.3)
            await pilot.click("#border-add")
            assert len(app.screen.borders) == 1
            await pilot.click("#borders-apply")
            await pilot.pause()
            assert len(app._config().adjacency) == 1
            assert not app.query_one("#run", Button).disabled
            await pilot.click("#choose-borders")
            app.screen.query_one("#border-list", SelectionList).select_all()
            await pilot.click("#border-remove")
            await pilot.click("#borders-apply")
            await pilot.pause()
            assert app._config().adjacency == ()
            assert not app.query_one("#run", Button).disabled
            app.query_one("#game", Select).value = "rome2"
            await pilot.pause()
            assert app._config().provinces is None and not app._config().joint
            await pilot.click("#choose-provinces")
            assert app.screen.query_one("#joint-provinces", Checkbox).disabled

    asyncio.run(exercise())


def test_picker_actions_remain_accessible_in_a_small_terminal():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.query_one("#choose-provinces", Button).focus()
            await pilot.pause(0.3)
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ProvincePicker)
            for selector in (
                "#provinces-all",
                "#provinces-none",
                "#provinces-apply",
                "#provinces-cancel",
            ):
                region = app.screen.query_one(selector).region
                assert region.y >= 0 and region.bottom <= 24
            await pilot.click("#provinces-none")
            await pilot.click("#provinces-apply")
            await pilot.pause()
            assert app._config().provinces == ()

    asyncio.run(exercise())


def test_multi_province_cancellation_keeps_completed_cases():
    class PausingRunner(QuickRunner):
        async def run(self, config, on_log, on_progress=None):
            if config.province == "inland":
                while not self.cancelled:
                    await asyncio.sleep(0.01)
                return None
            return await super().run(config, on_log, on_progress)

    async def exercise():
        app = OptimizerApp(runner_factory=PausingRunner)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            app.provinces_chosen(ProvinceSelection(("coastal", "inland")))
            await pilot.press("ctrl+r")
            await pilot.pause(0.2)
            assert app.busy and len(app.results) == 1
            await pilot.press("escape")
            await app.workers.wait_for_complete()
            assert not app.busy and len(app.results) == 1
            assert app.results[0]["request"]["province"] == "coastal"

    asyncio.run(exercise())


def test_research_exclusions_remain_attached_to_a_completed_batch():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            app.query_one("#faction", Select).value = "all"
            app.query_one("#research", Select).value = "public"
            await pilot.pause()
            await pilot.press("ctrl+r")
            await app.workers.wait_for_complete()
            assert len(app.results) == 29 and len(app.skipped) == 7

    asyncio.run(exercise())
