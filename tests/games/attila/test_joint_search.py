"""Keep Attila's exact native certificates and validate restored compact candidates."""

from dataclasses import replace
from fractions import Fraction
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.optimization.bounds import BoundSearchResult
from games.optimization.cancellation import Cancellation, Cancelled
from games.optimization.competition import BinaryModel
from games.tw.attila import bound_search, joint_search


def alternatives(*, provinces=4, unit=Fraction(3, 20)):
    """Three layouts earn 10, 25 or 30 native units, including an AND bonus."""
    model = cp_model.CpModel()
    support = model.new_bool_var("support")
    choices = [model.new_bool_var(f"choice_{index}") for index in range(3)]
    model.add(support == 1)
    model.add_exactly_one(choices)
    model.maximize(10 * choices[0] + 25 * choices[1] + 30 * choices[2])
    reference = BinaryModel(
        names=("choice_0", "choice_1", "choice_2", "support", "bonus"),
        profit=np.array([10, 20, 30, 0, 5]) * float(unit),
        matrix=np.array(
            [
                [1, 1, 1, 0, 0],
                [0, 0, 0, 1, 0],
                [0, -1, 0, 0, 1],
                [0, 0, 0, -1, 1],
                [0, -1, 0, -1, 1],
            ]
        ),
        lower=np.array([1, 1, -np.inf, -np.inf, -1]),
        upper=np.array([1, 1, 0, 0, np.inf]),
    )
    builder = SimpleNamespace(
        model=model,
        variables={**dict(enumerate(choices)), 3: support},
        products={4: (1, 3)},
        income_groups=1,
        plan=SimpleNamespace(economy=SimpleNamespace(provinces=tuple(range(provinces)))),
    )
    return builder, reference, unit


def prepared_bounds(*, upper=40, seed=1):
    return BoundSearchResult(
        upper,
        None if seed is None else {0: 1, **{i + 1: int(i == seed) for i in range(3)}},
        {"hint_objective": None if seed is None else (10, 25, 30)[seed], "cuts": 0},
    )


def supply_bounds(monkeypatch, bounds):
    monkeypatch.setattr(joint_search, "_strengthen", lambda *args: bounds)


def solve(builder, reference, unit, **options):
    return joint_search.solve(
        builder,
        reference,
        unit,
        **{"seconds": None, "seed": 17, "workers": 1, "started": perf_counter(), **options},
    )


def native_response(monkeypatch, status, *, choice=0, bound=35, observations=()):
    """Control terminal responses without relying on native timing or tied layouts."""
    solver = SimpleNamespace(
        parameters=SimpleNamespace(),
        objective_value=(10, 25, 30)[choice],
        best_objective_bound=bound,
        value=lambda variable: int(variable.index in (0, choice + 1)),
        status_name=lambda value: cp_model.CpSolverStatus(value).name,
    )
    monkeypatch.setattr(joint_search.cp_model, "CpSolver", lambda: solver)

    def run(native, model, observer, bounds, cancellation):
        for objective, upper in observations:
            observer(objective, upper, 0.1)
        return status

    monkeypatch.setattr(joint_search, "_native_solve", run)
    return solver


@pytest.mark.parametrize("outcome", ["unknown", "cancel"])
@pytest.mark.parametrize("upper", [25, 40])
def test_validated_seed_survives_interruption_without_claiming_optimality(
    monkeypatch, outcome, upper
):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(upper=upper))
    token = Cancellation()
    if outcome == "cancel":
        token.cancel()
    else:
        native_response(monkeypatch, cp_model.UNKNOWN, bound=0)
    result = solve(builder, reference, unit, cancellation=token)
    assert result.status == "FEASIBLE" and result.model_stats["native_status"] == "UNKNOWN"
    assert result.values == [0, 1, 0, 1, 1]
    assert result.bound == upper * float(unit)
    assert reference.feasible(result.values)
    assert reference.profit @ result.values == 3.75


@pytest.mark.parametrize("preparation", [None, prepared_bounds(seed=None)])
def test_cancellation_without_a_validated_seed_propagates(monkeypatch, preparation):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, preparation)
    token = Cancellation()
    token.cancel()
    with pytest.raises(Cancelled):
        solve(builder, reference, unit, cancellation=token)


