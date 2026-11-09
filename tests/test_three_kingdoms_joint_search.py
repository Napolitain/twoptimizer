"""Joint bounds remain optimistic; reusable layouts satisfy the original economy."""

from copy import deepcopy
from dataclasses import replace
from itertools import product

import pytest
from ortools.linear_solver import linear_solver_pb2, pywraplp
from ortools.sat.python import cp_model

from games.tw.cancellation import Cancellation
from games.tw.highs_backend import solve_highs
from games.tw.three_kingdoms import joint_bounds, optimization, preparation
from games.tw.three_kingdoms.incumbent import layout_from
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.scenario import Commandery, Scenario

FACTION = "3k_main_faction_cao_cao"
YINGCHUAN = "3k_main_province_yingchuan"


@pytest.fixture
def local_optimum():
    model = Economy(Scenario(FACTION, (Commandery(YINGCHUAN, city_level=None),)))
    report = model.optimize(seconds=5, workers=1)
    assert report["solver"]["status"] == "OPTIMAL"
    return model, report


def _unknown(*args, **kwargs):
    return {
        "algorithm": "cp-sat",
        "status": "UNKNOWN",
        "objective": None,
        "bound": None,
        "values": None,
        "timings": {},
    }


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_cancelled_run_retains_validated_incumbent_and_matching_bound(local_optimum, algorithm):
    model, previous = local_optimum
    cancellation = Cancellation()
    cancellation.cancel()
    result = model.optimize(
        algorithm, seconds=5, workers=1, incumbent=previous, cancellation=cancellation
    )
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["solver"]["seed_reused"] is True
    assert result["domestic_income"] == previous["domestic_income"]
    assert result["solver"]["bound"] == previous["solver"]["bound"]
    assert model.evaluate(layout_from(result))["domestic_income"] == result["domestic_income"]


def test_unknown_keeps_seed_without_fabricating_optimality(local_optimum, monkeypatch):
    model, previous = local_optimum
    observed = []
    monkeypatch.setattr(optimization, "cpsat", _unknown)
    result = model.optimize(
        seconds=5, workers=1, incumbent=previous, on_search=lambda *event: observed.append(event)
    )
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["bound"] == result["domestic_income"]
    assert observed[0][:2] == (previous["domestic_income"], previous["solver"]["bound"])


def test_changed_model_does_not_reuse_old_upper_bound(local_optimum, monkeypatch):
    model, previous = local_optimum
    changed = Economy(replace(model.scenario, external_food=20))
    monkeypatch.setattr(optimization, "cpsat", _unknown)
    result = changed.optimize(seconds=5, workers=1, incumbent=previous)
    assert result["model_fingerprint"] != previous["model_fingerprint"]
    assert result["solver"]["bound"] is None
    assert result["domestic_income"] == previous["domestic_income"]


def test_invalid_seed_cannot_survive_independent_evaluation(local_optimum):
    model, previous = local_optimum
    invalid = deepcopy(previous)
    invalid["domestic_income"] += 100
    with pytest.raises(ValueError, match="independent economics"):
        model.optimize(seconds=5, workers=1, incumbent=invalid)
    impossible = Economy(replace(model.scenario, external_food=-1000))
    with pytest.raises(ValueError, match="food deficit"):
        impossible.optimize(seconds=5, workers=1, incumbent=previous)


def test_native_infeasible_cannot_override_a_valid_layout(local_optimum, monkeypatch):
    model, previous = local_optimum
    monkeypatch.setattr(
        optimization,
        "cpsat",
        lambda *a, **kw: {
            **_unknown(),
            "status": "INFEASIBLE",
        },
    )
    with pytest.raises(AssertionError, match="Native proof contradicts"):
        model.optimize(seconds=5, workers=1, incumbent=previous)


def _coupled_proto():
    solver = pywraplp.Solver.CreateSolver("SAT")
    x, y = solver.BoolVar("income"), solver.BoolVar("food")
    fixed = solver.IntVar(2, 2, "fixed_food")
    supplier = solver.BoolVar("resource_supplier")
    solver.Add(fixed - 2 * x + 3 * y >= 3, "__realm_food")
    solver.Add(x <= supplier, "__resource:eligibility")
    solver.Maximize(7 + 10 * x - 3 * y - supplier)
    proto = linear_solver_pb2.MPModelProto()
    solver.ExportModelToProto(proto)
    return proto


