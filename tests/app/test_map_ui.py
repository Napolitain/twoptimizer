"""Automatic campaign borders and explicit edits remain distinct in the TUI."""

import asyncio
from dataclasses import replace

import pytest
from textual.app import App
from textual.widgets import Button, SelectionList, Static

from tests.support.ui import QuickRunner
from twoptimizer.models import RunConfig
from twoptimizer.presentation import border_summary
from twoptimizer.province_picker import (
    USE_MAP_BORDERS,
    BorderPicker,
    ProvinceSelection,
)
from twoptimizer.tui import OptimizerApp

ROME = ("rome_main_italia", "rome_main_cisalpina")


def test_automatic_selection_stays_automatic_but_manual_additions_require_review():
    auto = ProvinceSelection(("a", "b"), True)
    expanded = auto.with_provinces(("a", "b", "c"), True)
    assert expanded.adjacency is None and not expanded.borders_need_review
    manual = ProvinceSelection(("a", "b"), True, (("a", "b"),))
    assert manual.with_provinces(("a",), True).adjacency == ()
    expanded = manual.with_provinces(("a", "b", "c"), True)
    assert expanded.adjacency is None and expanded.borders_need_review
    assert expanded.with_provinces(("a", "b", "c"), True).borders_need_review


@pytest.mark.parametrize("mode", ["auto", "custom", "none", "unavailable"])
def test_border_picker_preserves_override_and_cancel_semantics(mode):
    class PickerApp(App):
        selected = "pending"

        def on_mount(self):
            explicit = None if mode in {"auto", "unavailable"} else ()
            self.push_screen(
                BorderPicker(
                    [("First", "a"), ("Second", "b")],
                    explicit,
                    map_borders=None if mode == "unavailable" else (("a", "b"),),
                ),
                self.finish,
            )

        def finish(self, selection):
            self.selected = selection

    async def exercise():
        app = PickerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, BorderPicker)
            if mode == "auto":
                assert app.screen.borders == {("a", "b")}
                assert "automatic" in str(app.screen.query_one("#border-source", Static).content)
                await pilot.click("#borders-cancel")
                assert app.selected is None
            elif mode == "unavailable":
                assert app.screen.query_one("#borders-map", Button).disabled
                assert app.screen.borders == set()
                await pilot.click("#borders-apply")
                assert app.selected == ()
            elif mode == "custom":
                assert app.screen.borders == set()
                await pilot.click("#borders-map")
                assert app.selected is USE_MAP_BORDERS
            else:
                assert app.screen.borders == set()
                await pilot.click("#borders-apply")
                assert app.selected == ()

    asyncio.run(exercise())


def test_preview_distinguishes_automatic_map_and_custom_border_counts():
    config = RunConfig(provinces=ROME, joint=True)
    assert border_summary(config) == "1 map border · automatic"
    assert border_summary(replace(config, adjacency=(ROME,))) == "1 supplied border · custom"
    assert border_summary(replace(config, adjacency=())) == "0 supplied borders · custom"


def test_ui_uses_auto_map_and_can_restore_it_after_explicit_no_borders():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            app.provinces_chosen(ProvinceSelection(ROME, True))
            assert app._config().adjacency is None
            assert not app.query_one("#run", Button).disabled
            assert "map border · automatic" in str(app.query_one("#preview", Static).content)
            app.choose_borders()
            await pilot.pause()
            assert isinstance(app.screen, BorderPicker)
            assert len(app.screen.borders) == 1
            app.screen.query_one("#border-list", SelectionList).select_all()
            app.screen.remove_borders()
            assert "Custom border list" in str(
                app.screen.query_one("#border-source", Static).content
            )
            await pilot.click("#borders-apply")
            await pilot.pause()
            assert app._config().adjacency == ()
            assert "0 supplied borders · custom" in str(app.query_one("#preview", Static).content)
            app.choose_borders()
            await pilot.pause()
            await pilot.click("#borders-map")
            await pilot.pause()
            assert app._config().adjacency is None
            app.action_run()
            await app.workers.wait_for_complete()
            assert app.results[0]["request"]["adjacency"] is None

    asyncio.run(exercise())


def test_custom_border_expansion_requires_review_before_keyboard_run():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            manual = ProvinceSelection(ROME, True, (ROME,))
            expanded = manual.with_provinces((*ROME, "rome_main_magna_graecia"), True)
            app.provinces_chosen(expanded)
            assert app.query_one("#run", Button).disabled
            assert "Review custom borders" in str(app.query_one("#preview", Static).content)
            await pilot.press("ctrl+r")
            assert app.runner is None and not app.results
            app.choose_borders()
            await pilot.pause()
            await pilot.click("#borders-map")
            await pilot.pause()
            assert not app.province_selection.borders_need_review
            assert app._config().adjacency is None
            assert not app.query_one("#run", Button).disabled

    asyncio.run(exercise())
