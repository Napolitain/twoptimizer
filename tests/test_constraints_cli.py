"""Optional CLI constraints survive shared requests, reports and resume boundaries."""

import csv
import json
from argparse import ArgumentParser

import pytest

from games.tw import benchmark as attila_cli
from games.tw.rome2 import benchmark as rome_cli
from games.tw.shogun2 import benchmark as shogun_cli
from twoptimizer.cli_constraints import (
    add_constraint_options,
    constraint_metadata,
    read_constraints,
)
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.requests import make_jobs


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_constraint_flags_default_to_the_existing_unrestricted_request(game):
    parser = ArgumentParser()
    add_constraint_options(parser, game)
    args = parser.parse_args([])
    assert read_constraints(args, game) == ConstraintOptions()
    assert constraint_metadata(args, game) == {}


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_repeated_building_flags_preserve_every_requirement(game):
    parser = ArgumentParser()
    add_constraint_options(parser, game)
    args = parser.parse_args(
        [
            "--require-building",
            "first",
            "--require-building",
            "second",
            "--forbid-building",
            "third",
        ]
    )
    options = read_constraints(args, game)
    assert options.required_buildings == ("first", "second")
    assert options.forbidden_buildings == ("third",)
    assert constraint_metadata(args, game)["constraints"] == options.to_dict()


@pytest.mark.parametrize(
    "flags, message",
    [
        (["--require-building", "same", "--forbid-building", "same"], "both required"),
        (["--require-building", "same", "--require-building", "same"], "only once"),
        (["--minimum-religious-influence", "nan"], "finite"),
        (["--minimum-religious-influence", "-1"], "nonnegative"),
    ],
)
def test_invalid_cli_constraints_are_not_silently_ignored(flags, message):
    args = attila_cli._parser().parse_args(flags)
    with pytest.raises(ValueError, match=message):
        attila_cli.request_from_args(args)


def test_attila_cli_keeps_state_faith_and_optional_target_separate():
    args = attila_cli._parser().parse_args(
        [
            "--province",
            "Thracia",
            "--fertility",
            "5",
            "--religion",
            "CHRIST_EAST",
            "--minimum-religious-influence",
            "4",
            "--require-building",
            "att_bld_eos_religion_east_church_major_1",
        ]
    )
    jobs, skipped = make_jobs(attila_cli.request_from_args(args))
    assert len(jobs) == 1 and not skipped
    assert jobs[0].religion == "CHRIST_EAST"
    assert jobs[0].constraints.minimum_religious_influence == 4
    assert jobs[0].constraints.required_buildings == ("att_bld_eos_religion_east_church_major_1",)


def test_rome_forced_building_is_saved_and_resume_cannot_drop_it(tmp_path):
    building = "rome_religious_jupiter_2"
    flags = [
        "--faction",
        "rom_rome",
        "--layout",
        "coastal",
        "--algorithm",
        "cp-sat",
        "--workers",
        "1",
        "--seconds",
        "0.01",
        "--output",
        str(tmp_path / "rome"),
    ]
    report = rome_cli.main([*flags, "--require-building", building])
    assert report["constraints"] == {"required_buildings": [building]}
    case = report["cases"][0]
    assert tuple(case["scenario"]["required_buildings"]) == (building,)
    assert json.loads(case["case_key"])[0]["required_buildings"] == [building]
    assert json.loads((tmp_path / "rome.json").read_text()) == report
    with (tmp_path / "rome.csv").open() as stream:
        assert json.loads(next(csv.DictReader(stream))["constraints"]) == report["constraints"]
    resumed = rome_cli.main([*flags, "--require-building", building, "--resume", "--fill-missing"])
    assert resumed["cases"] == report["cases"]
    with pytest.raises(ValueError, match="Cannot change optional constraints"):
        rome_cli.main([*flags, "--resume"])
    with pytest.raises(ValueError, match="Cannot change optional constraints"):
        rome_cli.main([*flags, "--forbid-building", building, "--resume"])


def test_shogun_religion_contact_and_required_building_reach_the_solver_and_report(tmp_path):
    building = "sho_christian_1_chapel"
    report = shogun_cli.main(
        [
            "--clan",
            "oda",
            "--province",
            "jap_owari",
            "--soil",
            "native",
            "--religion",
            "christian",
            "--nanban-contact",
            "--require-building",
            building,
            "--forbid-building",
            "sho_christian_2_hospital",
            "--workers",
            "1",
            "--seconds",
            "5",
            "--output",
            str(tmp_path / "shogun"),
        ]
    )
    assert report["constraints"] == {
        "required_buildings": [building],
        "forbidden_buildings": ["sho_christian_2_hospital"],
        "shogun_religion": "christian",
        "nanban_contact": True,
    }
    case = report["cases"][0]
    assert case["scenario"]["religion"] == "christian"
    assert case["scenario"]["nanban_contact"] is True
    assert tuple(case["scenario"]["required_buildings"]) == (building,)
    assert case["solver"]["status"] == "OPTIMAL"
    assert building in case["provinces"]["jap_owari"]["buildings"]
    assert "sho_christian_2_hospital" not in case["provinces"]["jap_owari"]["buildings"]
    with (tmp_path / "shogun.csv").open() as stream:
        row = next(csv.DictReader(stream))
        assert row["religion"] == "christian"
        assert json.loads(row["constraints"]) == report["constraints"]
    saved = json.loads((tmp_path / "shogun.json").read_text())
    assert saved == json.loads(json.dumps(report))
    assert saved["cases"][0]["scenario"]["required_buildings"] == [building]


def test_shogun_all_clans_reports_religious_exclusions(tmp_path, capsys):
    report = shogun_cli.main(
        [
            "--province",
            "jap_owari",
            "--soil",
            "native",
            "--religion",
            "christian",
            "--workers",
            "1",
            "--seconds",
            "0.01",
            "--output",
            str(tmp_path / "clans"),
        ]
    )
    assert len(report["cases"]) == 11
    assert all(case["scenario"]["clan"] != "ikko_ikki" for case in report["cases"])
    assert len(report["skipped"]) == 1
    reason = report["skipped"][0]
    assert "Ikko" in reason and "incompatible with christian religion" in reason
    assert f"Skipped: {reason}" in capsys.readouterr().out
    assert json.loads((tmp_path / "clans.json").read_text())["skipped"] == [reason]