@pytest.mark.parametrize("choice,expected", [(0, [0, 1, 0, 1, 1]), (2, [0, 0, 1, 1, 0])])
def test_best_assignment_restores_original_indices_and_product_auxiliary(
    monkeypatch, choice, expected
):
    builder, reference, unit = alternatives()
    original = tuple(array.copy() for array in (reference.matrix, reference.profit))
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.FEASIBLE, choice=choice)
    result = solve(builder, reference, unit)
    assert result.status == "FEASIBLE" and result.values == expected
    assert result.bound == 5.25
    assert reference.feasible(result.values)
    assert reference.profit @ result.values == max(25, (10, 25, 30)[choice]) * float(unit)
    np.testing.assert_array_equal(reference.matrix, original[0])
    np.testing.assert_array_equal(reference.profit, original[1])


def test_real_native_search_improves_seed_and_proves_the_original_optimum(monkeypatch):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    result = solve(builder, reference, unit)
    assert result.status == "OPTIMAL"
    assert result.values == [0, 0, 1, 1, 0]
    assert reference.profit @ result.values == result.bound == 4.5


@pytest.mark.parametrize("status", [cp_model.INFEASIBLE, cp_model.OPTIMAL])
def test_native_proof_contradicting_a_valid_seed_is_rejected(monkeypatch, status):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, status, bound=10)
    with pytest.raises(AssertionError, match="proof contradicts"):
        solve(builder, reference, unit)


@pytest.mark.parametrize("choice,upper", [(0, 20), (2, 29)])
def test_bound_below_retained_candidate_is_rejected(monkeypatch, choice, upper):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(upper=upper))
    native_response(monkeypatch, cp_model.FEASIBLE, choice=choice)
    with pytest.raises(AssertionError, match="upper bound is below"):
        solve(builder, reference, unit)


@pytest.mark.parametrize("upper", [None, 40])
def test_unknown_without_candidate_never_uses_default_native_zero_bound(monkeypatch, upper):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(upper=upper, seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0)
    result = solve(builder, reference, unit)
    assert result.status == "UNKNOWN" and result.values is None and result.objective is None
    assert result.bound == (None if upper is None else upper * float(unit))


@pytest.mark.parametrize("preparation", ["none", "unbounded", "bounded"])
def test_unknown_retains_the_tightest_genuine_observed_native_bound(monkeypatch, preparation):
    builder, reference, unit = alternatives()
    bounds = (
        None
        if preparation == "none"
        else prepared_bounds(upper=40 if preparation == "bounded" else None, seed=None)
    )
    supply_bounds(monkeypatch, bounds)
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, 35), (None, 37)])
    result = solve(builder, reference, unit)
    assert result.status == "UNKNOWN" and result.values is None
    assert result.bound == 5.25


@pytest.mark.parametrize(
    "observation,expected",
    [(35.1, 36), (-35.1, -35), (float("inf"), 40), (float("nan"), 40), (float(2**53), 40)],
)
def test_observed_native_bound_rounds_outward_and_ignores_unsafe_values(
    monkeypatch, observation, expected
):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, observation)])
    result = solve(builder, reference, unit)
    assert result.bound == expected * float(unit)


def test_large_negative_bound_preserves_exact_native_integer_before_display(monkeypatch):
    builder, reference, unit = alternatives(unit=Fraction(1, 10000))
    bound = -6498266171365257
    selection, certificates = joint_search._selection, []

    def inspect_selection(*args):
        result = selection(*args)
        certificates.append(result[2])
        return result

    monkeypatch.setattr(joint_search, "_selection", inspect_selection)
    supply_bounds(monkeypatch, prepared_bounds(upper=None, seed=None))
    native_response(monkeypatch, cp_model.UNKNOWN, bound=0, observations=[(None, bound)])
    result = solve(builder, reference, unit)
    assert result.status == "UNKNOWN" and result.values is None
    assert result.bound == bound * float(unit)
    # Display floats can alias adjacent native integers; inspect before conversion.
    assert certificates == [bound]


def test_invalid_native_model_is_not_relabelled_as_a_feasible_seed(monkeypatch):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.MODEL_INVALID)
    result = solve(builder, reference, unit)
    assert result.status == "MODEL_INVALID" and result.values is None


def test_infeasible_without_seed_remains_a_proof_without_an_income_bound(monkeypatch):
    builder, reference, unit = alternatives()
    supply_bounds(monkeypatch, prepared_bounds(seed=None))
    native_response(monkeypatch, cp_model.INFEASIBLE)
    result = solve(builder, reference, unit)
    assert result.status == "INFEASIBLE" and result.values is None and result.bound is None


