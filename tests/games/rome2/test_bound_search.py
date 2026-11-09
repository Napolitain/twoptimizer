"""Priced component cuts preserve every feasible joint layout and income bound."""

from itertools import product
from math import inf

import pytest
from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.optimization.budget import Budget
from games.optimization.cancellation import Cancellation, Cancelled
from games.optimization.cp_backend import NativeCP
from games.optimization.exact import integer_upper_bound
from games.optimization.linear_components import UnsupportedDecomposition
from games.tw.rome2 import bound_search
from games.tw.rome2.bound_search import strengthen


def holdings(*, groups=4, offset=0, fixed=False, requirement=0, profits=(1, 5)):
    proto = linear_solver_pb2.MPModelProto(maximize=True, objective_offset=offset)
    food_indices, food_coefficients = [], []
    for group in range(groups):
        for kind, profit, food in zip(("farm", "market"), profits, (2, -1), strict=True):
            index = len(proto.variable)
            proto.variable.add(
                name=f"{group}:{kind}",
                lower_bound=0,
                upper_bound=1,
                is_integer=True,
                objective_coefficient=profit,
            )
            food_indices.append(index)
            food_coefficients.append(food)
        proto.constraint.add(
            lower_bound=1,
            upper_bound=1,
            var_index=[2 * group, 2 * group + 1],
            coefficient=[1, 1],
        )
    if fixed:
        food_indices.append(len(proto.variable))
        food_coefficients.append(4)
        proto.variable.add(
            name="fixed",
            lower_bound=2,
            upper_bound=2,
            is_integer=True,
            objective_coefficient=-3,
        )
    food_row = len(proto.constraint)
    proto.constraint.add(
        name="__realm_food",
        lower_bound=requirement,
        upper_bound=inf,
        var_index=food_indices,
        coefficient=food_coefficients,
    )
    return proto, food_row


def feasible_layouts(proto):
    domains = [range(int(v.lower_bound), int(v.upper_bound) + 1) for v in proto.variable]
    for values in product(*domains):
        if all(
            row.lower_bound
            <= sum(c * values[i] for i, c in zip(row.var_index, row.coefficient, strict=True))
            <= row.upper_bound
            for row in proto.constraint
        ):
            objective = int(proto.objective_offset) + sum(
                int(v.objective_coefficient) * value
                for v, value in zip(proto.variable, values, strict=True)
            )
            yield values, objective


def assert_cuts_preserve_layouts(problem, first_cut, layouts):
    for cut in list(problem.model.proto.constraints)[first_cut:]:
        assert cut.has_linear()
        row = cut.linear
        domain = list(row.domain)
        for values, _ in layouts:
            total = sum(c * values[i] for i, c in zip(row.vars, row.coeffs, strict=True))
            assert any(
                lower <= total <= upper
                for lower, upper in zip(domain[::2], domain[1::2], strict=True)
            )


def price_stub(monkeypatch, price):
    monkeypatch.setattr(
        bound_search,
        "estimate_lower_bound_price",
        lambda *args, **kwargs: {"price": price, "status": "OPTIMAL", "seconds": 0},
    )


@pytest.mark.parametrize("price", [0, 1, 2, None])
@pytest.mark.parametrize(
    "offset,fixed,requirement,profits", [(0, False, 0, (1, 5)), (7, True, 10, (-2, 5))]
)
def test_every_original_layout_survives_priced_cuts_and_bounds(
    monkeypatch, price, offset, fixed, requirement, profits
):
    price_stub(monkeypatch, price)
    proto, food_row = holdings(offset=offset, fixed=fixed, requirement=requirement, profits=profits)
    original = proto.SerializeToString()
    problem = NativeCP.from_linear(proto)
    first_cut = len(problem.model.proto.constraints)
    layouts = list(feasible_layouts(proto))
    optimum = max(income for _, income in layouts)
    result = strengthen(problem, proto, food_row, 5, 1)
    assert result.upper_bound is not None and result.upper_bound >= optimum
    assert result.report["components"] == result.report["cuts"] == 4
    assert result.report["component_statuses"] == {"OPTIMAL": 4}
    assert_cuts_preserve_layouts(problem, first_cut, layouts)
    if result.hint_values is not None:
        selected = tuple(result.hint_values[i] for i in range(len(proto.variable)))
        assert (selected, result.report["hint_income"]) in layouts
    assert proto.SerializeToString() == original
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.solve(problem.model) == cp_model.OPTIMAL
    assert solver.objective_value == optimum