def _evaluate_proto(proto, values):
    return all(
        row.lower_bound
        <= sum(values[i] * c for i, c in zip(row.var_index, row.coefficient, strict=True))
        <= row.upper_bound
        for row in proto.constraint
    )


@pytest.mark.parametrize("price", [0, 1, 3, 100])
def test_component_bound_contains_exhaustive_joint_optimum_and_preserves_rows(monkeypatch, price):
    proto = _coupled_proto()
    before = proto.SerializeToString()
    monkeypatch.setattr(joint_bounds, "_price", lambda *args: price)
    strengthened, bound, report = joint_bounds.strengthen(proto, 5, 1)
    feasible = [
        (x, y, 2, z)
        for x, y, z in product((0, 1), repeat=3)
        if _evaluate_proto(proto, (x, y, 2, z))
    ]
    incomes = [7 + 10 * x - 3 * y - z for x, y, _, z in feasible]
    assert max(incomes) == 13
    assert bound >= max(incomes)
    assert report["components"] == 3
    assert report["relaxed_rows"] == 2
    assert proto.SerializeToString() == before
    assert all(_evaluate_proto(strengthened, values) for values in feasible)
    assert all(a == b for a, b in zip(proto.constraint, strengthened.constraint, strict=False))
    native, _ = optimization.native_model(strengthened)
    backend = cp_model.CpSolver()
    backend.parameters.num_search_workers = 1
    assert backend.solve(native) == cp_model.OPTIMAL
    assert backend.objective_value == 13
    assert len({row.name for row in strengthened.constraint}) == len(strengthened.constraint)
    alternative = solve_highs(strengthened, seconds=5, workers=1)
    assert alternative["status"] == "OPTIMAL"
    assert alternative["objective"] == 13


def test_unfinished_components_keep_safe_domain_bounds(monkeypatch):
    proto = _coupled_proto()
    monkeypatch.setattr(joint_bounds, "_price", lambda *args: 3)
    monkeypatch.setattr(joint_bounds, "_stopped", lambda *args: True)
    # Exercise the lower-level component loop, with the whole allowance gone.
    target = linear_solver_pb2.MPModelProto()
    target.CopyFrom(proto)
    _, bound, report = joint_bounds._strengthen(
        proto, target, (0, 1), joint_bounds.Budget(0), 1, None, None
    )
    assert bound >= 13
    assert report["component_statuses"] == {"NOT_RUN": 3}


def test_local_preparation_keeps_global_requirement_out_of_each_local_solve(
    local_optimum, monkeypatch
):
    _, report = local_optimum
    observed = []
    options = Scenario(
        FACTION,
        (Commandery(YINGCHUAN, city_level=None),),
        required_buildings=("3k_district_market_inn_3",),
        external_food=7,
    )
    model = Economy(options)

    def solve(local, **kwargs):
        observed.append(local.scenario)
        return report

    monkeypatch.setattr(Economy, "optimize", solve)
    seed, completed = preparation._local_seed(model, joint_bounds.Budget(1), None, None)
    assert completed == 1
    assert observed[0].required_buildings == ()
    assert observed[0].external_food == 0
    if seed is not None:
        assert model.evaluate(layout_from(seed))["domestic_income"] == seed["domestic_income"]


def test_local_failure_is_not_a_joint_infeasibility_proof(local_optimum, monkeypatch):
    model, _ = local_optimum
    monkeypatch.setattr(Economy, "optimize", lambda *a, **kw: {"solver": {"status": "INFEASIBLE"}})
    seed, completed = preparation._local_seed(model, joint_bounds.Budget(1), None, None)
    assert seed is None
    assert completed == 0


def test_preparation_is_bounded_and_skips_small_or_short_cases(local_optimum):
    model, _ = local_optimum
    assert preparation.allowance(model, None) == 0
    model.provinces = dict.fromkeys(range(4))
    assert preparation.allowance(model, 5) == 0
    assert preparation.allowance(model, 15) == 0
    assert preparation.allowance(model, 20) == 12
    assert preparation.allowance(model, None) == 30


