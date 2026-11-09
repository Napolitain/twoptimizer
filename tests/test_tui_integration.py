"""Regression coverage for merging the terminal app with strict engine tooling."""

import asyncio
import json
import subprocess
import sys
from dataclasses import replace

import pytest

from twoptimizer import __main__ as entry
from twoptimizer import worker
from twoptimizer.catalog import choices
from twoptimizer.errors import ApplicationError
from twoptimizer.models import RunConfig
from twoptimizer.runner import CaseRunner
from twoptimizer.service import make_jobs, solve_case
from twoptimizer.tui import OptimizerApp


@pytest.mark.parametrize("game", ["rome2", "shogun2", "attila", "three_kingdoms"])
def test_ui_adapters_validate_real_engine_results(game):
    options = choices(game)
    config = RunConfig(
        game=game,
        faction=options["default_faction"],
        province=options["default_province"],
        research=options["default_research"],
        algorithm="cp-sat",
        seconds=5,
        workers=1,
    )
    result = solve_case(config).to_dict()
    assert result["request"] == config.to_dict()
    assert result["solver"]["status"] in {"OPTIMAL", "FEASIBLE"}
    assert result["income"] > 0
    assert result["buildings"]
    assert result["metrics"]["food_surplus"] >= 0
    assert all(len(digest) == 64 for digest in result["source_files"].values())
    assert result["solver"]["bound"] >= result["income"] - 1e-5
    assert result["gap_percent"] >= 0
    json.dumps(result, allow_nan=False)


def test_worker_success_and_error_are_portable_json(tmp_path, monkeypatch, capsys):
    request, output = tmp_path / "request.json", tmp_path / "result.json"
    config = RunConfig(
        game="shogun2",
        faction="oda",
        province="jap_owari",
        research="all",
        algorithm="cp-sat",
        seconds=5,
        workers=1,
    )
    request.write_text(json.dumps(config.to_dict()))
    monkeypatch.setattr(sys, "argv", ["worker", str(request), str(output)])
    assert worker.main() == 0
    result = json.loads(output.read_text())
    assert result["income"] > 0 and result["request"] == config.to_dict()
    request.write_text(json.dumps(replace(config, game="hoi4").to_dict()))
    assert worker.main() == 1
    assert "complete optimizer" in json.loads(output.read_text())["error"]
    assert "ApplicationError" in capsys.readouterr().err


def test_runner_exposes_worker_errors_and_reaps_process():
    async def exercise():
        runner, logs = CaseRunner(), []
        with pytest.raises(ApplicationError, match="complete optimizer"):
            await runner.run(RunConfig(game="hoi4"), logs.append)
        assert runner.process is not None and runner.process.returncode == 1
        assert any("ApplicationError" in line for line in logs)

    asyncio.run(exercise())


def test_stop_force_kills_a_worker_that_does_not_terminate(monkeypatch):
    class UnresponsiveProcess:
        returncode = None
        terminated = False
        killed = False

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            if not self.killed:
                raise TimeoutError
            return self.returncode

    async def exercise():
        runner, process = CaseRunner(), UnresponsiveProcess()
        monkeypatch.setattr(runner, "process", process)
        await runner.stop()
        assert process.terminated and process.killed
        assert process.returncode == -9 and runner.cancelled

    asyncio.run(exercise())


def test_settings_events_before_mount_do_not_query_missing_widgets():
    app = OptimizerApp()
    app.game_changed()
    app.settings_changed()
    assert not app.busy and not app.results


def test_noninteractive_launch_help_and_unknown_command(monkeypatch, capsys):
    monkeypatch.setattr(entry.sys.stdin, "isatty", lambda: False)
    assert entry.main([]) == 2
    assert "interactive terminal" in capsys.readouterr().err
    assert entry.main(["--help"]) == 0
    assert "attila-factions" in capsys.readouterr().out
    assert entry.main(["missing"]) == 2
    assert "Unknown command" in capsys.readouterr().err


def test_parser_can_be_imported_first_in_a_fresh_interpreter():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from games.tw.parser.parser_attila import ParserAttila; assert callable(ParserAttila)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert not result.stdout


@pytest.mark.parametrize(
    "changes",
    [
        {"workers": True},
        {"faction": "missing"},
        {"research": "missing"},
        {
            "game": "shogun2",
            "faction": "oda",
            "province": "jap_owari",
            "research": "all",
            "soil": "missing",
        },
        {
            "game": "shogun2",
            "faction": "oda",
            "province": "jap_owari",
            "research": "all",
            "tax": 101,
        },
        {
            "game": "shogun2",
            "faction": "oda",
            "province": "jap_owari",
            "research": "all",
            "town_wealth": -1,
        },
        {
            "game": "attila",
            "faction": "att_fact_eastern_roman_empire",
            "province": "att_prov_thracia",
            "research": "all",
            "fertility": -1,
        },
        {
            "game": "attila",
            "faction": "att_fact_eastern_roman_empire",
            "province": "att_prov_thracia",
            "research": "all",
            "religion": "missing",
        },
    ],
)
def test_invalid_game_specific_settings_never_reach_a_solver(changes):
    with pytest.raises(ValueError):
        make_jobs(replace(RunConfig(algorithm="cp-sat"), **changes))


@pytest.mark.parametrize(
    ("game", "changes", "message"),
    [
        ("shogun2", {"soil": "unknown"}, "Choose a listed soil profile."),
        ("shogun2", {"tax": float("nan")}, "Tax must be 0-100%; town wealth must be nonnegative."),
        ("shogun2", {"tax": float("inf")}, "Tax must be 0-100%; town wealth must be nonnegative."),
        (
            "shogun2",
            {"town_wealth": float("nan")},
            "Tax must be 0-100%; town wealth must be nonnegative.",
        ),
        ("attila", {"fertility": float("inf")}, "Fertility must be finite and nonnegative."),
        ("attila", {"religion": "unknown"}, "Choose an available religion."),
    ],
)
def test_invalid_settings_explain_the_rejected_field(game, changes, message):
    options = choices(game)
    config = RunConfig(
        game=game,
        algorithm="cp-sat",
        faction=options["default_faction"],
        province=options["default_province"],
        research=options["default_research"],
    )
    with pytest.raises(ValueError) as error:
        make_jobs(replace(config, **changes))
    assert str(error.value) == message


@pytest.mark.parametrize("tax", [0, 100])
def test_tax_boundaries_are_valid_and_need_no_solver(tax):
    jobs, skipped = make_jobs(
        RunConfig(
            game="shogun2",
            faction="oda",
            province="jap_owari",
            research="all",
            algorithm="cp-sat",
            tax=tax,
        )
    )
    assert len(jobs) == 1 and jobs[0].tax == tax and not skipped


def test_zero_fertility_is_a_supported_attila_scenario():
    jobs, skipped = make_jobs(
        RunConfig(
            game="attila",
            faction="att_fact_eastern_roman_empire",
            province="att_prov_thracia",
            research="all",
            algorithm="cp-sat",
            fertility=0,
        )
    )
    assert len(jobs) == 1 and jobs[0].fertility == 0 and not skipped


@pytest.mark.parametrize("soil", ["native", "barren", "very_fertile"])
def test_all_listed_soil_profiles_remain_available(soil):
    jobs, skipped = make_jobs(
        RunConfig(
            game="shogun2",
            faction="oda",
            province="jap_owari",
            research="all",
            algorithm="cp-sat",
            soil=soil,
        )
    )
    assert len(jobs) == 1 and jobs[0].soil == soil and not skipped
