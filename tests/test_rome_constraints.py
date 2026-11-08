"""Optional exact-building rules survive optimization, replay and joint scope."""

import copy
import json
from dataclasses import replace

import pytest

from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import tiny_catalog

ALPHA, BETA = "rome_religious_alpha_4", "rome_religious_beta_4"


def province(site="capital", **kwargs):
    return Scenario(
        "rom_rome",
        (Site(site, major=True, slots=1),),
        name=site,
        external_food=4,
        minimum_order=-10,
        party=0,
        **kwargs,
    )


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip", "scip-nonlinear", "portfolio"])
@pytest.mark.parametrize("joint", [False, True])
def test_exact_backends_obey_required_and_forbidden_buildings(algorithm, joint):
    data = tiny_catalog()
    if joint:
        scenario = HoldingScenario.from_provinces(
            (province("a"), province("b")),
            (),
            required_buildings=(ALPHA,),
            forbidden_buildings=(BETA,),
        )
        economy = HoldingEconomy(scenario, data)
    else:
        scenario = province(required_buildings=(ALPHA,), forbidden_buildings=(BETA,))
        economy = Economy(scenario, data)
    report = economy.optimize(algorithm, seconds=5, workers=1)
    assert report["solver"]["status"] == "OPTIMAL"
    chosen = {key for row in report["sites"].values() for key in row["buildings"]}
    assert ALPHA in chosen and BETA not in chosen
    replay = {site: row["buildings"] for site, row in report["sites"].items()}
    assert economy.evaluate(replay, report["party_index"])["domestic_net_income"] == pytest.approx(
        report["domestic_net_income"]
    )


def test_joint_requirement_is_global_and_can_be_satisfied_at_one_eligible_site():
    data = tiny_catalog()
    data["buildings"][ALPHA]["occurrences"][0]["allowed_regions"] = ["a"]
    # A non-economic required building must not disappear in candidate filtering.
    data["buildings"][ALPHA]["effects"] = []
    baseline = HoldingScenario.from_provinces((province("a"), province("b")), ())
    assert ALPHA not in HoldingEconomy(baseline, data).candidates["a"]
    scenario = replace(baseline, required_buildings=(ALPHA,))
    economy = HoldingEconomy(scenario, data)
    report = economy.optimize("cp-sat", workers=1)
    assert report["solver"]["status"] == "OPTIMAL"
    assert ALPHA in report["sites"]["a"]["buildings"]
    assert ALPHA not in report["sites"]["b"]["buildings"]
    with pytest.raises(ValueError, match="requirements violated"):
        economy.evaluate({"a": ["rome_city_4"], "b": ["rome_city_4"]}, 0)


def test_local_requirements_stay_local_when_building_joint_holding():
    scenario = HoldingScenario.from_provinces(
        (province("a", required_buildings=(ALPHA,)), province("b")), ()
    )
    economy = HoldingEconomy(scenario, tiny_catalog())
    with pytest.raises(ValueError, match="requirements violated"):
        economy.evaluate({"a": ["rome_city_4"], "b": ["rome_city_4", ALPHA]}, 0)
    report = economy.optimize("cp-sat", workers=1)
    assert ALPHA in report["sites"]["a"]["buildings"]


def test_forbidden_layout_and_unconstrained_proof_cannot_be_reused():
    baseline = Economy(province(), tiny_catalog()).optimize("cp-sat", workers=1)
    selected = next(
        key for key in baseline["sites"]["capital"]["buildings"] if key != "rome_city_4"
    )
    restricted = Economy(province(forbidden_buildings=(selected,)), tiny_catalog())
    with pytest.raises(ValueError, match="requirements violated"):
        restricted.warm_values(baseline)
    with pytest.raises(ValueError, match="Optimality proof"):
        restricted.reuse_optimum(baseline)


@pytest.mark.parametrize("required", [(ALPHA, ALPHA), "not-a-list", (42,), ("",)])
def test_bad_requirement_ids_rejected(required):
    with pytest.raises(ValueError, match="Building requirements"):
        province(required_buildings=required)


def test_unknown_conflicting_and_unavailable_requirements_are_actionable():
    with pytest.raises(ValueError, match="both required and forbidden"):
        province(required_buildings=(ALPHA,), forbidden_buildings=(ALPHA,))
    with pytest.raises(ValueError, match="Unknown building IDs"):
        Economy(province(forbidden_buildings=("missing",)), tiny_catalog())
    data = tiny_catalog()
    data["buildings"][ALPHA]["level"] = 5
    with pytest.raises(ValueError, match="unavailable"):
        Economy(province(required_buildings=(ALPHA,)), data)
    data["buildings"][ALPHA]["level"] = 4
    data["buildings"][ALPHA]["occurrences"][0]["allowed_regions"] = ["other"]
    with pytest.raises(ValueError, match="unavailable"):
        Economy(province(required_buildings=(ALPHA,)), data)


def test_explicit_lower_core_is_retained_without_changing_default_core_pruning():
    data = tiny_catalog()
    lower = copy.deepcopy(data["buildings"]["rome_city_4"])
    lower.update(id="rome_city_3", level=3)
    data["buildings"][lower["id"]] = lower
    assert lower["id"] not in Economy(province(), data).candidates["capital"]
    economy = Economy(province(required_buildings=(lower["id"],)), data)
    result = economy.optimize("cp-sat", workers=1)
    assert lower["id"] in result["sites"]["capital"]["buildings"]
    assert "rome_city_4" not in result["sites"]["capital"]["buildings"]


def test_impossible_slot_requirements_return_infeasible():
    scenario = province(required_buildings=(ALPHA, BETA))
    report = Economy(scenario, tiny_catalog()).optimize("cp-sat", workers=1)
    assert report["solver"]["status"] == "INFEASIBLE"


def test_new_rules_roundtrip_without_changing_default_serialization():
    single = province(required_buildings=(ALPHA,), forbidden_buildings=(BETA,))
    joint = HoldingScenario.from_provinces((province("a"), province("b")), ())
    constrained = replace(joint, required_buildings=(ALPHA,), forbidden_buildings=(BETA,))
    for scenario in (single, constrained):
        decoded = type(scenario).from_dict(json.loads(json.dumps(scenario.to_dict())))
        assert decoded == scenario
    for scenario in (province(), joint):
        assert "required_buildings" not in scenario.to_dict()
        assert "forbidden_buildings" not in scenario.to_dict()