def test_real_lp_price_and_component_search_preserve_food_and_a_certified_upper_bound():
    proto, food_row = holdings(profits=(10, 50))
    problem = NativeCP.from_linear(proto)
    result = strengthen(problem, proto, food_row, 5, 1)
    price_solver = result.report["price_solver"]
    assert isinstance(price_solver, dict)
    assert price_solver["status"] == "OPTIMAL"
    assert isinstance(result.report["food_price"], int) and result.report["food_price"] >= 0
    assert result.upper_bound is not None
    assert max(income for _, income in feasible_layouts(proto)) <= result.upper_bound


def test_infeasible_assembled_components_are_never_offered_as_joint_hints(monkeypatch):
    price_stub(monkeypatch, 0)
    proto, food_row = holdings()
    result = strengthen(NativeCP.from_linear(proto), proto, food_row, 5, 1)
    # Every relaxed component picks its market. Their combined food is -4.
    assert result.report["component_statuses"] == {"OPTIMAL": 4}
    assert result.hint_values is None and result.report["hint_income"] is None
    assert result.upper_bound == 20


@pytest.mark.parametrize("observed,expected", [(None, 20), (14.0, 14), (14.1, 15), (inf, 20)])
def test_unknown_uses_only_observed_finite_outward_bounds(monkeypatch, observed, expected):
    proto = linear_solver_pb2.MPModelProto(maximize=True)
    proto.variable.add(lower_bound=0, upper_bound=10, is_integer=True, objective_coefficient=2)
    proto.constraint.add(lower_bound=-inf, upper_bound=7, var_index=[0], coefficient=[1])

    def unknown(solver, model, *, cancellation, on_search):
        # UNKNOWN response fields are unset/default zero; only an actual bound
        # notification is evidence. The helper must not query native defaults.
        if observed is not None:
            on_search(None, observed, 0)
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "solve_with_progress", unknown)
    result = bound_search._solve_component(
        proto, Budget(5, clock=lambda: bound_search.perf_counter()), 1, None
    )
    assert result.status == "UNKNOWN" and result.values is None
    assert result.bound == expected


@pytest.mark.parametrize("value", [2**53, -(2**53), float("nan")])
def test_unsafe_float_bounds_are_ignored(value):
    assert integer_upper_bound(value) is None


def test_expired_preparation_never_starts_lp_or_native_search(monkeypatch):
    proto, food_row = holdings()
    clock = [0.0]
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])
    decompose = bound_search.decompose

    def slow_decomposition(*args, **kwargs):
        result = decompose(*args, **kwargs)
        clock[0] = 6.0
        return result

    def unexpected(*args, **kwargs):
        pytest.fail("Expired preparation must not begin another native search")

    monkeypatch.setattr(bound_search, "decompose", slow_decomposition)
    monkeypatch.setattr(bound_search, "estimate_lower_bound_price", unexpected)
    monkeypatch.setattr(bound_search, "solve_with_progress", unexpected)
    result = strengthen(NativeCP.from_linear(proto), proto, food_row, 5, 1)
    assert result.report["component_statuses"] == {"NOT_RUN": 4}
    assert result.upper_bound == 24 and result.hint_values is None


def test_component_conversion_counts_against_its_remaining_allowance(monkeypatch):
    proto, _ = holdings(groups=1)
    clock = [0.0]
    budget = Budget(5, clock=lambda: bound_search.perf_counter())
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])
    budget.started = 0.0
    convert = NativeCP.from_linear

    def slow_conversion(proto):
        result = convert(proto)
        clock[0] = 6.0
        return result

    monkeypatch.setattr(NativeCP, "from_linear", slow_conversion)
    result = bound_search._solve_component(proto, budget, 1, None)
    assert result.status == "NOT_RUN" and result.values is None


@pytest.mark.parametrize("seconds,expected_price_allowance", [(3, 1), (40, 10)])
def test_lp_and_component_limits_share_the_same_stage_allowance(
    monkeypatch, seconds, expected_price_allowance
):
    proto, food_row = holdings()
    clock, native_limits = [0.0], []
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])

    def price(proto, row, allowance, workers, *, cancellation):
        assert allowance == expected_price_allowance and workers == 7
        clock[0] += allowance
        return {"price": 0, "status": "UNKNOWN"}

    def unknown(solver, model, *, cancellation, on_search):
        allowance = solver.parameters.max_time_in_seconds
        assert 0 < allowance <= min(1, seconds - clock[0])
        assert solver.parameters.num_search_workers == 7
        assert solver.parameters.linearization_level == 2
        native_limits.append(allowance)
        clock[0] += allowance
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "estimate_lower_bound_price", price)
    monkeypatch.setattr(bound_search, "solve_with_progress", unknown)
    result = strengthen(NativeCP.from_linear(proto), proto, food_row, seconds, 7)
    assert native_limits and clock[0] <= seconds
    assert result.hint_values is None and result.upper_bound == 24


