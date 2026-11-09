"""Optional constraints stay explicit through mouse/keyboard editing and runs."""

import asyncio

import pytest
from textual.app import App
from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from tests.support.ui import QuickRunner
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.constraint_picker import ConstraintPicker, constraint_count
from twoptimizer.tui import OptimizerApp

BUILDINGS = [("Grand Temple", "temple"), ("Market", "market")]


class PickerApp(App):
    def __init__(self, game="rome2", options=None, *, joint=False):
        super().__init__()
        self.game, self.options, self.joint = game, options or ConstraintOptions(), joint
        self.selected = "pending"

    def on_mount(self):
        self.push_screen(
            ConstraintPicker(self.game, BUILDINGS, self.options, joint=self.joint), self.finish
        )

    def finish(self, options):
        self.selected = options


def test_building_require_forbid_search_remove_and_cancel():
    async def exercise():
        app = PickerApp()
        async with app.run_test(size=(100, 44)) as pilot:
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, ConstraintPicker)
            await pilot.click("#constraint-require")
            assert "Choose a building" in str(picker.query_one("#constraint-error", Static).content)
            await pilot.pause(0.25)  # Textual suppresses repeat presses during its animation.
            picker.query_one("#constraint-search", Input).value = "temple"
            await pilot.pause()
            picker.query_one("#constraint-building", Select).value = "temple"
            picker.query_one("#constraint-require", Button).focus()
            await pilot.press("enter")
            assert picker.required == {"temple"}
            await pilot.click("#constraint-forbid")
            assert not picker.forbidden
            assert "Remove the existing" in str(
                picker.query_one("#constraint-error", Static).content
            )
            await pilot.pause(0.25)
            picker.query_one("#constraint-search", Input).value = "market"
            await pilot.pause()
            picker.query_one("#constraint-building", Select).value = "market"
            picker.query_one("#constraint-forbid", Button).focus()
            await pilot.press("enter")
            assert picker.required == {"temple"} and picker.forbidden == {"market"}
            picker.query_one("#constraint-list", SelectionList).select(("Require", "temple"))
            await pilot.click("#constraint-remove")
            assert not picker.required and picker.forbidden == {"market"}
            await pilot.press("escape")
            assert app.selected is None
            assert app.options == ConstraintOptions()

    asyncio.run(exercise())


@pytest.mark.parametrize("game", ["attila", "shogun2", "rome2"])
def test_religious_options_apply_and_clear_without_changing_defaults(game):
    async def exercise():
        original = ConstraintOptions(required_buildings=("old_unavailable_id",))
        app = PickerApp(game, original, joint=True)
        async with app.run_test(size=(100, 44)) as pilot:
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, ConstraintPicker)
            assert picker.required == {"old_unavailable_id"}
            if game == "attila":
                picker.query_one("#constraint-influence", Input).value = "5"
                assert picker.options().minimum_religious_influence == 5
                picker.query_one("#constraint-influence", Input).value = "-1"
                await pilot.click("#constraints-apply")
                assert app.selected == "pending"
                assert "nonnegative" in str(picker.query_one("#constraint-error", Static).content)
                # A second click is ignored while Textual's pressed effect is active.
                # Wait for the actual widget duration before correcting and reapplying.
                await pilot.pause(
                    picker.query_one("#constraints-apply", Button).active_effect_duration
                )
                picker.query_one("#constraint-influence", Input).value = "5"
            elif game == "shogun2":
                picker.query_one("#constraint-faith", Select).value = "christian"
                picker.query_one("#constraint-nanban", Checkbox).value = True
                assert picker.options().shogun_religion == "christian"
                assert picker.options().nanban_contact
            else:
                assert not picker.query("#constraint-influence")
                assert not picker.query("#constraint-faith")
            await pilot.click("#constraints-clear")
            assert picker.options() == ConstraintOptions()
            await pilot.click("#constraints-apply")
            assert app.selected == ConstraintOptions()
            assert original.required_buildings == ("old_unavailable_id",)

    asyncio.run(exercise())


@pytest.mark.parametrize("game", ["attila", "shogun2"])
def test_faith_values_survive_apply(game):
    async def exercise():
        app = PickerApp(game)
        async with app.run_test(size=(100, 44)) as pilot:
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, ConstraintPicker)
            if game == "attila":
                picker.query_one("#constraint-influence", Input).value = "0"
                expected = ConstraintOptions(minimum_religious_influence=0)
            else:
                picker.query_one("#constraint-faith", Select).value = "buddhist"
                picker.query_one("#constraint-nanban", Checkbox).value = True
                expected = ConstraintOptions(shogun_religion="buddhist", nanban_contact=True)
            await pilot.click("#constraints-apply")
            assert app.selected == expected
            assert constraint_count(expected) == (1 if game == "attila" else 2)

    asyncio.run(exercise())


def test_tui_constraints_reach_requests_and_reset_on_game_change(monkeypatch):
    monkeypatch.setattr("twoptimizer.tui.building_choices", lambda config: BUILDINGS)

    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            assert app._config().constraints == ConstraintOptions()
            app.query_one("#game", Select).value = "attila"
            await pilot.pause()
            app.choose_constraints()
            await pilot.pause()
            assert isinstance(app.screen, ConstraintPicker)
            app.screen.query_one("#constraint-influence", Input).value = "2"
            await pilot.click("#constraints-apply")
            await pilot.pause()
            expected = ConstraintOptions(minimum_religious_influence=2)
            assert app._config().constraints == expected
            assert "(1)" in str(app.query_one("#choose-constraints", Button).label)
            app.action_run()
            await app.workers.wait_for_complete()
            assert app.results[0]["request"]["constraints"] == expected.to_dict()
            app.query_one("#game", Select).value = "shogun2"
            await pilot.pause()
            assert app._config().constraints == ConstraintOptions()
            assert "(" not in str(app.query_one("#choose-constraints", Button).label)
            app.query_one("#game", Select).value = "hoi4"
            await pilot.pause()
            assert app.query_one("#choose-constraints", Button).disabled

    asyncio.run(exercise())


def test_empty_catalog_still_allows_removing_stale_requirements():
    async def exercise():
        app = PickerApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.pop_screen()
            app.push_screen(
                ConstraintPicker("rome2", [], ConstraintOptions(required_buildings=("old",))),
                app.finish,
            )
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, ConstraintPicker)
            assert picker.required == {"old"}
            await pilot.click("#constraints-clear")
            await pilot.click("#constraints-apply")
            assert app.selected == ConstraintOptions()

    asyncio.run(exercise())
