"""Attila CLI compatibility over the shared typed application service."""

import json
from dataclasses import replace

import pytest

from games.tw import benchmark, faction_comparison
from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.scenario import Scenario
from games.tw.models.game_attila import AttilaGame
from twoptimizer import service
from twoptimizer.adapters.attila import faction_report
from twoptimizer.attila_session import AttilaSession, campaign_scenario, signature
from twoptimizer.models import AttilaOptions, RegionFertility, RunConfig
from twoptimizer.session import RunSession


def _config(**changes):
    return replace(
        RunConfig(
            game="attila",
            faction="att_fact_eastern_roman_empire",
            province="att_prov_thracia",
            algorithm="cp-sat",
            research="all",
            workers=1,
        ),
        **changes,
    )


def test_cli_and_direct_case_have_the_same_income_and_relaxation_semantics():
    report = benchmark.main(
        [
            "--province",
            "Thracia",
            "--fertility",
            "5",
            "--workers",
            "1",
            "--algorithms",
            "cp-sat",
            "glop",
        ]
    )
    case = report["cases"][0]
    exact, relaxation = case["results"]
    direct = service.solve_case(_config())
    relaxed = service.solve_case(_config(algorithm="glop"))
    assert direct.income == pytest.approx(24140.375)
    assert exact["objective"] == direct.income
    assert exact["layout"]["finances"]["total"]["net_income"] == direct.income
    assert exact["layout"]["province_food"] == direct.raw["layout"]["province_food"]
    assert direct.request.seconds is None
    assert case["best_feasible"] == direct.income
    assert case["upper_bound"] == direct.solver.bound
    assert exact["gap_to_bound_percent"] == 0
    assert relaxation["relaxation"] is True
    assert relaxation["selected"] is None
    assert relaxation["fractional_values"]
    assert relaxation["gap_to_bound_percent"] is None
    assert relaxed.income is None
    assert relaxed.gap_percent is None
    assert relaxed.buildings == []
    assert relaxed.solver.bound is not None and direct.income is not None
    assert relaxed.solver.bound >= direct.income


def test_advanced_cli_compiles_the_same_joint_campaign_model(tmp_path):
    data = {
        "campaign": {"base_tribute": 100},
        "adjacency": {"att_prov_aegyptus": ["att_prov_aethiopia"]},
    }
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(data))
    args = benchmark._parser().parse_args(
        [
            "--province",
            "Aegyptus",
            "--province",
            "Aethiopia",
            "--joint",
            "--fertility",
            "1",
            "--scenario",
            str(path),
            "--technology",
            "Moulded Architecture",
            "--region-fertility",
            "Alexandria=2",
            "--city-level",
            "2",
            "--building-level",
            "2",
            "--military",
            "--seed",
            "7",
            "--beam-width",
            "64",
            "--restarts",
            "3",
            "--algorithms",
            "glop",
            "--workers",
            "1",
        ]
    )
    jobs, skipped = service.make_jobs(benchmark.request_from_args(args))
    assert skipped == []
    assert len(jobs) == 1
    job = jobs[0]
    assert job.joint
    assert set(job.holdings) == {"att_prov_aegyptus", "att_prov_aethiopia"}
    assert job.attila.technologies == ("Moulded Architecture",)
    assert job.attila.region_fertility == (RegionFertility("Alexandria", 2),)
    assert (job.attila.seed, job.attila.beam_width, job.attila.restarts) == (7, 64, 3)
    assert job.attila.campaign is not None
    assert job.attila.campaign.to_dict() == data
    prepared = AttilaSession().prepare(job)
    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
    )
    parser.regions["att_reg_aegyptus_alexandria"].fertility = 2
    expected = compile_scenario(
        [parser.provinces[key] for key in job.holdings],
        SnapshotOptions(
            fertility=1,
            city_level=2,
            building_level=2,
            military=True,
            technologies=frozenset({"Moulded Architecture"}),
            scenario=Scenario(data),
        ),
    )
    assert signature(prepared.snapshot.model) == signature(expected.model)
    assert prepared.snapshot.economy is not None
    assert prepared.snapshot.economy.base_fertility["att_reg_aegyptus_alexandria"] == 2
    assert prepared.snapshot.economy.scenario.campaign.base_tribute == 100
    assert tuple(prepared.snapshot.economy.scenario.adjacency["att_prov_aegyptus"]) == (
        "att_prov_aethiopia",
    )
    assert "att_prov_aethiopia" not in prepared.snapshot.economy.scenario.adjacency


