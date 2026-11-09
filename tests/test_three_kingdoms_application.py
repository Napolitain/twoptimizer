"""Historical Three Kingdoms inputs survive UI, CLI, worker and export boundaries."""

import asyncio
import csv
import json
from dataclasses import replace

import pytest
from textual.widgets import Button, Checkbox, Input, Select, SelectionList

from games.tw.cancellation import Cancellation
from tests.support.ui import QuickRunner, result
from twoptimizer import __main__ as entry
from twoptimizer.adapters.three_kingdoms import prepare_scenario
from twoptimizer.catalog import choices
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.export import export_session
from twoptimizer.holdings import map_context
from twoptimizer.models import RunConfig, RunRequest
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.service import solve_case
from twoptimizer.three_kingdoms_cli import parser, request_from_args
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions
from twoptimizer.tui import OptimizerApp

GAME = "three_kingdoms"
YINGCHUAN = "3k_main_province_yingchuan"
COPPER = "3k_main_provincial_resources_copper"


def test_cli_preserves_named_capital_resources_research_and_solver_comparison():
    args = parser().parse_args(
        [
            "--commandery",
            "Yingchuan",
            "--capital-commandery",
            "Yingchuan",
            "--resource",
            COPPER,
            "--reforms",
            "all",
            "--corruption",
            "25",
            "--population",
            "500000",
            "--algorithm",
            "cp-sat",
            "--algorithm",
            "highs",
            "--require-building",
            "3k_city_5",
            "--no-leader-effects",
        ]
    )
    jobs, skipped = make_jobs(request_from_args(args))
    assert not skipped and [job.algorithm for job in jobs] == ["cp-sat", "highs"]
    for job in jobs:
        scenario = prepare_scenario(job)
        assert scenario.capital_commandery == YINGCHUAN
        assert scenario.commanderies[0].population == 500000
        assert scenario.commanderies[0].corruption_percent == 25
        assert scenario.commanderies[0].city_level is None
        assert scenario.external_resources == (COPPER,)
        assert scenario.required_buildings == ("3k_city_5",)
        assert scenario.all_reforms
        assert not scenario.include_leader_effects
        assert RunConfig.from_dict(json.loads(json.dumps(job.to_dict()))) == job


@pytest.mark.parametrize(
    "changes",
    [
        {"population": -1},
        {"population": True},
        {"population": 1.5},
        {"city_level": 11},
        {"city_level": 0},
        {"corruption_percent": 101},
        {"order_offset": float("nan")},
        {"external_food": float("inf")},
        {"include_leader_effects": "false"},
    ],
)
def test_bad_snapshot_inputs_fail_before_starting_a_solver(changes):
    config = replace(default_config(GAME), three_kingdoms=ThreeKingdomsOptions(**changes))
    with pytest.raises(ValueError):
        make_jobs(config)


@pytest.mark.parametrize("resources", ["copper", [COPPER, COPPER], [True]])
def test_resource_lists_reject_malformed_or_duplicate_values(resources):
    with pytest.raises(ValueError):
        RunConfig.from_dict({"three_kingdoms": {"external_resources": resources}})


def test_game_options_cannot_be_silently_applied_to_another_game():
    with pytest.raises(ValueError, match="require the Three Kingdoms game"):
        make_jobs(RunConfig(three_kingdoms=ThreeKingdomsOptions(population=5)))
    with pytest.raises(ValueError, match="JSON object"):
        RunConfig.from_dict({"three_kingdoms": []})


def test_new_auto_defaults_are_explicit_and_old_requests_keep_fixed_city_level():
    fresh = default_config(GAME)
    assert fresh.three_kingdoms.city_level is None
    payload = json.loads(json.dumps(fresh.to_dict()))
    assert payload["three_kingdoms"]["city_level"] is None
    assert RunConfig.from_dict(payload) == fresh
    payload.pop("three_kingdoms")
    legacy = RunConfig.from_dict(payload)
    assert legacy.three_kingdoms.city_level == 5
    payload["three_kingdoms"] = {}
    assert RunConfig.from_dict(payload) == legacy
    assert prepare_scenario(legacy).commanderies[0].city_level == 5


@pytest.mark.parametrize("value, expected", [("auto", None), ("1", 1), ("5", 5), ("10", 10)])
def test_cli_auto_and_fixed_city_levels_translate_without_changing_other_inputs(value, expected):
    args = parser().parse_args(["--city-level", value])
    config = request_from_args(args).config
    assert config.three_kingdoms.city_level == expected
    assert config.three_kingdoms.population == 1_000_000
    assert config.three_kingdoms.external_food == 0