@pytest.mark.parametrize("invalid", ["income", "constraint"])
def test_restored_candidate_is_checked_against_unchanged_reference(monkeypatch, invalid):
    builder, reference, unit = alternatives()
    if invalid == "income":
        reference = replace(reference, offset=1)
    else:
        reference = replace(
            reference,
            matrix=np.vstack([reference.matrix, [0, 1, 0, 0, 0]]),
            lower=np.append(reference.lower, 0),
            upper=np.append(reference.upper, 0),
        )
    supply_bounds(monkeypatch, prepared_bounds())
    native_response(monkeypatch, cp_model.UNKNOWN)
    message = "income objectives disagree" if invalid == "income" else "reference constraints"
    with pytest.raises(AssertionError, match=message):
        solve(builder, reference, unit)


def test_progress_converts_fraction_units_and_reports_post_preparation_model(monkeypatch):
    builder, reference, unit = alternatives()
    original_constraints = len(builder.model.proto.constraints)

    def strengthen(builder, *args):
        builder.model.add(sum(builder.variables[index] for index in range(3)) <= 1)
        return prepared_bounds()

    monkeypatch.setattr(joint_search, "_strengthen", strengthen)
    native_response(monkeypatch, cp_model.FEASIBLE, observations=[(None, 50), (10, 35)])
    observations, models, phases = [], [], []
    result = solve(
        builder,
        reference,
        unit,
        on_search=lambda *event: observations.append(event),
        on_model=models.append,
        on_phase=phases.append,
    )
    assert observations == [(3.75, 6.0, 0.1), (3.75, 5.25, 0.1)]
    assert len(models) == 1 and models[0] == result.model_stats
    assert models[0]["formulation"] == "factored_income"
    assert models[0]["variables"] == 4 and models[0]["reference_variables"] == 5
    assert models[0]["constraints"] == original_constraints + 1
    assert models[0]["reference_constraints"] == 5 and models[0]["income_groups"] == 1
    assert phases[-1] == "Searching the complete joint model"


def test_native_allowance_deducts_conversion_and_bound_preparation(monkeypatch):
    builder, reference, unit = alternatives()
    clock = [100.0]
    monkeypatch.setattr(joint_search, "perf_counter", lambda: clock[0])

    def strengthen(*args):
        clock[0] += 6.0
        return prepared_bounds(seed=None)

    monkeypatch.setattr(joint_search, "_strengthen", strengthen)
    native = native_response(monkeypatch, cp_model.OPTIMAL, choice=2, bound=30)
    result = solve(builder, reference, unit, seconds=30, started=90.0)
    assert native.parameters.max_time_in_seconds == 14
    assert native.parameters.num_search_workers == 1 and native.parameters.random_seed == 17
    assert result.timings == {
        "model_conversion_seconds": 10,
        "bound_strengthening_seconds": 6,
        "search_seconds": 0,
    }


@pytest.mark.parametrize(
    "provinces,seconds,elapsed", [(3, None, 0), (4, 4, 0), (4, 44, 0), (4, 60, 16)]
)
def test_small_or_short_search_skips_preparation(monkeypatch, provinces, seconds, elapsed):
    builder, reference, unit = alternatives(provinces=provinces)
    monkeypatch.setattr(joint_search, "perf_counter", lambda: 100.0)
    original = str(builder.model.proto)

    def unexpected(*args, **kwargs):
        raise AssertionError("Bound preparation should be skipped")

    monkeypatch.setattr(bound_search, "strengthen", unexpected)
    phases = []
    result = solve(
        builder, reference, unit, seconds=seconds, started=100.0 - elapsed, on_phase=phases.append
    )
    assert result.status == "OPTIMAL" and result.bound == 4.5
    assert result.values == [0, 0, 1, 1, 0]
    assert "joint_bound_search" not in result.model_stats
    assert str(builder.model.proto) == original
    assert phases == ["Solving and validating"]


@pytest.mark.parametrize(
    "seconds,elapsed,expected", [(None, 0, 40), (60, 10, 100 / 3), (55, 10, 30)]
)
def test_preparation_uses_capped_fraction_of_remaining_budget(
    monkeypatch, seconds, elapsed, expected
):
    builder, reference, unit = alternatives()
    captured = []
    monkeypatch.setattr(joint_search, "perf_counter", lambda: 100.0)

    def strengthen(builder, allowance, seed, workers, **kwargs):
        captured.append((allowance, seed, workers))
        return prepared_bounds()

    monkeypatch.setattr(bound_search, "strengthen", strengthen)
    native_response(monkeypatch, cp_model.OPTIMAL, choice=2, bound=30)
    solve(builder, reference, unit, seconds=seconds, started=100.0 - elapsed)
    assert captured == [(pytest.approx(expected), 17, 1)]