def test_cached_independent_layouts_seed_short_joint_search_without_reusing_local_bounds(
    local_optimum, monkeypatch
):
    first, first_report = local_optimum
    other = Commandery("3k_main_province_chenjun", city_level=None)
    second = Economy(replace(first.scenario, commanderies=(other,)))
    second_report = second.optimize(seconds=5, workers=1)
    joint = Economy(replace(first.scenario, commanderies=(*first.scenario.commanderies, other)))
    monkeypatch.setattr(optimization, "cpsat", _unknown)
    first_report["solver"]["bound"] = 0  # Local certificates do not apply to the joint model.
    result = joint.optimize(seconds=0.1, workers=1, local_incumbents=(first_report, second_report))
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["solver"]["bound"] is None
    assert result["solver"]["joint_bound_search"]["cached_local_cases"] == 2
    assert joint.evaluate(layout_from(result))["domestic_income"] == result["domestic_income"]


def test_cached_layout_failing_joint_requirement_is_discarded(local_optimum, monkeypatch):
    model, previous = local_optimum
    changed = Economy(replace(model.scenario, external_food=-1000))
    monkeypatch.setattr(optimization, "cpsat", _unknown)
    result = changed.optimize(seconds=0.1, workers=1, local_incumbents=(previous,))
    assert result["solver"]["status"] == "UNKNOWN"
    assert "commanderies" not in result


def test_cached_layout_can_be_retained_if_cancel_precedes_native_search(local_optimum):
    model, previous = local_optimum
    cancelled = Cancellation()
    cancelled.cancel()
    result = model.optimize(
        seconds=0.1, workers=1, local_incumbents=(previous,), cancellation=cancelled
    )
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["domestic_income"] == previous["domestic_income"]
    assert result["solver"]["bound"] is None


def test_unmarked_resource_constraint_stays_in_bound_components(monkeypatch):
    proto = _coupled_proto()
    proto.constraint[1].name = "mandatory_requirement"
    monkeypatch.setattr(joint_bounds, "_price", lambda *args: 3)
    _, bound, report = joint_bounds.strengthen(proto, 5, 1)
    assert report["relaxed_rows"] == 1
    assert report["components"] == 2
    assert report["largest_component_variables"] == 2
    assert bound >= 13


def test_failed_bound_partition_is_not_reported_as_joint_infeasibility():
    proto = _coupled_proto()
    impossible = proto.constraint.add(name="impossible_local_rule", lower_bound=2)
    impossible.upper_bound = float("inf")
    impossible.var_index.append(0)
    impossible.coefficient.append(1)
    result, bound, report = joint_bounds.strengthen(proto, 5, 1)
    assert result.SerializeToString() == proto.SerializeToString()
    assert bound is None
    assert report["status"] == "skipped"


def test_unfinished_price_estimate_uses_unit_aware_positive_fallback(monkeypatch):
    proto = _coupled_proto()
    monkeypatch.setattr(
        joint_bounds,
        "estimate_lower_bound_price",
        lambda *a, **kw: {
            "status": "UNKNOWN",
            "price": None,
        },
    )
    budget = joint_bounds.Budget(5)
    price = joint_bounds._price(proto, 0, budget, 1, None)
    assert price > 0
    assert budget.price_report["price_source"] == "objective_food_domain_ratio"
    assert budget.price_report["fallback_price"] == price
    for variable in proto.variable:
        variable.objective_coefficient *= 10
    assert joint_bounds._fallback_price(proto, 0) >= 10 * price


def test_valid_zero_food_price_is_preserved(monkeypatch):
    monkeypatch.setattr(
        joint_bounds,
        "estimate_lower_bound_price",
        lambda *a, **kw: {
            "status": "OPTIMAL",
            "price": 0,
        },
    )
    budget = joint_bounds.Budget(5)
    assert joint_bounds._price(_coupled_proto(), 0, budget, 1, None) == 0
    assert budget.price_report["price_source"] == "continuous_relaxation"


def test_seed_only_policy_keeps_original_model_without_component_cuts(local_optimum, monkeypatch):
    model, seed = local_optimum
    proto = model.compile()
    monkeypatch.setattr(preparation, "allowance", lambda *a: 10)

    def unexpected_bounds(*args, **kwargs):
        raise AssertionError("Seed-only policy must not run component bounds")

    monkeypatch.setattr(preparation, "strengthen", unexpected_bounds)
    prepared, retained, bound, report = preparation.prepare(
        model, proto, 30, 1, seed, strengthen_bounds=False
    )
    assert prepared is proto
    assert retained is seed
    assert bound is None
    assert report["status"] == "seed_only"