def test_joint_cli_defaults_to_no_borders_and_keeps_campaign_inputs(tmp_path):
    path = tmp_path / "campaign.json"
    path.write_text('{"campaign":{"base_tribute":200}}')
    args = benchmark._parser().parse_args(
        [
            "--province",
            "Thracia",
            "--province",
            "Aegyptus",
            "--joint",
            "--fertility",
            "5",
            "--scenario",
            str(path),
        ]
    )
    jobs, _ = service.make_jobs(benchmark.request_from_args(args))
    scenario = campaign_scenario(jobs[0])
    assert scenario is not None
    assert scenario.campaign.base_tribute == 200
    assert dict(scenario.adjacency) == {key: () for key in jobs[0].holdings}
    assert jobs[0].attila.campaign is not None
    assert jobs[0].attila.campaign.to_dict() == {"campaign": {"base_tribute": 200}}


def test_conflicting_campaign_and_ui_borders_are_rejected():
    campaign = Scenario({"adjacency": {"att_prov_aegyptus": ["att_prov_aethiopia"]}})
    config = _config(
        provinces=("att_prov_aegyptus", "att_prov_aethiopia"),
        joint=True,
        adjacency=(("att_prov_aegyptus", "att_prov_aethiopia"),),
        attila=AttilaOptions(campaign=campaign),
    )
    with pytest.raises(ValueError, match="Campaign adjacency conflicts"):
        service.solve_case(config)


def test_matching_ui_borders_do_not_rewrite_the_campaign():
    data = {
        "campaign": {"base_tribute": 50},
        "adjacency": {
            "att_prov_aegyptus": ["att_prov_aethiopia"],
            "att_prov_aethiopia": ["att_prov_aegyptus"],
        },
    }
    config = _config(
        provinces=("att_prov_aegyptus", "att_prov_aethiopia"),
        joint=True,
        adjacency=(("att_prov_aegyptus", "att_prov_aethiopia"),),
        attila=AttilaOptions(campaign=Scenario(data)),
    )
    scenario = campaign_scenario(config)
    assert scenario is not None
    assert scenario.to_dict() == data
    assert config.attila.campaign is not None
    assert config.attila.campaign.to_dict() == data


@pytest.mark.parametrize("objective", ["wealth", "legacy"])
def test_application_cli_accepts_only_the_income_objective(objective):
    with pytest.raises(SystemExit) as error:
        benchmark.main(["--objective", objective])
    assert error.value.code == 2


def test_comparison_compiles_once_and_revalidates_saved_proofs(monkeypatch):
    import twoptimizer.attila_session as module

    config = _config()
    state = AttilaSession(reuse_proofs=True)
    session = RunSession(attila=state)
    first = service.solve_case(config, session=session)
    prepared = state.prepare(config)
    assert state.prepare(replace(config, algorithm="glop", seconds=3)) is prepared
    row = faction_report(first)
    prior = {row["signature"]: row}
    restored = RunSession(attila=AttilaSession(reuse_proofs=True, prior=prior))
    original_solve = module.solve
    called = []

    def solve(*args, **kwargs):
        called.append(True)
        return original_solve(*args, **kwargs)

    monkeypatch.setattr(module, "solve", solve)
    replay = service.solve_case(config, session=restored)
    assert called == []
    assert replay.income == first.income
    assert replay.solver.status == "OPTIMAL"
    assert replay.raw["proof_reused"] is True
    assert replay.raw["layout"]["objective"] == first.income
    corrupted = {row["signature"]: {**row, "bound": row["bound"] + 100}}
    rerun = service.solve_case(
        config,
        session=RunSession(attila=AttilaSession(reuse_proofs=True, prior=corrupted)),
    )
    assert called == [True]
    assert rerun.raw["proof_reused"] is False
    assert rerun.income == first.income


def test_region_overrides_do_not_leak_between_cached_models():
    config = _config()
    state = AttilaSession()
    original = state.prepare(config)
    changed = state.prepare(
        replace(
            config,
            attila=AttilaOptions(region_fertility=(RegionFertility("Marcianopolis", 0),)),
        )
    )
    restored = state.prepare(config)
    assert signature(changed.snapshot.model) != signature(original.snapshot.model)
    assert signature(restored.snapshot.model) == signature(original.snapshot.model)


def test_faction_comparison_keeps_requested_province_column_order():
    args = faction_comparison._parser().parse_args([])
    jobs = faction_comparison._faction_jobs(
        args, "att_fact_eastern_roman_empire", ["Thracia", "Aegyptus"]
    )
    assert [job.province for job in jobs] == ["att_prov_thracia", "att_prov_aegyptus"]
