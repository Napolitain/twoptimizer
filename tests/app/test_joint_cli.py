"""Ownership and explicit border inputs survive CLI report and worker boundaries."""

import json
from argparse import ArgumentParser

import pytest

from games.tw.attila import benchmark as attila_cli
from games.tw.rome2 import benchmark as rome_cli
from twoptimizer.cli_holdings import add_holding_options, read_borders
from twoptimizer.errors import ApplicationError
from twoptimizer.holdings import resolved_borders
from twoptimizer.models import RunConfig
from twoptimizer.requests import make_jobs, province_id


def test_cli_border_file_resolves_names_and_preserves_two_way_pairs(tmp_path):
    parser = ArgumentParser()
    add_holding_options(parser)
    path = tmp_path / "borders.json"
    path.write_text(json.dumps([["Italia", "Magna Graecia"]]))
    args = parser.parse_args(["--joint", "--borders", str(path)])
    assert args.joint
    expected = ((province_id("rome2", "Italia"), province_id("rome2", "Magna Graecia")),)
    assert read_borders(args, "rome2") == expected
    assert read_borders(parser.parse_args(["--joint", "--no-borders"]), "rome2") == ()
    assert read_borders(parser.parse_args([]), "rome2") is None
    assert not parser.parse_args(["--independent"]).joint


@pytest.mark.parametrize("raw", [{}, ["Italia"], [["Italia"]], [["Italia", "Africa", "Asia"]]])
def test_cli_rejects_malformed_border_files(tmp_path, raw):
    parser = ArgumentParser()
    add_holding_options(parser)
    path = tmp_path / "borders.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="JSON list of province pairs"):
        read_borders(parser.parse_args(["--borders", str(path)]), "rome2")


def test_cli_border_read_errors_are_actionable(tmp_path):
    parser = ArgumentParser()
    add_holding_options(parser)
    path = tmp_path / "borders.json"
    args = parser.parse_args(["--borders", str(path)])
    with pytest.raises(ApplicationError, match="Cannot read border pairs"):
        read_borders(args, "rome2")
    path.write_text("{incomplete")
    with pytest.raises(ApplicationError, match="Cannot read border pairs"):
        read_borders(args, "rome2")


def test_attila_cli_does_not_silently_assume_missing_borders(monkeypatch):
    monkeypatch.setattr("twoptimizer.holdings.province_borders", lambda *args: None)
    args = attila_cli._parser().parse_args(
        ["--province", "Thracia", "--province", "Aegyptus", "--joint"]
    )
    with pytest.raises(ValueError, match="neighboring provinces"):
        make_jobs(attila_cli.request_from_args(args))


@pytest.mark.parametrize("neighbor, adjacent", [("Macedonia", True), ("Aegyptus", False)])
def test_attila_cli_uses_known_map_borders_without_manual_input(neighbor, adjacent):
    args = attila_cli._parser().parse_args(
        ["--province", "Thracia", "--province", neighbor, "--joint"]
    )
    jobs, skipped = make_jobs(attila_cli.request_from_args(args))
    assert jobs and not skipped
    expected = tuple(sorted(province_id("attila", name) for name in ("Thracia", neighbor)))
    for job in jobs:
        assert job.adjacency is None
        assert resolved_borders(job) == ((expected,) if adjacent else ())


@pytest.mark.parametrize("args", [["--joint"], ["--joint", "--layout", "coastal"]])
def test_rome_joint_cli_requires_named_provinces(args, tmp_path):
    with pytest.raises(SystemExit):
        rome_cli.main([*args, "--output", str(tmp_path / "invalid")])
    assert not (tmp_path / "invalid.json").exists()


def test_rome_joint_cli_writes_replayable_request_and_resume_metadata(tmp_path):
    from games.tw.rome2.holdings import HoldingScenario, joint_model_fingerprint

    args = [
        "--faction",
        "rom_rome",
        "--province",
        "Italia",
        "--province",
        "Magna Graecia",
        "--joint",
        "--no-borders",
        "--algorithm",
        "cp-sat",
        "--seconds",
        "0.01",
        "--workers",
        "1",
        "--output",
        str(tmp_path / "holding"),
    ]
    report = rome_cli.main(args)
    assert report["joint_model_sha256"] == joint_model_fingerprint()
    assert len(report["cases"]) == 1
    case = report["cases"][0]
    scenario = HoldingScenario.from_dict(case["scenario"])
    assert len(scenario.provinces) == 2
    assert scenario.adjacency == ()
    assert case["layout"] == scenario.name
    assert json.loads(case["case_key"])[0] == scenario.to_dict()
    assert "shared food" in report["assumptions"]["food"]
    assert json.loads((tmp_path / "holding.json").read_text()) == report
    resumed = rome_cli.main([*args, "--resume", "--fill-missing"])
    assert resumed["cases"] == report["cases"]
    with pytest.raises(ValueError, match="Cannot change joint/independent"):
        rome_cli.main(["--resume", "--independent", "--output", str(tmp_path / "holding")])
    report["joint_model_sha256"] = "stale"
    (tmp_path / "holding.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="different joint model code"):
        rome_cli.main([*args, "--resume"])


def test_all_rome_provinces_expand_both_ownership_modes():
    jobs, _ = make_jobs(RunConfig(provinces=("all",), algorithm="cp-sat"))
    assert len(jobs) == 57
    assert not any(job.province in {"coastal", "inland", "grain"} for job in jobs)
    joint, _ = make_jobs(
        RunConfig(provinces=("all",), algorithm="cp-sat", joint=True, adjacency=())
    )
    assert len(joint) == 1
    assert set(joint[0].holdings) == {job.province for job in jobs}
