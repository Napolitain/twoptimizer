"""CLI compatibility reports use the same scenarios and results as the application."""

import csv
import json
from dataclasses import replace

import pytest

from games.tw.rome2 import benchmark as rome_cli
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from games.tw.shogun2 import benchmark as shogun_cli
from twoptimizer.adapters.rome2 import prepare_scenario, request_key
from twoptimizer.models import RunConfig
from twoptimizer.rome_session import RomeSession, _merge_incumbent
from twoptimizer.service import make_jobs, solve_case


def test_rome_cli_and_terminal_request_share_economics_and_native_report(tmp_path):
    config = RunConfig(algorithm="cp-sat", workers=1)
    result = solve_case(config)
    report = rome_cli.main(
        [
            "--faction",
            "rom_rome",
            "--layout",
            "coastal",
            "--algorithm",
            "cp-sat",
            "--workers",
            "1",
            "--output",
            str(tmp_path / "rome"),
        ]
    )
    case = report["cases"][0]
    assert case["scenario"] == result.raw["scenario"]
    assert case["solver"]["status"] == result.solver.status == "OPTIMAL"
    assert case["domestic_net_income"] == pytest.approx(result.income)
    assert case["solver"]["bound"] == pytest.approx(result.solver.bound)
    assert case["food_surplus"] == pytest.approx(result.metrics["food_surplus"])
    assert case["case_key"] == request_key(config)
    assert json.loads((tmp_path / "rome.json").read_text()) == report
    with (tmp_path / "rome.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert set(rows[0]) == {
        "layout",
        "faction",
        "algorithm",
        "status",
        "income",
        "upper_bound",
        "food",
        "public_order",
        "seconds",
    }
    assert float(rows[0]["income"]) == pytest.approx(result.income)


def test_shogun_cli_and_terminal_request_share_economics(tmp_path):
    config = RunConfig(
        game="shogun2",
        faction="oda",
        province="jap_owari",
        algorithm="cp-sat",
        research="all",
        workers=1,
        town_wealth=100,
        tax=35,
    )
    result = solve_case(config)
    report = shogun_cli.main(
        [
            "--clan",
            "oda",
            "--province",
            "jap_owari",
            "--soil",
            "native",
            "--workers",
            "1",
            "--town-wealth",
            "100",
            "--tax",
            "35",
            "--output",
            str(tmp_path / "shogun"),
        ]
    )
    case = report["cases"][0]
    assert case["scenario"] == result.raw["scenario"]
    assert case["solver"]["status"] == result.solver.status == "OPTIMAL"
    assert case["domestic_tax_income"] == pytest.approx(result.income)
    assert case["solver"]["bound"] == pytest.approx(result.solver.bound)
    assert case["food_surplus"] == pytest.approx(result.metrics["food_surplus"])
    assert json.loads((tmp_path / "shogun.json").read_text()) == json.loads(json.dumps(report))


def test_named_rome_province_preserves_modifiers_and_report_label(tmp_path):
    report = rome_cli.main(
        [
            "--faction",
            "rom_rome",
            "--province",
            "Italia",
            "--algorithm",
            "cp-sat",
            "--workers",
            "1",
            "--output",
            str(tmp_path / "italia"),
        ]
    )
    case = report["cases"][0]
    scenario = prepare_scenario(RunConfig(province="Italia", algorithm="cp-sat"))
    assert case["layout"] == "Italia"
    assert case["scenario"] == scenario.to_dict()
    assert case["scenario"]["modifiers"]
    assert case["solver"]["status"] == "OPTIMAL"
    assert json.loads((tmp_path / "italia.json").read_text()) == report
    resumed = rome_cli.main(
        [
            "--faction",
            "rom_rome",
            "--province",
            "Italia",
            "--algorithm",
            "cp-sat",
            "--workers",
            "1",
            "--resume",
            "--output",
            str(tmp_path / "italia"),
        ]
    )
    assert resumed["cases"] == report["cases"]


@pytest.mark.parametrize(
    ("cli", "args", "config"),
    [
        (rome_cli, ["--seconds", "nan"], RunConfig(seconds=float("nan"))),
        (rome_cli, ["--workers", "0"], RunConfig(workers=0)),
        (
            shogun_cli,
            ["--town-wealth", "-1"],
            RunConfig(
                game="shogun2",
                faction="oda",
                province="jap_owari",
                algorithm="cp-sat",
                research="all",
                town_wealth=-1,
            ),
        ),
    ],
)
def test_cli_and_application_reject_same_invalid_inputs(cli, args, config, tmp_path):
    with pytest.raises(ValueError) as application:
        make_jobs(config)
    with pytest.raises(ValueError) as command:
        cli.main([*args, "--output", str(tmp_path / "invalid")])
    assert str(command.value) == str(application.value)
    assert not (tmp_path / "invalid.json").exists()


