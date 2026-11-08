"""Optional requirements survive application preparation, batching and exports."""

import csv
import json
from dataclasses import replace

import pytest

from games.tw.attila.scenario import Scenario
from games.tw.rome2.holdings import HoldingScenario
from tests.support.ui import result
from twoptimizer.adapters.rome2 import prepare_scenario as rome_scenario
from twoptimizer.adapters.shogun2 import prepare_scenario as shogun_scenario
from twoptimizer.attila_session import campaign_scenario
from twoptimizer.constraint_catalog import building_choices
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.export import export_session
from twoptimizer.models import AttilaOptions, RunConfig
from twoptimizer.requests import default_config, make_jobs


def test_default_request_shape_and_immutable_optional_worker_roundtrip():
    assert "constraints" not in RunConfig().to_dict()
    required = ["temple"]
    options = ConstraintOptions.from_dict(
        {"required_buildings": required, "forbidden_buildings": ["market"]}
    )
    required.clear()
    config = replace(default_config("rome2"), constraints=options)
    restored = RunConfig.from_dict(json.loads(json.dumps(config.to_dict())))
    assert restored == config and restored.constraints.required_buildings == ("temple",)
    assert options.to_dict() == {
        "required_buildings": ["temple"],
        "forbidden_buildings": ["market"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"unknown": 1},
        {"required_buildings": "temple"},
        {"required_buildings": [""]},
        {"forbidden_buildings": [None]},
        {"required_buildings": ["temple", "temple"]},
        {"required_buildings": ["temple"], "forbidden_buildings": ["temple"]},
        {"minimum_religious_influence": True},
        {"minimum_religious_influence": float("inf")},
        {"minimum_religious_influence": -1},
        {"shogun_religion": "missing"},
        {"nanban_contact": 1},
    ],
)
def test_invalid_worker_constraints_are_rejected_before_any_solver(payload):
    with pytest.raises(ValueError):
        RunConfig.from_dict({"constraints": payload})


@pytest.mark.parametrize(
    "game, options",
    [
        ("rome2", ConstraintOptions(minimum_religious_influence=1)),
        ("shogun2", ConstraintOptions(minimum_religious_influence=1)),
        ("attila", ConstraintOptions(shogun_religion="christian")),
        ("rome2", ConstraintOptions(nanban_contact=True)),
    ],
)
def test_game_specific_options_are_not_silently_ignored(game, options):
    with pytest.raises(ValueError):
        make_jobs(replace(default_config(game), constraints=options))


def test_state_religion_filters_all_clans_and_rejects_explicit_incompatible_clan():
    base = replace(
        default_config("shogun2"),
        faction="all",
        constraints=ConstraintOptions(shogun_religion="christian"),
    )
    jobs, skipped = make_jobs(base)
    assert jobs and all(job.faction != "ikko_ikki" for job in jobs)
    assert len(skipped) == 1 and "Ikko" in skipped[0]
    with pytest.raises(ValueError, match="incompatible"):
        make_jobs(replace(base, faction="ikko_ikki"))
    jobs, skipped = make_jobs(replace(base, constraints=ConstraintOptions(shogun_religion="ikko")))
    assert [job.faction for job in jobs] == ["ikko_ikki"] and skipped


def test_attilla_requirements_merge_with_campaign_and_target_every_selected_province():
    campaign = Scenario(
        {
            "building_rules": [{"buildings": ["temple"], "maximum": 1}],
            "targets": [{"metric": "research_percent", "scope": "faction", "value": 10}],
        }
    )
    before = campaign.to_dict()
    config = replace(
        default_config("attila"),
        provinces=("att_prov_thracia", "att_prov_macedonia"),
        joint=True,
        attila=AttilaOptions(campaign=campaign),
        constraints=ConstraintOptions(
            required_buildings=("temple",),
            forbidden_buildings=("market",),
            minimum_religious_influence=4,
        ),
    )
    prepared = campaign_scenario(config)
    assert prepared is not None and campaign.to_dict() == before
    assert prepared.building_rules[0].maximum == 1
    assert prepared.building_rules[1].minimum == 1
    assert prepared.building_rules[2].maximum == 0
    targets = prepared.targets[1:]
    assert {target.target for target in targets} == set(config.holdings)
    assert all(target.metric == "religion:state" and target.value == 4 for target in targets)
    assert prepared.adjacency["att_prov_thracia"] == ("att_prov_macedonia",)


def test_rome_requirements_apply_once_across_joint_holding_and_per_independent_case():
    config = replace(
        default_config("rome2"),
        provinces=("rome_main_italia", "rome_main_magna_graecia"),
        constraints=ConstraintOptions(required_buildings=("rome_religious_jupiter_2",)),
    )
    independent, _ = make_jobs(config)
    assert len(independent) == 2
    assert all(rome_scenario(job).required_buildings for job in independent)
    jobs, _ = make_jobs(replace(config, joint=True))
    together = rome_scenario(jobs[0])
    assert isinstance(together, HoldingScenario)
    assert together.required_buildings == config.constraints.required_buildings
    assert all(not province.required_buildings for province in together.provinces)


def test_shogun_requirements_and_faith_options_reach_scenario():
    config = replace(
        default_config("shogun2"),
        constraints=ConstraintOptions(
            required_buildings=("sho_christian_1_chapel",),
            forbidden_buildings=("sho_stealth_4_mizu_shobai",),
            shogun_religion="christian",
            nanban_contact=True,
        ),
    )
    scenario = shogun_scenario(config)
    assert scenario.required_buildings == config.constraints.required_buildings
    assert scenario.forbidden_buildings == config.constraints.forbidden_buildings
    assert scenario.religion == "christian" and scenario.nanban_contact


def test_optional_constraints_remain_inspectable_in_json_and_csv(tmp_path):
    config = replace(RunConfig(), constraints=ConstraintOptions(required_buildings=("temple",)))
    json_path, csv_path = export_session(tmp_path / "constrained.json", [result(config)])
    assert json.loads(json_path.read_text())["cases"][0]["request"]["constraints"] == (
        config.constraints.to_dict()
    )
    with csv_path.open(newline="") as stream:
        assert (
            json.loads(next(csv.DictReader(stream))["constraints"]) == config.constraints.to_dict()
        )


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_browser_keeps_catalog_searchable_after_an_unavailable_requirement(game):
    config = default_config(game)
    baseline = building_choices(config)
    assert baseline and len({key for _, key in baseline}) == len(baseline)
    assert (
        building_choices(
            replace(config, constraints=ConstraintOptions(required_buildings=("unavailable",)))
        )
        == baseline
    )