@pytest.mark.parametrize("value", ["0", "11", "5.5", "unknown"])
def test_cli_city_levels_reject_uninhabited_out_of_range_and_noninteger_values(value):
    with pytest.raises(SystemExit):
        parser().parse_args(["--city-level", value])


def test_zero_all_and_joint_batch_modes_preserve_each_commandery():
    base = default_config(GAME)
    assert make_jobs(replace(base, provinces=())) == ([], [])
    independent, _ = make_jobs(RunRequest(base, provinces=("all",)))
    assert {job.province for job in independent} == {key for _, key in choices(GAME)["provinces"]}
    joint, _ = make_jobs(RunRequest(base, provinces=("all",), joint=True))
    assert len(joint) == 1 and joint[0].joint
    assert set(joint[0].holdings) == {job.province for job in independent}
    assert map_context(joint[0])["mode"] == "unverified_no_effect"
    changed = replace(joint[0], three_kingdoms=ThreeKingdomsOptions(corruption_percent=25))
    with pytest.raises(ValueError, match="neighboring provinces"):
        make_jobs(changed)
    explicit, _ = make_jobs(replace(changed, adjacency=()))
    assert map_context(explicit[0])["mode"] == "none"


def test_one_joint_commandery_needs_no_internal_border_at_positive_corruption():
    config = replace(
        default_config(GAME),
        joint=True,
        three_kingdoms=ThreeKingdomsOptions(corruption_percent=25),
    )
    jobs, _ = make_jobs(config)
    assert len(jobs) == 1
    assert prepare_scenario(jobs[0]).adjacency == ()
    assert map_context(jobs[0])["mode"] == "not_applied"


def test_export_records_snapshot_inputs_without_changing_legacy_csv(tmp_path):
    config = replace(default_config(GAME), three_kingdoms=ThreeKingdomsOptions(population=500000))
    payload = result(config)
    json_path, csv_path = export_session(tmp_path / "historical", [payload])
    assert json.loads(json_path.read_text())["cases"][0]["request"] == config.to_dict()
    with csv_path.open() as stream:
        row = next(csv.DictReader(stream))
    assert json.loads(row["three_kingdoms"])["population"] == 500000