def test_rome_session_keeps_best_incumbent_and_strongest_bound_without_mutation():
    old = {"domestic_net_income": 12, "solver": {"bound": 20, "status": "FEASIBLE"}}
    new = {"domestic_net_income": 10, "solver": {"bound": 15, "status": "FEASIBLE"}}
    merged = _merge_incumbent(old, new)
    assert merged["domestic_net_income"] == 12
    assert merged["solver"]["bound"] == 15
    assert old["solver"]["bound"] == 20
    assert new["domestic_net_income"] == 10


@pytest.mark.parametrize("previous_feasible", [False, True])
def test_rome_session_retains_negative_feasible_income_when_other_run_is_unknown(previous_feasible):
    feasible = {
        "domestic_net_income": -5,
        "solver": {"bound": 0, "status": "FEASIBLE"},
    }
    unknown = {"solver": {"bound": -2, "status": "UNKNOWN"}}
    old, new = (feasible, unknown) if previous_feasible else (unknown, feasible)
    merged = _merge_incumbent(old, new)
    assert merged["domestic_net_income"] == -5
    assert merged["solver"] == {"bound": -2, "status": "FEASIBLE"}
    assert feasible["solver"]["bound"] == 0


@pytest.mark.parametrize("bound", [None, float("inf"), float("nan")])
def test_rome_session_without_feasible_solution_retains_only_finite_bounds(bound):
    old = {"solver": {"bound": bound, "status": "UNKNOWN"}}
    new = {"solver": {"bound": -3, "status": "UNKNOWN"}}
    merged = _merge_incumbent(old, new)
    assert "domestic_net_income" not in merged
    assert merged["solver"] == {"bound": -3, "status": "UNKNOWN"}
    assert _merge_incumbent(None, old)["solver"]["bound"] is None


def test_rome_session_rejects_bound_below_retained_feasible_income():
    old = {"domestic_net_income": 12, "solver": {"bound": 20, "status": "FEASIBLE"}}
    new = {"domestic_net_income": 10, "solver": {"bound": 11, "status": "FEASIBLE"}}
    with pytest.raises(RuntimeError, match="upper bound is below"):
        _merge_incumbent(old, new)
    assert old["solver"]["bound"] == 20


def test_rome_session_retains_negative_optimal_status_and_bound():
    optimal = {"domestic_net_income": -5, "solver": {"bound": -5, "status": "OPTIMAL"}}
    unknown = {"solver": {"bound": 0, "status": "UNKNOWN"}}
    assert _merge_incumbent(optimal, unknown) == optimal


def test_rome_session_resume_selection_distinguishes_incumbents_and_proofs():
    config = RunConfig(algorithm="cp-sat")
    key = request_key(config)
    previous = {key: {"solver": {"status": "FEASIBLE"}}}
    session = RomeSession(previous)
    assert not session.should_skip(config)
    assert session.should_skip(config, fill_missing=True)
    assert not session.should_skip(replace(config, province="inland"), fill_missing=True)
    session.cases[key]["solver"]["status"] = "OPTIMAL"
    assert session.should_skip(config)
    assert previous[key]["solver"]["status"] == "FEASIBLE"


def test_rome_session_reuses_only_portable_proofs_and_supplies_validated_hints(tiny, monkeypatch):
    scenario = Scenario("rom_rome", (Site("capital", major=True),))
    config = RunConfig(algorithm="cp-sat", workers=1)
    session = RomeSession()
    first = session.solve(Economy(scenario, tiny), config)
    assert first["solver"]["status"] == "OPTIMAL"
    assert first["proof_fingerprint"]
    repeated = Economy(scenario, tiny)

    def unexpected_search(*args, **kwargs):
        pytest.fail("An identical portable optimality proof should be independently replayed")

    monkeypatch.setattr(repeated, "optimize", unexpected_search)
    reused = session.solve(repeated, config)
    assert reused["domestic_net_income"] == first["domestic_net_income"]
    assert reused["solver"]["proof_reused_from"] == "rom_rome"
    assert reused["solver"]["seconds"] == 0

    nonlinear = Economy(scenario, tiny)
    optimize = nonlinear.optimize
    hints = []

    def capture_hint(algorithm, seconds, workers, incumbent=None):
        hints.append(incumbent)
        return optimize(algorithm, seconds, workers, incumbent=incumbent)

    monkeypatch.setattr(nonlinear, "optimize", capture_hint)
    checked = session.solve(nonlinear, replace(config, algorithm="scip-nonlinear"))
    assert hints and hints[0]["domestic_net_income"] == first["domestic_net_income"]
    assert checked["solver"]["status"] == "OPTIMAL"
    assert checked["domestic_net_income"] == first["domestic_net_income"]


def test_disabled_rome_research_preserves_explicit_profile():
    config = RunConfig(research="none", technology_profile="archived")
    scenario = prepare_scenario(config)
    assert scenario.technology_profile == "archived"
    assert not scenario.all_technologies
    assert json.loads(request_key(config))[0] == scenario.to_dict()
