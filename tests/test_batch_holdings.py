"""Batches, shared ownership, border effects and portable multi-province requests."""

import json
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from games.tw.attila.economy import Economy
from games.tw.region import Region
from tests.support.attila import building, province
from twoptimizer.catalog import choices
from twoptimizer.export import export_session
from twoptimizer.holdings import adjacency_mapping, province_label, selected_provinces
from twoptimizer.models import RunConfig
from twoptimizer.service import make_jobs, solve_case

SHOGUN = ("jap_sado", "jap_settsu", "jap_owari")
ATTILA = ("att_prov_thracia", "att_prov_macedonia")


@given(st.lists(st.sampled_from(SHOGUN), unique=True))
def test_independent_batch_is_the_complete_province_faction_solver_product(selected):
    config = RunConfig(
        game="shogun2",
        faction="all",
        research="all",
        algorithm="compare",
        provinces=tuple(selected),
    )
    jobs, skipped = make_jobs(config)
    expected = {
        (province, key, solver)
        for province in selected
        for _, key in choices("shogun2")["factions"]
        for solver in ("cp-sat", "cbc", "scip")
    }
    assert len(jobs) == len(expected)
    assert {(j.province, j.faction, j.algorithm) for j in jobs} == expected
    assert all(j.provinces is None and not j.joint for j in jobs)
    assert not skipped


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_all_listed_holdings_can_be_queued_without_starting_a_solver(game):
    options = choices(game)
    selected = tuple(key for _, key in options["provinces"])
    config = RunConfig(
        game=game,
        faction=options["default_faction"],
        research=options["default_research"],
        algorithm="cp-sat",
        provinces=selected,
    )
    jobs, _ = make_jobs(config)
    assert tuple(job.province for job in jobs) == selected


def test_zero_one_and_joint_holdings_have_distinct_meanings():
    config = RunConfig(
        game="shogun2", faction="oda", province=SHOGUN[0], research="all", algorithm="cp-sat"
    )
    assert selected_provinces(config) == (SHOGUN[0],)
    assert len(make_jobs(config)[0]) == 1
    assert make_jobs(replace(config, provinces=()))[0] == []
    jobs, _ = make_jobs(replace(config, provinces=SHOGUN, joint=True))
    assert len(jobs) == 1 and jobs[0].provinces == SHOGUN
    assert jobs[0].joint and "Together" in province_label(jobs[0])
    with pytest.raises(ValueError, match="exactly one holding"):
        solve_case(replace(config, provinces=SHOGUN))


def test_worker_json_roundtrip_keeps_immutable_selection_and_borders():
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        research="all",
        provinces=ATTILA,
        joint=True,
        adjacency=(ATTILA,),
        algorithm="cp-sat",
    )
    decoded = RunConfig.from_dict(json.loads(json.dumps(config.to_dict())))
    assert decoded == config
    jobs, _ = make_jobs(decoded)
    assert len(jobs) == 1 and jobs[0].provinces == ATTILA
    assert adjacency_mapping(jobs[0]) == {ATTILA[0]: [ATTILA[1]], ATTILA[1]: [ATTILA[0]]}


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"provinces": (ATTILA[0], ATTILA[0])}, "only once"),
        ({"provinces": ("missing",)}, "available province"),
        ({"adjacency": None}, "Set neighboring"),
        ({"adjacency": ((ATTILA[0], ATTILA[0]),)}, "two different"),
        ({"adjacency": ((ATTILA[0], "missing"),)}, "two different"),
        ({"adjacency": ((ATTILA[0],),)}, "two different"),
        ({"adjacency": (ATTILA, ATTILA[::-1])}, "only once"),
        ({"joint": False}, "joint Attila"),
        ({"joint": "false"}, "must be a boolean"),
    ],
)
def test_invalid_or_unknown_borders_never_silently_drop_effects(changes, message):
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        research="all",
        provinces=ATTILA,
        joint=True,
        adjacency=(ATTILA,),
    )
    with pytest.raises(ValueError, match=message):
        make_jobs(replace(config, **changes))


def test_rome_joint_ownership_is_not_presented_as_an_independent_batch():
    with pytest.raises(ValueError, match="Rome II batches are independent"):
        make_jobs(RunConfig(provinces=("coastal", "inland"), joint=True))


def test_explicit_borders_change_adjacent_income_only_in_the_joint_holding(context):
    a, b = Region("a", context=context), Region("b", context=context)
    provinces = [province(ATTILA[0], a), province(ATTILA[1], b)]
    for index, region in enumerate((a, b)):
        building(
            region, f"factory{index}", ("economy_gdp_industry", "building_to_building_own", 100)
        )
    building(
        a,
        "neighbor_bonus",
        ("economy_gdp_mod_industry", "province_to_regions_own_in_adjacent_province", 20),
    )
    config = RunConfig(game="attila", provinces=ATTILA, joint=True, adjacency=(ATTILA,))
    linked = Economy(provinces, adjacency_mapping(config))
    isolated = Economy(provinces, adjacency_mapping(replace(config, adjacency=())))
    assert linked.evaluate_layout(set(linked.by_id))["objective"] == 220
    assert isolated.evaluate_layout(set(isolated.by_id))["objective"] == 200


def test_joint_shogun_uses_shared_food_and_exports_every_province(tmp_path):
    config = RunConfig(
        game="shogun2",
        faction="oda",
        provinces=SHOGUN,
        joint=True,
        research="all",
        algorithm="cp-sat",
        seconds=5,
        workers=1,
    )
    result = solve_case(config).to_dict()
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["income"] == pytest.approx(7688.06)
    assert set(result["raw"]["provinces"]) == set(SHOGUN)
    assert result["income"] == pytest.approx(
        sum(row["tax_income"] for row in result["raw"]["provinces"].values())
    )
    assert result["metrics"]["food_surplus"] >= 0
    json_path, csv_path = export_session(tmp_path / "joint.json", [result])
    saved = json.loads(json_path.read_text())["cases"][0]
    assert saved["request"]["provinces"] == list(SHOGUN)
    assert saved["request"]["joint"]
    assert ";".join(SHOGUN) in csv_path.read_text()


def test_joint_attila_worker_uses_the_selected_border_graph():
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        provinces=ATTILA,
        joint=True,
        adjacency=(ATTILA,),
        research="all",
        algorithm="cp-sat",
        seconds=0.05,
        workers=1,
    )
    result = solve_case(config).to_dict()
    assert result["request"]["provinces"] == list(ATTILA)
    assert result["raw"]["adjacency"] == adjacency_mapping(config)
    assert "Together" in result["province"]
    assert result["solver"]["status"] in {"OPTIMAL", "FEASIBLE", "UNKNOWN"}