def test_native_cli_dispatch_compares_both_solvers_and_exports_provenance(tmp_path):
    output = tmp_path / "native"
    assert (
        entry.main(
            [
                "three-kingdoms",
                "--commandery",
                "Yingchuan",
                "--algorithm",
                "cp-sat",
                "--algorithm",
                "highs",
                "--seconds",
                "5",
                "--workers",
                "1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    reports = json.loads(output.with_suffix(".json").read_text())["cases"]
    assert len(reports) == 2
    assert all(row["solver"]["status"] == "OPTIMAL" for row in reports)
    assert reports[0]["income"] == pytest.approx(reports[1]["income"])
    for row in reports:
        assert row["income"] > 0 and row["metrics"]["food_surplus"] >= 0
        assert row["metrics"]["public_order"] >= 0
        assert "1.2.0" in row["assumptions"]
        assert row["source_files"]["three_kingdoms/data/reference.json"]
        assert row["raw"]["model_complexity"]
        assert all("Yingchuan," in placement["region"] for placement in row["buildings"])
        assert row["request"]["three_kingdoms"]["city_level"] is None
        assert row["raw"]["commanderies"][YINGCHUAN]["city_level"] in range(1, 11)
        assert any("city level" in building["building"] for building in row["buildings"])


def test_native_constraint_comparison_preserves_building_requirements_and_snapshot():
    forbidden = "3k_district_artisan_workshop_state_2"
    config = replace(
        default_config(GAME),
        seconds=5,
        workers=1,
        compare_constraints=True,
        constraints=ConstraintOptions(forbidden_buildings=(forbidden,)),
    )
    result = solve_case(config)
    assert result.solver.status == "OPTIMAL"
    assert result.income is not None
    assert forbidden not in {building.id for building in result.buildings}
    comparison = result.raw["constraint_comparison"]
    assert comparison["status"] == "exact"
    assert comparison["exact_cost"] >= 0
    assert comparison["baseline"]["request"]["three_kingdoms"] == config.three_kingdoms.to_dict()
    assert comparison["baseline_income"] - result.income == pytest.approx(comparison["exact_cost"])


def test_auto_city_default_recovers_a_holding_infeasible_at_fixed_level_five():
    commandery = "3k_main_province_changan"
    config = replace(default_config(GAME), province=commandery, seconds=5, workers=1)
    fixed = solve_case(replace(config, three_kingdoms=ThreeKingdomsOptions(city_level=5)))
    assert fixed.solver.status == "INFEASIBLE" and fixed.income is None
    automatic = solve_case(config)
    assert automatic.solver.status == "OPTIMAL"
    assert automatic.income is not None and automatic.income > 0
    assert automatic.raw["commanderies"][commandery]["city_level"] < 5
    assert automatic.request.three_kingdoms.population == fixed.request.three_kingdoms.population
    assert (
        automatic.request.three_kingdoms.external_food == fixed.request.three_kingdoms.external_food
    )


def test_native_cancellation_on_first_candidate_keeps_validated_result_and_progress():
    cancellation, events = Cancellation(), []

    def progress(event):
        events.append(event)
        if isinstance(event, SearchStats) and event.objective is not None:
            cancellation.cancel()

    config = replace(default_config(GAME), seconds=5, workers=1, research="all")
    result = solve_case(config, progress, cancellation=cancellation)
    assert cancellation.requested
    assert result.solver.status in {"OPTIMAL", "FEASIBLE"}
    assert result.income is not None and result.buildings
    assert result.raw["cancellation"]["incumbent_retained"]
    food, order = result.metrics["food_surplus"], result.metrics["public_order"]
    assert food is not None and food >= 0
    assert order is not None and order >= 0
    assert result.solver.bound is not None and result.solver.bound >= result.income
    native = [
        event for event in events if isinstance(event, ModelStats) and event.stage == "solver"
    ]
    assert native[-1].constraints == result.solver.details["model_stats"]["constraints"]


def test_highs_progress_reports_only_its_actual_model_without_cp_sat_labels():
    events = []
    config = replace(default_config(GAME), algorithm="highs", seconds=5, workers=1)
    result = solve_case(config, events.append)
    assert result.solver.status == "OPTIMAL"
    models = [event for event in events if isinstance(event, ModelStats)]
    assert len(models) == 1
    assert models[0].label == "HiGHS solver input" and models[0].stage == "solver"
    stats = result.solver.details["model_stats"]
    assert (models[0].variables, models[0].constraints) == (
        stats["variables"],
        stats["constraints"],
    )
    assert [model.to_dict() for model in models] == result.raw["model_complexity"]
    assert not any(isinstance(event, SearchStats) for event in events)


def test_tui_snapshot_controls_and_resources_reach_shared_requests():
    async def exercise():
        app = OptimizerApp(runner_factory=QuickRunner)
        async with app.run_test(size=(100, 34)) as pilot:
            app.query_one("#game", Select).value = GAME
            await pilot.pause()
            assert app.query_one("#three-kingdoms-options").display
            assert not app.query_one("#run", Button).disabled
            assert app._config().three_kingdoms.population == 1000000
            assert app._config().three_kingdoms.city_level is None
            app.query_one("#three-kingdoms-city_level", Select).value = "4"
            await pilot.pause()
            assert app._config().three_kingdoms.city_level == 4
            app.query_one("#three-kingdoms-city_level", Select).value = "auto"
            app.query_one("#three-kingdoms-population", Input).value = "500000"
            app.query_one("#three-kingdoms-capital", Select).value = YINGCHUAN
            app.query_one("#three-kingdoms-resources", SelectionList).select(COPPER)
            app.query_one("#research", Select).value = "all"
            app.query_one("#three-kingdoms-leader-effects", Checkbox).value = False
            await pilot.pause()
            await pilot.press("ctrl+r")
            await app.workers.wait_for_complete()
            saved = app.results[0]["request"]
            assert saved["three_kingdoms"]["population"] == 500000
            assert saved["three_kingdoms"]["city_level"] is None
            assert saved["three_kingdoms"]["capital_commandery"] == YINGCHUAN
            assert saved["three_kingdoms"]["external_resources"] == [COPPER]
            assert saved["three_kingdoms"]["include_leader_effects"] is False
            assert saved["research"] == "all" and saved["workers"] is None
            assert not app.query_one("#time-limit", Checkbox).value
            app.query_one("#three-kingdoms-population", Input).value = "-1"
            await pilot.pause()
            assert app.query_one("#run", Button).disabled
            app.query_one("#game", Select).value = "rome2"
            await pilot.pause()
            assert not app.query_one("#three-kingdoms-options").display
            assert "three_kingdoms" not in app._config().to_dict()

    asyncio.run(exercise())
