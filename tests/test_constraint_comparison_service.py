"""Comparison orchestration preserves inputs, results, cancellation and exports."""

import csv
import json
from dataclasses import replace

import pytest

from games.tw import benchmark as attila_cli
from games.tw.shogun2 import benchmark as shogun_cli
from twoptimizer.adapters.rome2 import request_key
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.export import export_session
from twoptimizer.models import BuildingSelection, EngineResult, RunConfig
from twoptimizer.progress import ModelStats
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.rome_session import RomeSession
from twoptimizer.service import solve_case


def install_adapter(monkeypatch, game, *, failing=None):
    calls = []

    def adapter(config, phase, session):
        required = bool(config.constraints.required_buildings)
        calls.append(config)
        if failing == ("constrained" if required else "baseline"):
            raise ValueError("Unavailable test building")
        phase("build_model_seconds", "Building")
        phase.record_model(ModelStats("Test input", 4, 3))
        phase("solve_and_check_seconds", "Solving")
        income = 80 if required else 100
        return EngineResult(
            {
                "solver": {
                    "algorithm": config.algorithm,
                    "status": "OPTIMAL",
                    "seconds": 0.01,
                    "objective": income,
                    "bound": income,
                }
            },
            income,
            [
                BuildingSelection(
                    "Capital",
                    "Temple" if required else "Market",
                    "temple" if required else "market",
                )
            ],
            {},
        )

    name = {"rome2": "rome", "shogun2": "shogun", "attila": "attila"}[game]
    monkeypatch.setattr(f"twoptimizer.service.solve_{name}", adapter)
    return calls


@pytest.mark.parametrize("game", ["rome2", "attila", "shogun2"])
def test_comparison_runs_both_scenarios_and_preserves_original_request(monkeypatch, game):
    calls = install_adapter(monkeypatch, game)
    config = replace(
        default_config(game),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("temple",)),
    )
    events = []
    result = solve_case(config, events.append)
    summary = result.raw["constraint_comparison"]
    assert len(calls) == 2 and all(not config.compare_constraints for config in calls)
    assert calls[0].constraints.required_buildings == ("temple",)
    assert calls[1].constraints.required_buildings == ()
    assert result.request.compare_constraints and result.income == 80
    assert summary["status"] == "exact" and summary["exact_cost"] == 20
    assert summary["baseline"]["income"] == 100
    assert summary["added_buildings"][0]["id"] == "temple"
    assert summary["removed_buildings"][0]["id"] == "market"
    assert len(result.raw["model_complexity"]) == 2
    assert any(str(event).startswith("Without requirements:") for event in events)
    assert any(str(event).startswith("With requirements:") for event in events)
    assert result.timings["build_model_seconds"] == pytest.approx(
        summary["baseline"]["timings"]["build_model_seconds"]
        + summary["constrained_timings"]["build_model_seconds"]
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_no_requirements_never_triggers_an_extra_solve(monkeypatch, enabled):
    calls = install_adapter(monkeypatch, "shogun2")
    config = replace(
        default_config("shogun2"),
        compare_constraints=enabled,
        constraints=ConstraintOptions(shogun_religion="christian", nanban_contact=True),
    )
    result = solve_case(config)
    assert len(calls) == 1 and calls[0].constraints == config.constraints
    if enabled:
        assert result.raw["constraint_comparison"]["status"] == "unavailable"
    else:
        assert "constraint_comparison" not in result.raw


def test_failed_baseline_does_not_discard_a_valid_constrained_result(monkeypatch):
    install_adapter(monkeypatch, "shogun2", failing="baseline")
    config = replace(
        default_config("shogun2"),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("temple",)),
    )
    result = solve_case(config)
    assert result.income == 80 and result.solver.status == "OPTIMAL"
    summary = result.raw["constraint_comparison"]
    assert summary["status"] == "unavailable" and summary["exact_cost"] is None
    assert summary["baseline"]["solver"]["status"] == "ERROR"


def test_constrained_validation_error_keeps_existing_error_contract(monkeypatch):
    install_adapter(monkeypatch, "shogun2", failing="constrained")
    config = replace(
        default_config("shogun2"),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("temple",)),
    )
    with pytest.raises(ValueError, match="Unavailable test building"):
        solve_case(config)


def test_worker_flags_are_optional_typed_and_preserve_retained_candidates():
    assert "compare_constraints" not in RunConfig().to_dict()
    config = RunConfig(compare_constraints=True, comparison_candidates=("temple",))
    assert RunConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config
    with pytest.raises(ValueError, match="boolean"):
        make_jobs(replace(config, compare_constraints="yes"))
    with pytest.raises(ValueError, match="Rome II"):
        make_jobs(replace(default_config("shogun2"), comparison_candidates=("temple",)))


def test_shared_export_records_cost_status_bounds_and_baseline(monkeypatch, tmp_path):
    install_adapter(monkeypatch, "shogun2")
    config = replace(
        default_config("shogun2"),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("temple",)),
    )
    result = solve_case(config).to_dict()
    path, csv_path = export_session(tmp_path / "comparison.json", [result])
    saved = json.loads(path.read_text())["cases"][0]
    assert saved["raw"]["constraint_comparison"]["baseline"]["income"] == 100
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["comparison_status"] == "exact"
    assert row["baseline_income"] == "100.0"
    assert (
        row["constraint_cost"]
        == row["constraint_cost_lower"]
        == row["constraint_cost_upper"]
        == "20.0"
    )


def test_rome_resume_does_not_skip_an_unproved_comparison():
    config = replace(
        default_config("rome2"),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("rome_religious_jupiter_2",)),
    )
    previous = {"solver": {"status": "OPTIMAL"}, "constraint_comparison": {"status": "bounded"}}
    session = RomeSession({request_key(config): previous})
    assert not session.should_skip(config)
    assert session.should_skip(config, fill_missing=True)
    session.cases[request_key(config)]["constraint_comparison"]["status"] = "exact"
    assert session.should_skip(config)


def test_attilla_cli_flag_reaches_shared_request():
    args = attila_cli._parser().parse_args(
        ["--compare-constraints", "--require-building", "temple"]
    )
    request = attila_cli.request_from_args(args)
    assert request.config.compare_constraints


def test_shogun_cli_saves_and_prints_comparison_with_adapter_double(monkeypatch, tmp_path, capsys):
    install_adapter(monkeypatch, "shogun2")
    report = shogun_cli.main(
        [
            "--clan",
            "oda",
            "--province",
            "jap_owari",
            "--soil",
            "native",
            "--require-building",
            "temple",
            "--compare-constraints",
            "--output",
            str(tmp_path / "comparison"),
        ]
    )
    assert (
        report["compare_constraints"]
        and report["cases"][0]["constraint_comparison"]["exact_cost"] == 20
    )
    assert "Proven income cost" in capsys.readouterr().out
    with (tmp_path / "comparison.csv").open(newline="") as stream:
        assert next(csv.DictReader(stream))["constraint_cost"] == "20.0"
