"""Interactive navigation, engine isolation, CLI compatibility and export checks."""

import asyncio
import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from textual.widgets import Button, Checkbox, DataTable, Input, Select, TabbedContent

from twoptimizer.catalog import choices
from twoptimizer.export import export_session
from twoptimizer.models import RunConfig
from twoptimizer.runner import CaseRunner
from twoptimizer.service import make_jobs
from twoptimizer.tui import ExportScreen, OptimizerApp


def result(config=None):
    config = config or RunConfig()
    return {
        "request": asdict(config),
        "faction": "Rome",
        "province": "Coastal reference",
        "solver": {
            "algorithm": config.algorithm,
            "status": "OPTIMAL",
            "seconds": 0.1,
            "objective": 4182.7,
            "bound": 4182.7,
        },
        "income": 4182.7,
        "gap_percent": 0,
        "metrics": {"food_surplus": 2, "public_order": 1},
        "buildings": [{"region": "Capital", "building": "Test Market", "id": "market_4"}],
        "assumptions": "Explicit test scenario",
        "source_files": {},
        "raw": {},
    }


class QuickRunner:
    def __init__(self):
        self.cancelled = False

    async def run(self, config, on_log, on_progress=None):
        await asyncio.sleep(0.02)
        if on_progress:
            on_progress("Solving and validating")
        on_log("Validated test layout")
        return result(config)

    async def stop(self):
        self.cancelled = True


def test_all_factions_and_solver_comparisons_expand_explicitly():
    jobs, skipped = make_jobs(RunConfig(faction="all", algorithm="compare"))
    assert len(jobs) == 36 * 4 and not skipped
    assert {j.algorithm for j in jobs} == {"cp-sat", "cbc", "scip", "scip-nonlinear"}
    researched, skipped = make_jobs(RunConfig(faction="all", research="public"))
    assert len(researched) == 29 and len(skipped) == 7
    assert all(j.research == "public" for j in researched)
    with pytest.raises(ValueError, match="incomplete"):
        make_jobs(RunConfig(research="public"))


@pytest.mark.parametrize(
    "config",
    [
        RunConfig(seconds=float("nan")),
        RunConfig(seconds=-1),
        RunConfig(workers=0),
        RunConfig(province="unknown"),
        RunConfig(algorithm="unknown"),
        RunConfig(game="three_kingdoms"),
    ],
)
def test_invalid_requests_are_rejected_before_spawning(config):
    with pytest.raises(ValueError):
        make_jobs(config)


def test_export_roundtrip_and_existing_csv_is_protected(tmp_path):
    path = tmp_path / "run.json"
    json_path, csv_path = export_session(path, [result()], skipped=["Incomplete research"])
    saved = json.loads(json_path.read_text())
    assert saved["cases"][0]["income"] == 4182.7
    assert saved["skipped"] == ["Incomplete research"]
    assert "OPTIMAL" in csv_path.read_text()
    json_path.unlink()
    with pytest.raises(FileExistsError):
        export_session(path, [result()])
    assert not json_path.exists()
    export_session(path, [result()], overwrite=True)


def test_keyboard_mouse_game_changes_run_layout_and_export(tmp_path):
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(120, 42)) as pilot:
            await pilot.pause()
            assert app.query_one("#algorithm", Select).value == "portfolio"
            assert app._config().seconds is None
            assert app._config().workers is None
            assert not app.query("#workers")
            assert not app.query_one("#time-options").display
            # A Select opens on click and navigates with arrow keys.
            await pilot.click("#game")
            await pilot.press("down", "enter")
            await pilot.pause()
            assert app.query_one("#game", Select).value == "attila"
            assert app.query_one("#attila-options").display
            app.query_one("#game", Select).value = "three_kingdoms"
            await pilot.pause()
            assert app.query_one("#run", Button).disabled
            app.query_one("#game", Select).value = "shogun2"
            await pilot.pause()
            assert app.query_one("#research", Select).value == "all"
            assert app.query_one("#shogun-options").display
            app.query_one("#game", Select).value = "rome2"
            await pilot.pause()
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            await pilot.click("#run")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(app.results) == 4
            assert app.query_one("#results", DataTable).row_count == 4
            assert not app.busy
            app.query_one("#results", DataTable).focus()
            await pilot.press("down", "enter")
            assert app.query_one("#tabs", TabbedContent).active == "buildings-pane"
            assert app.query_one("#buildings", DataTable).row_count == 1
            await pilot.press("ctrl+s")
            await pilot.pause()
            assert isinstance(app.screen, ExportScreen)
            app.screen.query_one("#export-path", Input).value = str(tmp_path / "interactive.json")
            await pilot.click("#save-file")
            await pilot.pause()
            assert (tmp_path / "interactive.json").exists()
            assert (tmp_path / "interactive.csv").exists()
            await pilot.press("f1")
            await pilot.press("escape")

    asyncio.run(exercise())


