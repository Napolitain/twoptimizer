"""Query scope and compiled counts remain distinct through the UI lifecycle."""

import asyncio

import pytest
from textual.widgets import Button, Checkbox, DataTable, Select, Static

from tests.support.ui import QuickRunner, result
from twoptimizer.holdings import named_province_choices
from twoptimizer.models import RunConfig
from twoptimizer.presentation import model_details, model_size_summary, query_summary
from twoptimizer.progress import ModelStats
from twoptimizer.province_picker import ProvinceSelection
from twoptimizer.registry import choices, game_plugin
from twoptimizer.service import make_jobs
from twoptimizer.tui import OptimizerApp


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
@pytest.mark.parametrize("joint", [False, True])
def test_query_summary_counts_cases_without_combining_independent_models(game, joint):
    options = choices(game)
    provinces = tuple(key for _, key in named_province_choices(game)[:2])
    config = RunConfig(
        game=game,
        faction=options.default_faction,
        province=provinces[0],
        research=options.default_research,
        provinces=provinces,
        joint=joint,
        adjacency=((provinces[0], provinces[1]),)
        if joint and game_plugin(game).capabilities.borders
        else None,
        algorithm="compare",
    )
    jobs, skipped = make_jobs(config)
    text = query_summary(config, jobs, skipped)
    assert f"2 provinces · {'together' if joint else 'independent'}" in text
    assert f"1 faction · {len(game_plugin(game).algorithms)} solver choices" in text
    assert f"{len(game_plugin(game).algorithms) * (1 if joint else 2)} cases" in text
    assert "until proved / cancelled" in text
    assert ("1 supplied border" in text) == (joint and game_plugin(game).capabilities.borders)


def test_counts_label_reference_solver_and_optional_metrics_honestly():
    reference = ModelStats(
        "Validation reference",
        1200,
        2400,
        formulation="expanded_income",
        decision_variables=10,
        nonzeros=400,
        storage_bytes=2 * 1024**2,
    )
    solver = ModelStats("CP-SAT", 80, 60, formulation="factored_income", stage="solver")
    text = model_details([reference, solver], "Active case")
    assert "Validation reference · reference model" in text
    assert "CP-SAT · solver model" in text
    assert "Variables: 1,200 · Constraints: 2,400" in text
    assert "Variables: 80 · Constraints: 60" in text
    assert "Decision variables: 10 · Auxiliary variables: 1,190" in text
    assert "Nonzero coefficients: 400" in text
    assert "Constraint matrix storage: 2.00 MiB" in text
    assert "Formulation: factored income" in text
    assert "before presolve" in text and "does not predict runtime" in text
    assert model_size_summary([reference, solver]) == (
        "Model size: 80 vars · 60 constraints · solver"
    )
    assert "no counts recorded" in model_size_summary([])


def test_scope_preview_handles_empty_selection_and_keeps_small_terminal_actions_accessible():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.provinces_chosen(ProvinceSelection(()))
            await pilot.pause()
            assert "0 provinces" in str(app.query_one("#preview", Static).content)
            assert "Select at least one province" in str(app.query_one("#preview", Static).content)
            assert app.query_one("#run", Button).disabled
            assert app.runner is None
            app.provinces_chosen(ProvinceSelection(("coastal", "inland")))
            await pilot.pause()
            assert "2 provinces · independent" in str(app.query_one("#preview", Static).content)
            assert "2 cases" in str(app.query_one("#preview", Static).content)
            assert "available after compilation" in str(
                app.query_one("#model-size", Static).content
            )
            assert await pilot.click("#run")
            await app.workers.wait_for_complete()
            assert len(app.results) == 2

    asyncio.run(exercise())


def test_live_model_counts_reset_between_cases_on_cancel_and_settings_changes():
    async def exercise():
        first_compiled, finish_first, second_started = (asyncio.Event() for _ in range(3))
        stats = ModelStats("CP-SAT", 80, 60, stage="solver")

        class ControlledRunner(QuickRunner):
            async def run(self, config, on_log, on_progress=None):
                assert on_progress is not None
                if config.algorithm == "cp-sat":
                    on_progress(ModelStats("Reference", 1200, 2400))
                    on_progress(stats)
                    on_progress("Solving and validating")
                    first_compiled.set()
                    await finish_first.wait()
                    completed = result(config)
                    completed["raw"]["model_complexity"] = [stats.to_dict()]
                    return completed
                second_started.set()
                while not self.cancelled:
                    await asyncio.sleep(0.01)
                return None

        app = OptimizerApp(runner_factory=ControlledRunner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(first_compiled.wait(), 5)
            assert app.current_phase == "Solving and validating"
            assert "80 vars" in str(app.query_one("#model-size", Static).content)
            details = str(app.query_one("#model-details", Static).content)
            assert "1,200" in details and "80" in details
            finish_first.set()
            await asyncio.wait_for(second_started.wait(), 5)
            await pilot.pause()
            assert app.current_models == []
            assert "compiling this case" in str(app.query_one("#model-size", Static).content)
            app._show_result(app.results[0])
            assert "Selected" in str(app.query_one("#model-details", Static).content)
            assert "80" in str(app.query_one("#model-details", Static).content)
            assert "compiling this case" in str(app.query_one("#model-size", Static).content)
            await app.action_cancel()
            await app.workers.wait_for_complete()
            assert len(app.results) == 1
            assert "80 vars" in str(app.query_one("#model-size", Static).content)
            app._show_result(app.results[0])
            assert "80 vars" in str(app.query_one("#model-size", Static).content)
            app.query_one("#world-bonuses", Checkbox).value = False
            await pilot.pause()
            assert "available after compilation" in str(
                app.query_one("#model-size", Static).content
            )
            app.action_clear()
            assert not app.results
            assert "80 vars" not in str(app.query_one("#model-size", Static).content)

    asyncio.run(exercise())


def test_browsing_results_restores_each_saved_model_size():
    class StatsRunner(QuickRunner):
        async def run(self, config, on_log, on_progress=None):
            completed = result(config)
            count = 10 if config.province == "coastal" else 20
            completed["raw"]["model_complexity"] = [
                ModelStats("Reference", count, count * 2).to_dict()
            ]
            return completed

    async def exercise():
        app = OptimizerApp(runner_factory=StatsRunner)
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause()
            app.provinces_chosen(ProvinceSelection(("coastal", "inland")))
            app.action_run()
            await app.workers.wait_for_complete()
            await pilot.pause()
            table = app.query_one("#results", DataTable)
            table.move_cursor(row=table.get_row_index("1"))
            await pilot.pause()
            assert "20 vars" in str(app.query_one("#model-size", Static).content)
            table.move_cursor(row=table.get_row_index("0"))
            await pilot.pause()
            assert "10 vars" in str(app.query_one("#model-size", Static).content)
            assert "Constraints: 20" in str(app.query_one("#model-details", Static).content)

    asyncio.run(exercise())
