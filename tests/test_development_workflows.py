"""Exercise documented commands against bundled data and real solver backends."""

import csv
import json
from importlib import import_module

import pytest

from games.tw.rome2 import benchmark as rome_benchmark
from games.tw.rome2 import summarize, verify
from games.tw.shogun2 import benchmark as shogun_benchmark


@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("games.hoi4.example_usage", "Germany"),
        ("games.hoi4.enhanced_state_demo", "Industrial Heartland"),
        ("games.hoi4.optimization_demo", "OPTIMAL"),
    ],
)
def test_documented_hoi4_examples(module, expected, capsys):
    import_module(module).main()
    assert expected.lower() in capsys.readouterr().out.lower()


def test_shogun_benchmark_agrees_across_backends(tmp_path, capsys):
    output = tmp_path / "shogun"
    shogun_benchmark.main(
        [
            "--clan",
            "oda",
            "--soil",
            "native",
            "--workers",
            "1",
            "--seconds",
            "5",
            "--algorithm",
            "cp-sat",
            "--algorithm",
            "cbc",
            "--algorithm",
            "scip",
            "--output",
            str(output),
        ]
    )
    report = json.loads(output.with_suffix(".json").read_text())
    cases = report["cases"]
    assert len(cases) == 3
    for case in cases:
        assert case["solver"]["status"] == "OPTIMAL"
        assert case["domestic_tax_income"] == pytest.approx(7688.06)
    assert "OPTIMAL" in capsys.readouterr().out
    with output.with_suffix(".csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 1
    assert rows[0]["clan"] == "Oda"
    assert float(rows[0]["domestic_tax_income"]) == pytest.approx(7688.06)


def test_rome_benchmark_resume_verify_and_rank(tmp_path, capsys):
    output = tmp_path / "rome"
    argv = [
        "--faction",
        "rom_rome",
        "--layout",
        "coastal",
        "--algorithm",
        "cp-sat",
        "--seconds",
        "10",
        "--workers",
        "1",
        "--output",
        str(output),
    ]
    rome_benchmark.main(argv)
    path = output.with_suffix(".json")
    first = json.loads(path.read_text())
    assert len(first["cases"]) == 1
    case = first["cases"][0]
    assert case["solver"]["status"] in {"OPTIMAL", "FEASIBLE"}
    assert case["domestic_net_income"] > 0
    assert verify.verify([path])["verified_feasible_layouts"] == 1
    ranks = summarize.summarize([path])
    assert ranks["rows"][0]["rank_min"] == ranks["rows"][0]["rank_max"] == 1
    rome_benchmark.main([*argv, "--resume", "--fill-missing"])
    assert json.loads(path.read_text())["cases"] == first["cases"]
    assert "rom_rome" in json.dumps(first)
    assert capsys.readouterr().out


@pytest.mark.parametrize(
    "argv", [["--fill-missing"], ["--resume", "--fill-missing", "--all-technologies"]]
)
def test_rome_requires_consistent_resume_options(argv, tmp_path):
    if "--resume" in argv:
        # An absent prior output is valid; invalid faction IDs must be rejected.
        argv = [*argv, "--faction", "missing", "--output", str(tmp_path / "missing")]
        with pytest.raises((ValueError, KeyError)):
            rome_benchmark.main(argv)
    else:
        with pytest.raises(SystemExit) as error:
            rome_benchmark.main(argv)
        assert error.value.code == 2


@pytest.fixture
def preserve_game_state(monkeypatch):
    from games.tw.games import Games

    for name in ("instance", "problem", "buildings", "legacy_effects", "fertility", "USE_NAME"):
        monkeypatch.setattr(Games, name, getattr(Games, name))


def test_attila_benchmark_json_and_input_errors(tmp_path, preserve_game_state):
    from games.tw import benchmark

    output = tmp_path / "attila.json"
    args = [
        "--province",
        "Thracia",
        "--fertility",
        "5",
        "--objective",
        "legacy",
        "--seconds",
        "5",
        "--workers",
        "1",
        "--output",
        str(output),
    ]
    report = benchmark.main(args)
    case = report["cases"][0]
    assert case["results"][0]["status"] == "OPTIMAL"
    assert case["results"][0]["objective"] > 0
    assert json.loads(output.read_text()) == report
    with pytest.raises(SystemExit):
        benchmark.main([*args, "--province", "missing"])
    with pytest.raises(SystemExit):
        benchmark.main([*args, "--region-fertility", "bad=-1"])


def test_attila_faction_comparison_resumes_a_validated_proof(
    tmp_path, monkeypatch, preserve_game_state
):
    from games.tw import faction_comparison
    from games.tw.models.game_attila import AttilaGame

    monkeypatch.setattr(
        faction_comparison,
        "native_factions",
        lambda: [AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE],
    )
    output = tmp_path / "factions.json"
    args = ["--province", "Thracia", "--seconds", "10", "--workers", "1", "--output", str(output)]
    first = faction_comparison.main(args)
    case = first["factions"][0]["cases"][0]
    assert case["status"] == "OPTIMAL"
    assert case["income"] > 0
    assert first["source_sha256"]
    second = faction_comparison.main([*args, "--resume"])
    restored = second["factions"][0]["cases"][0]
    assert restored["income"] == case["income"]
    assert restored["signature"] == case["signature"]
    assert restored["status"] == "OPTIMAL"
    assert output.with_suffix(".csv").read_text().count("OPTIMAL") == 1


def test_rome_source_audit_offline_retains_mismatches(tmp_path):
    from games.tw.rome2 import audit_sources

    output = tmp_path / "audit.json"
    report = audit_sources.main(["--offline", "--output", str(output)])
    assert report["building_checks"]
    assert json.loads(output.read_text()) == report
    assert audit_sources.observation("+3 food (all regions)") == ("food", (), 3)
    assert audit_sources.observation("+2 public order per turn (sanitation)") == ("order", (), 2)
    assert audit_sources.observation("Edict: +3 food") is None
    assert audit_sources.observation("unmodeled military effect") is None


def test_attila_ci_entry_point_works_outside_checkout(
    tmp_path, monkeypatch, capsys, preserve_game_state
):
    import runpy

    monkeypatch.chdir(tmp_path)
    runpy.run_module("games.tw.attila.main", run_name="__main__")
    assert "Total solving time:" in capsys.readouterr().out
    assert (tmp_path / "attila_problem.lp").stat().st_size > 1000
