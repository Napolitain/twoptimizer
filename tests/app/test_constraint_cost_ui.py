"""Comparison controls and result labels preserve proof/estimate distinctions."""

import asyncio
from dataclasses import replace

import pytest
from textual.widgets import Checkbox, DataTable, Select, Static, TabbedContent

from tests.support.ui import QuickRunner, result
from twoptimizer.comparison_presentation import (
    COMPARISON_EMPTY,
    COMPARISON_NOTE,
    comparison_rows,
    comparison_summary,
)
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.models import RunConfig
from twoptimizer.tui import OptimizerApp


def compared_result(status="exact"):
    config = RunConfig(
        constraints=ConstraintOptions(required_buildings=("temple",)),
        compare_constraints=True,
    )
    record = result(config)
    record["raw"]["constraint_comparison"] = {
        "status": status,
        "baseline_income": 100,
        "constrained_income": 90,
        "observed_income_difference": 10,
        "exact_cost": 10 if status == "exact" else None,
        "percent": 10 if status == "exact" else None,
        "cost_lower": 10 if status == "exact" else 0,
        "cost_upper": 10 if status == "exact" else 20,
        "baseline": result(replace(config, constraints=ConstraintOptions())),
        "added_buildings": [{"region": "Capital", "building": "Temple", "id": "temple"}],
        "removed_buildings": [{"region": "Capital", "building": "Market", "id": "market"}],
    }
    return record


def test_exact_cost_displays_proven_loss_and_preserved_assumptions():
    record = compared_result()
    summary = comparison_summary(record)
    assert "Proven income loss: 10.000 per turn" in summary
    assert "10.00%" in summary and "Income without requirements: 100.000" in summary
    assert COMPARISON_NOTE in summary
    assert "world settings stay the same" in summary
    assert comparison_rows(record) == [
        ("Added", "Capital", "Temple", "temple"),
        ("Removed", "Capital", "Market", "market"),
    ]


@pytest.mark.parametrize("upper", [20, None])
def test_unproved_negative_incumbent_difference_is_not_reported_as_a_saving(upper):
    record = compared_result("bounded")
    record["raw"]["constraint_comparison"].update(observed_income_difference=-5, cost_upper=upper)
    summary = comparison_summary(record)
    assert "Income-loss bounds:" in summary
    assert "Exact income loss is not yet proved" in summary
    assert "Observed income difference: -5.000" in summary
    assert "Proven income loss" not in summary and "saving" not in summary.lower()
    assert ("no finite upper bound" in summary) == (upper is None)


def test_unavailable_and_missing_results_do_not_invent_zero_cost():
    record = compared_result("unavailable")
    record["raw"]["constraint_comparison"].update(
        baseline_income=None,
        constrained_income=None,
        reason="No feasible constrained layout was returned.",
    )
    summary = comparison_summary(record)
    assert "Income cost unavailable: No feasible constrained layout was returned." in summary
    assert "Proven income loss" not in summary
    record["raw"].clear()
    assert "No comparison was returned" in comparison_summary(record)
    assert comparison_summary(result()) == COMPARISON_EMPTY
    assert comparison_rows(result()) == []


def test_building_difference_rows_retain_multiple_copies():
    record = compared_result()
    changes = record["raw"]["constraint_comparison"]
    changes["added_buildings"] *= 2
    assert [row[0] for row in comparison_rows(record)] == ["Added", "Added", "Removed"]


class ComparedRunner(QuickRunner):
    async def run(self, config, on_log, on_progress=None):
        output = await super().run(config, on_log, on_progress)
        output["raw"] = compared_result()["raw"]
        return output


def test_checkbox_reaches_worker_and_result_tab_then_resets_on_game_change():
    async def exercise():
        app = OptimizerApp(runner_factory=ComparedRunner)
        async with app.run_test(size=(120, 44)) as pilot:
            await pilot.pause()
            toggle = app.query_one("#compare-constraints", Checkbox)
            assert not toggle.value and not app._config().compare_constraints
            app.constraint_options = ConstraintOptions(required_buildings=("temple",))
            toggle.value = True
            await pilot.pause()
            assert app._config().compare_constraints
            assert "up to 2 solves" in str(app.query_one("#preview", Static).content)
            app.action_run()
            await app.workers.wait_for_complete()
            assert app.results[0]["request"]["compare_constraints"] is True
            app.query_one("#tabs", TabbedContent).active = "constraint-cost-pane"
            await pilot.pause()
            assert "Proven income loss" in str(
                app.query_one("#constraint-cost-summary", Static).content
            )
            assert app.query_one("#constraint-changes", DataTable).row_count == 2
            app.action_clear()
            assert app.query_one("#constraint-changes", DataTable).row_count == 0
            assert (
                str(app.query_one("#constraint-cost-summary", Static).content) == COMPARISON_EMPTY
            )
            app.query_one("#game", Select).value = "shogun2"
            await pilot.pause()
            assert not toggle.value and not app._config().compare_constraints
            app.query_one("#game", Select).value = "hoi4"
            await pilot.pause()
            assert toggle.disabled

    asyncio.run(exercise())


def test_selected_result_replaces_prior_comparison_and_changed_buildings():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(110, 42)) as pilot:
            await pilot.pause()
            app._show_result(compared_result())
            assert app.query_one("#constraint-changes", DataTable).row_count == 2
            timed = compared_result("bounded")
            timed["raw"]["constraint_comparison"]["added_buildings"] = []
            app._show_result(timed)
            assert app.query_one("#constraint-changes", DataTable).row_count == 1
            assert "Exact income loss is not yet proved" in str(
                app.query_one("#constraint-cost-summary", Static).content
            )
            app._show_result(result())
            assert app.query_one("#constraint-changes", DataTable).row_count == 0
            assert (
                str(app.query_one("#constraint-cost-summary", Static).content) == COMPARISON_EMPTY
            )

    asyncio.run(exercise())