def test_phase_notification_that_exhausts_budget_does_not_start_lp(monkeypatch):
    proto, food_row = holdings()
    clock = [0.0]
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])

    def phase(message):
        if message.startswith("Estimating"):
            clock[0] = 5.0

    def unexpected(*args, **kwargs):
        pytest.fail("Do not start pricing after the stage allowance expires")

    monkeypatch.setattr(bound_search, "estimate_lower_bound_price", unexpected)
    result = strengthen(NativeCP.from_linear(proto), proto, food_row, 5, 1, on_phase=phase)
    price_solver = result.report["price_solver"]
    assert isinstance(price_solver, dict)
    assert price_solver["status"] == "NOT_RUN"
    assert result.report["component_statuses"] == {"NOT_RUN": 4}


def test_cancelled_preparation_does_not_expose_a_local_candidate(monkeypatch):
    price_stub(monkeypatch, 2)
    proto, food_row = holdings()
    cancellation = Cancellation()
    solve = bound_search.solve_with_progress
    phases = []

    def cancel_after_first(*args, **kwargs):
        status = solve(*args, **kwargs)
        cancellation.cancel()
        return status

    monkeypatch.setattr(bound_search, "solve_with_progress", cancel_after_first)
    with pytest.raises(Cancelled):
        strengthen(
            NativeCP.from_linear(proto),
            proto,
            food_row,
            5,
            1,
            cancellation=cancellation,
            on_phase=phases.append,
        )
    assert all(isinstance(event, str) for event in phases)


def test_late_cancel_keeps_a_complete_independently_validated_joint_hint(monkeypatch):
    price_stub(monkeypatch, 2)
    proto, food_row = holdings()
    cancellation = Cancellation()
    solve = bound_search.solve_with_progress
    calls = []

    def cancel_after_last(*args, **kwargs):
        status = solve(*args, **kwargs)
        calls.append(True)
        if len(calls) == 4:
            cancellation.cancel()
        return status

    monkeypatch.setattr(bound_search, "solve_with_progress", cancel_after_last)
    result = strengthen(
        NativeCP.from_linear(proto), proto, food_row, 5, 1, cancellation=cancellation
    )
    assert cancellation.requested
    assert result.hint_values is not None and result.report["hint_income"] == 4


def test_small_or_unsupported_models_skip_optional_preparation(monkeypatch):
    proto, food_row = holdings(groups=3)
    problem = NativeCP.from_linear(proto)
    initial = len(problem.model.proto.constraints)
    result = strengthen(problem, proto, food_row, 5, 1)
    assert result.report["status"] == "skipped"

    def unsupported(*args, **kwargs):
        raise UnsupportedDecomposition("Unsupported test structure")

    monkeypatch.setattr(bound_search, "decompose", unsupported)
    result = strengthen(problem, proto, food_row, 5, 1)
    assert result.report["reason"] == "Unsupported test structure"
    assert result.upper_bound is result.hint_values is None
    assert len(problem.model.proto.constraints) == initial


def test_infeasible_integer_component_proves_the_joint_model_infeasible(monkeypatch):
    price_stub(monkeypatch, 0)
    proto, food_row = holdings()
    third = len(proto.variable)
    proto.variable.add(lower_bound=0, upper_bound=1, is_integer=True)
    # Three binary variables with pair sums one have no integer assignment.
    proto.constraint.add(lower_bound=1, upper_bound=1, var_index=[0, third], coefficient=[1, 1])
    proto.constraint.add(lower_bound=1, upper_bound=1, var_index=[1, third], coefficient=[1, 1])
    problem = NativeCP.from_linear(proto)
    result = strengthen(problem, proto, food_row, 5, 1)
    assert result.report["status"] == "infeasible_relaxation"
    assert result.upper_bound is result.hint_values is None
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.solve(problem.model) == cp_model.INFEASIBLE
