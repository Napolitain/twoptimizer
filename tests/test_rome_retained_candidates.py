"""Relaxed requirement baselines retain the same legal building choices."""

import copy
import json
from dataclasses import replace

import pytest

from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import effect, tiny_catalog

LOWER = "rome_city_3"
BETA = "rome_religious_beta_4"


def _catalog(*, scarce_food=False):
    data = tiny_catalog()
    core = data["buildings"]["rome_city_4"]
    core["effects"] = [effect("rom_building_gdp_industry_manufacture", 100)]
    lower = copy.deepcopy(core)
    lower.update(id=LOWER, level=3)
    lower["effects"] = [effect("rom_building_gdp_industry_manufacture", 90)]
    data["buildings"][LOWER] = lower
    if scarce_food:
        core["effects"].append(effect("rom_building_food_consumption", 4, "this_region"))
    return data


def _province(name="capital", **kwargs):
    return Scenario(
        "rom_rome",
        (Site(name, major=True, slots=1),),
        name=name,
        external_food=4,
        minimum_order=-10,
        party=0,
        **kwargs,
    )


def test_relaxed_baseline_keeps_lower_core_and_its_food_tradeoff():
    data = _catalog(scarce_food=True)
    naive = Economy(_province(), data).optimize("cp-sat", workers=1)
    required = Economy(_province(required_buildings=(LOWER,)), data)
    baseline = Economy(_province(retained_buildings=(LOWER,)), data)
    assert required.candidates == baseline.candidates
    constrained = required.optimize("cp-sat", workers=1)
    relaxed = baseline.optimize("cp-sat", workers=1)
    assert constrained["solver"]["status"] == relaxed["solver"]["status"] == "OPTIMAL"
    assert constrained["domestic_net_income"] == pytest.approx(187)
    assert naive["domestic_net_income"] == pytest.approx(110)
    assert relaxed["domestic_net_income"] == constrained["domestic_net_income"]
    assert LOWER in relaxed["sites"]["capital"]["buildings"]
    assert BETA in relaxed["sites"]["capital"]["buildings"]


def test_retained_candidate_is_optional_and_changes_proof_identity():
    scenario = _province(retained_buildings=(LOWER,))
    economy = Economy(scenario, _catalog())
    baseline = Economy(_province(), _catalog())
    assert economy.fingerprint() != baseline.fingerprint()
    result = economy.optimize("cp-sat", workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    assert LOWER not in result["sites"]["capital"]["buildings"]
    assert "rome_city_4" in result["sites"]["capital"]["buildings"]
    replay = {key: row["buildings"] for key, row in result["sites"].items()}
    assert economy.evaluate(replay, 0)["domestic_net_income"] == result["domestic_net_income"]


def test_joint_retention_reaches_every_local_candidate_pool_without_forcing_copies():
    scenario = HoldingScenario.from_provinces(
        (_province("a"), _province("b")), (), retained_buildings=(LOWER,)
    )
    economy = HoldingEconomy(scenario, _catalog())
    assert all(LOWER in candidates for candidates in economy.candidates.values())
    assert all(not local.scenario.required_buildings for local in economy.locals.values())
    result = economy.optimize("cp-sat", workers=1)
    assert result["solver"]["status"] == "OPTIMAL"
    assert all(LOWER not in row["buildings"] for row in result["sites"].values())
    assert result["scenario"]["retained_buildings"] == [LOWER]


def test_local_and_global_retained_candidates_roundtrip_and_defaults_stay_unchanged():
    single = _province(retained_buildings=(LOWER,))
    joint = HoldingScenario.from_provinces((single, _province("b")), ())
    global_retention = replace(joint, retained_buildings=(BETA,))
    for scenario in (single, joint, global_retention):
        restored = type(scenario).from_dict(json.loads(json.dumps(scenario.to_dict())))
        assert restored == scenario
    assert "retained_buildings" not in _province().to_dict()
    assert "retained_buildings" not in HoldingScenario.from_provinces((_province(),), ()).to_dict()


@pytest.mark.parametrize("retained", ["not-a-list", (LOWER, LOWER), ("",), (1,)])
def test_invalid_retained_ids_are_rejected(retained):
    with pytest.raises(ValueError, match="Building requirements"):
        _province(retained_buildings=retained)


def test_retention_does_not_unlock_unsupported_levels_or_placements():
    data = _catalog()
    data["buildings"][LOWER]["level"] = 5
    assert LOWER not in Economy(_province(retained_buildings=(LOWER,)), data).candidates["capital"]
    data["buildings"][LOWER]["level"] = 3
    data["buildings"][LOWER]["occurrences"][0]["allowed_regions"] = ["elsewhere"]
    assert LOWER not in Economy(_province(retained_buildings=(LOWER,)), data).candidates["capital"]
    with pytest.raises(ValueError, match="Unknown building IDs"):
        Economy(_province(retained_buildings=("missing",)), data)


def test_retained_noneconomic_candidates_can_still_be_forbidden():
    data = _catalog()
    data["buildings"][BETA]["effects"] = []
    base = _province(retained_buildings=(BETA,), forbidden_buildings=(BETA,))
    economy = Economy(base, data)
    assert BETA in economy.candidates["capital"]
    with pytest.raises(ValueError, match="forbidden"):
        economy.evaluate({"capital": ["rome_city_4", BETA]}, 0)