def test_small_terminal_and_invalid_input_keep_actions_accessible():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.query_one("#time-limit", Checkbox).value = True
            await pilot.pause()
            app.query_one("#seconds", Input).value = "0"
            await pilot.pause()
            assert app.query_one("#run", Button).disabled
            app.query_one("#seconds", Input).value = "2"
            await pilot.pause()
            assert not app.query_one("#run", Button).disabled
            assert await pilot.click("#run")
            await app.workers.wait_for_complete()
            assert app.results

    asyncio.run(exercise())


def test_cancelling_batch_preserves_completed_cases():
    class BlockingRunner(QuickRunner):
        async def run(self, config, on_log, on_progress=None):
            if config.algorithm == "cp-sat":
                return result(config)
            while not self.cancelled:
                await asyncio.sleep(0.01)
            return None

    async def exercise():
        app = OptimizerApp(runner_factory=BlockingRunner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            assert app.busy and len(app.results) == 1
            await pilot.press("escape")
            await app.workers.wait_for_complete()
            assert len(app.results) == 1 and not app.busy
            assert not app.query_one("#export", Button).disabled

    asyncio.run(exercise())


@pytest.mark.parametrize("game", ["rome2", "shogun2", "attila"])
def test_real_engine_worker(game):
    options = choices(game)
    config = RunConfig(
        game=game,
        faction=options["default_faction"],
        province=options["default_province"],
        algorithm="cp-sat",
        seconds=3,
        workers=2,
        research=options["default_research"],
    )

    async def exercise():
        runner = CaseRunner()
        output = await runner.run(config, lambda _: None)
        assert output["solver"]["status"] in {
            "OPTIMAL",
            "FEASIBLE",
            "UNKNOWN",
            "INFEASIBLE",
        }
        assert output["request"] == asdict(config)
        assert output["source_files"]
        assert output["timings"]["worker_wall_seconds"] > 0
        assert output["timings"]["worker_startup_seconds"] >= 0
        assert output["solver"]["workers"] >= 1
        if game == "attila":
            assert output["solver"]["model_stats"]["formulation"] == "factored_income"
            assert output["raw"]["model_size"]["cp_sat"] == output["solver"]["model_stats"]
        if game == "rome2":
            assert output["solver"]["formulation"] == "linearized_income"
        if output["income"] is not None:
            assert output["buildings"] and output["metrics"]["food_surplus"] >= 0
        assert runner.process is not None
        assert runner.process.returncode == 0

    asyncio.run(exercise())


def test_parser_data_discovery_does_not_search_for_a_git_checkout(monkeypatch):
    from games.tw.parser.parser import Parser

    def no_git_search(path):
        raise AssertionError(f"Parser must use packaged paths, not inspect {path}")

    from games.tw.parser.parser_attila import ParserAttila

    target = object.__new__(ParserAttila)
    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "exists", no_git_search)
        from games.tw.context import GameContext

        Parser.__init__(target, context=GameContext())
    assert target.game_dir.name == "data"
    assert target.game_dir.parent.name == "tw"


def test_cancel_terminates_real_solver_process():
    async def exercise():
        runner = CaseRunner()
        task = asyncio.create_task(runner.run(replace(RunConfig(), seconds=60), lambda _: None))
        while runner.process is None:
            await asyncio.sleep(0.01)
        await runner.stop()
        assert await asyncio.wait_for(task, 5) is None
        assert runner.process is not None
        assert runner.process.returncode is not None

    asyncio.run(exercise())


def test_quit_stops_an_active_batch():
    class BlockingRunner(QuickRunner):
        async def run(self, config, on_log, on_progress=None):
            while not self.cancelled:
                await asyncio.sleep(0.01)

    async def exercise():
        app = OptimizerApp(runner_factory=BlockingRunner)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.press("ctrl+r")
            await pilot.pause()
            assert app.busy
            await pilot.press("ctrl+q")
        assert app.runner is not None
        assert app.runner.cancelled

    asyncio.run(exercise())


def test_cli_dispatch_and_no_parameter_launch(monkeypatch):
    from games.tw.rome2 import benchmark
    from twoptimizer import __main__ as entry
    from twoptimizer import tui

    forwarded = []
    monkeypatch.setattr(benchmark, "main", lambda args: forwarded.append(args))
    assert entry.main(["rome2", "--layout", "coastal"]) == 0
    assert forwarded == [["--layout", "coastal"]]
    opened = []
    monkeypatch.setattr(entry.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(entry.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(tui.OptimizerApp, "run", lambda self: opened.append(True))
    assert entry.main([]) == 0 and opened == [True]
