"""Joint seeds are original-model witnesses, never substitutes for native proofs."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from games.optimization.cancellation import Cancellation
from games.optimization.competition import Result, solve
from games.tw.shogun2 import optimization, preparation
from games.tw.shogun2.catalog import load_data
from games.tw.shogun2.model import Economy
from games.tw.shogun2.scenario import Province, Scenario
from twoptimizer.shogun_session import ShogunSession


def sustainable_report(economy):
    layout = {}
    for key, (_, province) in economy.provinces.items():
        buildings = [
            "sho_castle_1_fort",
            "sho_farming_4_consolidation",
            "sho_infrastructure_0_trails",
        ]
        if province["has_port"]:
            buildings.append("sho_port_0_coastal_village")
        if province["specialty"]:
            buildings.append(next(b for b in economy.candidates[key] if "region_specialty" in b))
        layout[key] = buildings
    return {"scenario": economy.scenario.to_dict(), **economy.evaluate(layout)}


@pytest.fixture
def economy():
    return Economy(Scenario("oda", (Province("jap_sado"), Province("jap_settsu"))))


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_both_backends_accept_checked_hints_and_keep_exact_optimum(economy, algorithm):
    seed = sustainable_report(economy)
    hinted = economy.optimize(algorithm, workers=1, incumbent=seed)
    plain = economy.optimize(algorithm, workers=1)
    assert hinted["solver"]["status"] == plain["solver"]["status"] == "OPTIMAL"
    assert hinted["domestic_tax_income"] == pytest.approx(plain["domestic_tax_income"])
    assert hinted["solver"]["warm_start"]["validated"]


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_cancel_after_validating_seed_preserves_real_income(economy, algorithm):
    seed = sustainable_report(economy)
    expected = seed["domestic_tax_income"]
    seed["domestic_tax_income"] = 1e15  # Supplied income is never trusted.
    cancellation = Cancellation()
    cancellation.cancel()
    result = economy.optimize(algorithm, workers=1, incumbent=seed, cancellation=cancellation)
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["solver"]["bound"] is None
    assert result["domestic_tax_income"] == expected
    assert result["solver"]["incumbent_retained"]


def test_unknown_with_seed_keeps_native_bound_and_reconstructs_products(monkeypatch, economy):
    seed = sustainable_report(economy)
    expected = seed["domestic_tax_income"]

    def search(binary, algorithm, **options):
        assert binary.feasible(options["hint_values"])
        assert float(binary.profit @ options["hint_values"]) + binary.offset == pytest.approx(
            expected
        )
        return Result(algorithm, "UNKNOWN", bound=expected + 100)

    monkeypatch.setattr(optimization, "solve", search)
    result = economy.optimize(incumbent=seed)
    assert result["solver"]["bound"] == expected + 100
    assert result["domestic_tax_income"] == expected
    assert result["solver"]["native_status"] == "UNKNOWN"


@pytest.mark.parametrize("status", ["INFEASIBLE", "OPTIMAL", "FEASIBLE"])
def test_seed_contradicting_native_proof_is_an_error(monkeypatch, economy, status):
    seed = sustainable_report(economy)
    monkeypatch.setattr(
        optimization,
        "solve",
        lambda *args, **kwargs: Result("cp-sat", status, objective=0, bound=0),
    )
    with pytest.raises(AssertionError, match="Native proof contradicts"):
        economy.optimize(incumbent=seed)


def test_invalid_unique_seed_is_rejected_before_native_search(monkeypatch, economy):
    seed = sustainable_report(economy)
    for row in seed["provinces"].values():
        row["buildings"].append("sho_crafts_4_kanabukama")
    monkeypatch.setattr(optimization, "solve", lambda *args, **kwargs: pytest.fail("native search"))
    with pytest.raises(ValueError, match=r"Unique building duplicated|food deficit"):
        economy.optimize(incumbent=seed)


def test_hint_vector_must_satisfy_original_binary_constraints(economy):
    model = economy.compile()
    with pytest.raises(ValueError, match="Initial binary layout"):
        solve(model, "cp-sat", hint_values=[0] * len(model.names))


def test_fresh_joint_preparation_builds_compatible_layout_without_unique_duplication():
    _, rules = load_data()
    provinces = tuple(Province(key) for key in tuple(rules["provinces"])[:4])
    economy = Economy(Scenario("oda", provinces))
    seed, report = preparation.prepare(economy, 20)
    assert report["status"] == "validated"
    assert report["completed"] == 4
    assert report["allowance_seconds"] == 4
    assert seed is not None and seed["food_surplus"] >= 0
    assert seed["faction_arts_food"] == economy.arts["food"]
    assert all(row["local_food_balance"] >= 0 for row in seed["provinces"].values())
    assert not any(
        economy.catalog.buildings[key].unique
        for row in seed["provinces"].values()
        for key in row["buildings"]
    )
    assert not economy.scenario.forbidden_buildings


def test_preparation_skips_small_short_and_global_required_scenarios(economy):
    assert preparation.prepare(economy, None)[1]["status"] == "skipped"
    _, rules = load_data()
    provinces = tuple(Province(key) for key in tuple(rules["provinces"])[:4])
    joint = Economy(replace(economy.scenario, provinces=provinces))
    assert preparation.prepare(joint, 1)[1]["reason"] == "Short remaining search allowance"
    required = Economy(replace(joint.scenario, required_buildings=("sho_crafts_1_market",)))
    assert preparation.prepare(required, 20)[1]["status"] == "skipped"


def test_failed_preparatory_case_does_not_become_infeasibility_proof(monkeypatch):
    _, rules = load_data()
    provinces = tuple(Province(key) for key in tuple(rules["provinces"])[:4])
    economy = Economy(Scenario("oda", provinces))
    monkeypatch.setattr(
        Economy, "optimize", lambda *args, **kwargs: {"solver": {"status": "UNKNOWN"}}
    )
    seed, report = preparation.prepare(economy, 20)
    assert seed is None and report["status"] == "unfinished"
    assert report["completed"] == 0


def test_session_combines_cached_local_layouts_and_revalidates_food_and_unique_rules(
    monkeypatch, economy
):
    state = ShogunSession()
    config = SimpleNamespace(algorithm="cp-sat", seconds=1, workers=1)
    for province in economy.scenario.provinces:
        local = Economy(replace(economy.scenario, provinces=(province,)))
        state.cases[province.id] = sustainable_report(local)
    seeds = []

    def search(self, *args, incumbent, **kwargs):
        seeds.append(incumbent)
        return {"scenario": self.scenario.to_dict(), "solver": {"status": "UNKNOWN"}}

    monkeypatch.setattr(Economy, "optimize", search)
    state.solve(economy, config)
    assert seeds[-1] is not None
    assert seeds[-1]["faction_arts_food"] == economy.arts["food"]
    for case in state.cases.values():
        for row in case["provinces"].values():
            row["buildings"].append("sho_crafts_4_kanabukama")
    state.solve(economy, config)
    assert seeds[-1] is None


def test_session_copies_reports_and_does_not_reuse_invalid_changed_candidates(monkeypatch, economy):
    state = ShogunSession()
    config = SimpleNamespace(algorithm="cp-sat", seconds=1, workers=1)
    report = sustainable_report(economy)
    report["solver"] = {"status": "FEASIBLE"}
    monkeypatch.setattr(Economy, "optimize", lambda *args, **kwargs: report)
    state.solve(economy, config)
    snapshot = deepcopy(next(iter(state.cases.values())))
    report["provinces"].clear()
    assert next(iter(state.cases.values())) == snapshot
    changed = Economy(
        replace(economy.scenario, forbidden_buildings=("sho_farming_4_consolidation",))
    )
    assert state._combined(changed) is None
    state.trim(0)
    assert not state.cases
    state.cases["one"] = snapshot
    state.clear()
    assert not state.cases


def test_matching_model_bound_and_live_seed_survive_unknown(monkeypatch, economy):
    seed = sustainable_report(economy)
    seed["model_fingerprint"] = economy.compile().fingerprint()
    income = seed["domestic_tax_income"]
    seed["solver"] = {"bound": income + 100}
    observations = []

    def search(binary, algorithm, **options):
        options["on_search"](None, None, 0.1)
        return Result(algorithm, "UNKNOWN")

    monkeypatch.setattr(optimization, "solve", search)
    result = economy.optimize(incumbent=seed, on_search=lambda *event: observations.append(event))
    assert result["solver"]["bound"] == income + 100
    assert result["solver"]["status"] == "FEASIBLE"
    assert len(observations) == 2
    assert all(event[:2] == (income, income + 100) for event in observations)


def test_changed_compiled_model_revalidates_layout_but_discards_old_bound(monkeypatch, economy):
    seed = sustainable_report(economy)
    seed["model_fingerprint"] = economy.compile().fingerprint()
    seed["solver"] = {"bound": seed["domestic_tax_income"]}
    changed = Economy(
        replace(
            economy.scenario,
            provinces=tuple(replace(p, town_wealth=1000) for p in economy.scenario.provinces),
        )
    )
    monkeypatch.setattr(optimization, "solve", lambda *args, **kwargs: Result("cp-sat", "UNKNOWN"))
    result = changed.optimize(incumbent=seed)
    assert result["solver"]["bound"] is None
    assert result["domestic_tax_income"] > seed["domestic_tax_income"]
    assert result["model_fingerprint"] != seed["model_fingerprint"]


def test_session_keeps_strongest_matching_model_bound_across_backends(monkeypatch, economy):
    seed = sustainable_report(economy)
    seed["model_fingerprint"] = economy.compile().fingerprint()
    seed["solver"] = {"bound": seed["domestic_tax_income"] + 500}
    stronger = deepcopy(seed)
    stronger["solver"]["bound"] = seed["domestic_tax_income"] + 100
    state = ShogunSession({"cp": seed, "highs": stronger})
    captured = []

    def search(self, *args, incumbent, **kwargs):
        captured.append(incumbent)
        return {"scenario": self.scenario.to_dict(), "solver": {"status": "UNKNOWN"}}

    monkeypatch.setattr(Economy, "optimize", search)
    state.solve(economy, SimpleNamespace(algorithm="cp-sat", seconds=1, workers=1))
    assert captured[0]["solver"]["bound"] == stronger["solver"]["bound"]
    assert seed["solver"]["bound"] != stronger["solver"]["bound"]
