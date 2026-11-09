"""Owned holdings preserve regional eligibility, uniqueness and honest scope reports."""

import csv
from collections import Counter
from dataclasses import asdict
from types import SimpleNamespace

import pytest

from games.tw.shogun2 import benchmark
from games.tw.shogun2.catalog import load_data
from games.tw.shogun2.effects import Effect, parse, unique_key
from games.tw.shogun2.model import Economy
from games.tw.shogun2.scenario import Province, Scenario


def test_every_specialty_stays_in_its_native_provinces():
    catalog, rules = load_data()
    economy = Economy(Scenario("oda", tuple(Province(key) for key in rules["provinces"])))
    for key, location in rules["provinces"].items():
        specialties = {
            building
            for building in economy.candidates[key]
            if building.startswith("sho_region_specialty_")
        }
        expected = {
            building
            for building in catalog["buildings"]
            if location["specialty"] is not None
            and building.startswith(f"sho_region_specialty_{location['specialty']}_")
        }
        assert specialties == expected


@pytest.mark.parametrize(
    ("fact", "effect"),
    [
        (
            "Spreads Buddhism to neighbouring provinces (+5 religious zeal)",
            Effect("adjacent_religious_zeal", 5, "buddhist"),
        ),
        (
            "Spreads Christianity to neighbouring provinces (+6 religious zeal)",
            Effect("adjacent_religious_zeal", 6, "christian"),
        ),
        (
            "Spreads radical Ikko beliefs to neighbouring provinces (+8 religious zeal)",
            Effect("adjacent_religious_zeal", 8, "ikko"),
        ),
    ],
)
def test_adjacency_facts_are_recognized_as_conversion_not_income(fact, effect):
    assert parse(fact) == effect
    catalog, _ = load_data()
    coverage = benchmark.coverage(catalog)
    rows = [row for row in coverage["recognized"] if row["kind"] == effect.kind]
    assert len(rows) == 15
    assert fact in {row["fact"] for row in rows}
    assert "outside the static income" in coverage["effect_disposition"][effect.kind]


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_independent_optima_cannot_be_summed_into_one_legal_holding(algorithm):
    catalog, _ = load_data()
    provinces = (Province("jap_sado"), Province("jap_owari"))
    separate = [
        Economy(Scenario("oda", (province,))).optimize(algorithm, workers=1)
        for province in provinces
    ]
    together = Economy(Scenario("oda", provinces)).optimize(algorithm, workers=1)
    assert all(report["solver"]["status"] == "OPTIMAL" for report in [*separate, together])
    assert (
        sum(report["domestic_tax_income"] for report in separate) > together["domestic_tax_income"]
    )
    joint_counts = Counter(
        unique_key(catalog["buildings"][key])
        for province in together["provinces"].values()
        for key in province["buildings"]
        if unique_key(catalog["buildings"][key]) is not None
    )
    assert joint_counts
    assert max(joint_counts.values()) == 1
    with pytest.raises(ValueError, match=r"Unique building duplicated|Faction food deficit"):
        Economy(Scenario("oda", provinces)).evaluate(
            {
                key: row["buildings"]
                for report in separate
                for key, row in report["provinces"].items()
            }
        )


def test_regional_tax_bonus_does_not_spread_but_arts_do():
    economy = Economy(Scenario("oda", (Province("jap_sado"), Province("jap_settsu"))))
    common = [
        "sho_castle_1_fort",
        "sho_farming_4_consolidation",
        "sho_infrastructure_0_trails",
        "sho_port_0_coastal_village",
    ]
    report = economy.evaluate(
        {
            "jap_sado": [*common, "sho_region_specialty_gold_mining_1_surface_mining"],
            "jap_settsu": [*common, "sho_region_specialty_intellectual_centre_3_law_cou"],
        }
    )
    sado, settsu = (report["provinces"][key] for key in ("jap_sado", "jap_settsu"))
    assert sado["effective_tax_percent"] == 38
    assert settsu["effective_tax_percent"] == 48
    assert sado["farm_wealth"] == 969
    assert settsu["farm_wealth"] == 1453.5
    assert report["food_surplus"] == 7
    assert report["domestic_tax_income"] == pytest.approx((969 + 600) * 0.38 + 1453.5 * 0.48)


def test_independent_cli_keeps_every_province_in_json_and_csv(tmp_path):
    output = tmp_path / "independent"
    payload = benchmark.main(
        [
            "--independent",
            "--clan",
            "oda",
            "--province",
            "jap_sado",
            "--province",
            "jap_owari",
            "--soil",
            "native",
            "--algorithm",
            "cp-sat",
            "--algorithm",
            "highs",
            "--workers",
            "1",
            "--output",
            str(output),
        ]
    )
    assert len(payload["cases"]) == 4
    assert all(len(case["provinces"]) == 1 for case in payload["cases"])
    assert "separate hypothetical holding" in payload["assumptions"]["ownership"]
    with output.with_suffix(".csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 2
    assert {row["provinces"] for row in rows} == {"jap_sado", "jap_owari"}
    for row in rows:
        own, other = (
            ("jap_sado", "jap_owari")
            if row["provinces"] == "jap_sado"
            else (
                "jap_owari",
                "jap_sado",
            )
        )
        assert row["ownership"] == "independent"
        assert float(row[own]) == pytest.approx(float(row["domestic_tax_income"]))
        assert row[other] == ""


@pytest.mark.parametrize(("mode", "expected"), [("--joint", 1), ("--independent", 65)])
def test_all_provinces_cli_expands_and_labels_actual_holdings(
    monkeypatch, tmp_path, mode, expected
):
    requests = []

    def solve(config, *, session):
        requests.append(config)
        return SimpleNamespace(
            raw={
                "scenario": asdict(
                    Scenario("oda", tuple(Province(key) for key in config.holdings))
                ),
                "provinces": {key: {"tax_income": 1} for key in config.holdings},
            },
            faction="Oda",
            solver=SimpleNamespace(status="OPTIMAL", seconds=0),
            income=len(config.holdings),
            metrics={},
        )

    monkeypatch.setattr(benchmark.service, "solve_case", solve)
    output = tmp_path / "all"
    payload = benchmark.main(
        [mode, "--province", "all", "--clan", "oda", "--soil", "native", "--output", str(output)]
    )
    assert len(requests) == len(payload["cases"]) == expected
    assert len({key for config in requests for key in config.holdings}) == 65
    with output.with_suffix(".csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == expected
    assert "all" not in rows[0]
    assert "jap_sado" in rows[0]
    assert {row["ownership"] for row in rows} == {mode.removeprefix("--")}


def test_cli_ownership_options_are_mutually_exclusive():
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--joint", "--independent"])
    assert error.value.code == 2
