"""Experimental native products preserve economics, certificates and cancellation."""

from contextlib import suppress
from copy import deepcopy
from itertools import product
from time import perf_counter

import pytest
from ortools.sat.python import cp_model

from games.optimization.bounds import BoundSearchResult
from games.optimization.cancellation import Cancellation
from games.optimization.cp_backend import NativeCP
from games.optimization.native_model import feasible, objective_value
from games.tw.rome2 import joint_search
from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario
from games.tw.rome2.model import Economy
from games.tw.rome2.native_search import prepare, validated_values
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import effect


def province(name):
    return Scenario(
        "rom_rome",
        (Site(name + "_capital", major=True, slots=1), Site(name + "_town", slots=1)),
        name=name,
        external_food=4,
        minimum_order=-10,
    )


def economy(data, joint=False):
    if joint:
        return HoldingEconomy(
            HoldingScenario.from_provinces((province("a"), province("b")), ()), data
        )
    return Economy(province("a"), data)


def exhaustive_income(model):
    best = float("-inf")
    for extras in product(
        (None, "rome_religious_alpha_4", "rome_religious_beta_4"), repeat=len(model.scenario.sites)
    ):
        layout = {
            site.id: ["rome_city_4" if site.major else "rome_town_4"]
            + ([] if extra is None else [extra])
            for site, extra in zip(model.scenario.sites, extras, strict=True)
        }
        for party in model.parties:
            with suppress(ValueError):
                best = max(best, model.evaluate(layout, party)["domestic_net_income"])
    return best


@pytest.mark.parametrize("joint", [False, True])
@pytest.mark.parametrize("signed", [False, True])
def test_native_linear_and_highs_match_enumerated_economics(tiny, joint, signed):
    if signed:
        tiny["buildings"]["rome_religious_alpha_4"]["effects"].extend(
            [
                effect("rom_building_tax_level", -7, "this_province"),
                effect("rom_building_gdp_mod_industry", -13, "this_province"),
            ]
        )
    expected = exhaustive_income(economy(tiny, joint))
    for backend, native in (("cp-sat", False), ("cp-sat", True), ("highs", False)):
        model = economy(tiny, joint)
        result = model.optimize(backend, seconds=5, workers=1, native_products=native)
        assert result["solver"]["status"] == "OPTIMAL"
        assert result["domestic_net_income"] == pytest.approx(expected)
        assert result["solver"]["bound"] == pytest.approx(expected)
        expected_formulation = "native_products" if native else "linearized_income"
        assert result["solver"]["formulation"] == expected_formulation
        assert model.reuse_optimum(result)["domestic_net_income"] == pytest.approx(expected)


def test_native_search_clone_keeps_canonical_model_and_validates_previous_auxiliaries(tiny):
    model = economy(tiny)
    previous = model.optimize(seconds=5, workers=1)
    canonical = str(model._prepared.model.proto)
    result = model.optimize(seconds=5, workers=1, incumbent=previous, native_products=True)
    assert result["domestic_net_income"] == previous["domestic_net_income"]
    assert str(model._prepared.model.proto) == canonical


def test_native_unknown_retains_validated_linear_incumbent(monkeypatch, tiny):
    model = economy(tiny)
    previous = model.optimize(seconds=5, workers=1)
    monkeypatch.setattr(
        joint_search, "solve_with_progress", lambda *args, **kwargs: cp_model.UNKNOWN
    )
    result = model.optimize(seconds=5, workers=1, incumbent=previous, native_products=True)
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["domestic_net_income"] == previous["domestic_net_income"]
    assert result["selected_decision_indices"] == previous["selected_decision_indices"]


def test_native_rejects_invalid_reconstructed_product(monkeypatch, tiny):
    model = economy(tiny)
    previous = model.optimize(seconds=5, workers=1)
    values = model.warm_values(previous)
    values["income_ten_thousandths"] += 1
    monkeypatch.setattr(model, "warm_values", lambda reference: values)
    with pytest.raises(AssertionError, match="native product constraints"):
        model.optimize(seconds=5, workers=1, incumbent=previous, native_products=True)


def linear_seed(model):
    proto = model.build()
    problem = NativeCP.from_linear(proto)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 5
    assert solver.solve(problem.model) == cp_model.OPTIMAL
    values = {variable.index: solver.value(variable) for variable in problem.variables}
    income = round(solver.objective_value)
    return BoundSearchResult(income, values, {"hint_income": income, "cuts": 4})


def test_linear_preparation_transfers_only_native_objective_cut_and_validated_seed(
    monkeypatch, tiny
):
    model = economy(tiny, True)
    model.fingerprint()
    bounds = linear_seed(model)
    problem = model._prepared.clone()
    original = len(problem.model.proto.constraints)

    def prepared(scratch, proto, *args):
        assert not any(row.has_int_prod() for row in scratch.model.proto.constraints)
        # This auxiliary-index cut belongs exclusively to the scratch formulation.
        scratch.model.add(scratch.variables[-1] >= 0)
        return bounds

    monkeypatch.setattr(joint_search, "_strengthen", prepared)
    result = prepare(model, problem, None, 60, 1, perf_counter(), None, None)
    assert result is not None and result.hint_values is not None
    assert result.report["linear_component_cuts"] == 4
    assert result.report["cuts"] == 1
    assert result.report["native_seed_validated"]
    assert len(problem.model.proto.constraints) == original + 1
    assert len(model._prepared.model.proto.constraints) == original
    assert feasible(problem.model, result.hint_values)
    assert objective_value(problem.model, result.hint_values) == bounds.report["hint_income"]


def test_native_prepared_seed_survives_cancellation_before_final_search(monkeypatch, tiny):
    model = economy(tiny, True)
    bounds = linear_seed(model)
    token = Cancellation()

    def prepared(*args):
        token.cancel()
        return deepcopy(bounds)

    monkeypatch.setattr(joint_search, "_strengthen", prepared)
    result = model.optimize(seconds=60, workers=1, native_products=True, cancellation=token)
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["domestic_net_income"] == bounds.report["hint_income"] / 10000
    assert result["solver"]["bound"] == bounds.upper_bound / 10000


@pytest.mark.parametrize(("backend", "native"), [("highs", True), ("cp-sat", "native")])
def test_native_selector_rejects_unsupported_or_ambiguous_choices(tiny, backend, native):
    with pytest.raises(ValueError, match="boolean CP-SAT"):
        economy(tiny).optimize(backend, native_products=native)


def test_native_clone_retains_inserted_constants_and_complete_hint_indices():
    original = NativeCP()
    original.Add(True)
    decision = original.BoolVar("choice")
    original.Maximize(decision)
    assert decision.index > 0
    copied = original.clone()
    assert [v.index for v in copied.variables] == list(range(len(copied.model.proto.variables)))
    values = validated_values(copied, {"choice": 1})
    assert feasible(copied.model, values)
    assert objective_value(copied.model, values) == 1
    with pytest.raises(ValueError, match="nonconstant"):
        validated_values(copied, {})
