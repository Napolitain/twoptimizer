"""Exact compact-component bounds preserve original food and integer products."""

from dataclasses import replace
from itertools import product
from threading import Barrier, Event, Lock, get_ident
from types import SimpleNamespace

import pytest
from ortools.sat.python import cp_model

from games.optimization.cancellation import Cancellation, Cancelled
from games.optimization.native_model import UnsupportedNativeModel, feasible, objective_value
from games.tw.attila import bound_search
from games.tw.attila.bound_search import strengthen
from games.tw.attila.partition import Part, Partition, UnsupportedPartition


def compact_groups(monkeypatch, *, requirement=0, groups=4, negative=False):
    model = cp_model.CpModel()
    fixed = model.new_int_var(2, 2, "fixed_tax")
    variables, parts = [], []
    for group in range(groups):
        choice = model.new_bool_var(f"choice_{group}")
        left = model.new_int_var(1, 3, f"left_{group}")
        right = model.new_int_var(1, 2, f"right_{group}")
        income = model.new_int_var(0, 20, f"income_{group}")
        rows = (
            model.add(left == 1 + 2 * choice).index,
            model.add(right == fixed - 1 + choice).index,
            model.add_multiplication_equality(income, [left, right]).index,
        )
        variables.append((choice, left, right, income))
        parts.append(Part(tuple(variable.index for variable in variables[-1]), rows))
    food = model.add(sum(2 - 3 * row[0] for row in variables) >= requirement).index
    sign = -1 if negative else 1
    model.maximize(sign * sum(row[3] for row in variables) - 3 * fixed + 7)
    decomposition = Partition(tuple(parts), {fixed.index: 2}, (food,), (123,), (), 1)
    monkeypatch.setattr(bound_search, "partition", lambda _: decomposition)
    builder = SimpleNamespace(model=model, variables_for_test=variables, fixed_for_test=fixed)
    return builder, decomposition


def assignments(builder):
    for choices in product((0, 1), repeat=len(builder.variables_for_test)):
        values = {builder.fixed_for_test.index: 2}
        for (choice, left, right, income), selected in zip(
            builder.variables_for_test, choices, strict=True
        ):
            values.update(
                {
                    choice.index: selected,
                    left.index: 1 + 2 * selected,
                    right.index: 1 + selected,
                    income.index: (1 + 2 * selected) * (1 + selected),
                }
            )
        if feasible(builder.model, values):
            yield values, objective_value(builder.model, values)


@pytest.mark.parametrize("negative", [False, True])
def test_native_component_cuts_preserve_every_feasible_original_layout(monkeypatch, negative):
    builder, decomposition = compact_groups(monkeypatch, negative=negative)
    original = builder.model.clone()
    layouts = list(assignments(builder))
    optimum = max(income for _, income in layouts)
    result = strengthen(builder, 5, 0, 1)
    assert result.upper_bound >= optimum
    assert result.report["components"] == result.report["cuts"] == 4
    assert result.report["component_statuses"] == {"OPTIMAL": 4}
    assert result.report["relaxed_rows"] == 1
    assert result.report["relaxed_reference_rows"] == [123]
    assert len(builder.model.proto.constraints) == len(original.proto.constraints) + 4
    assert all(feasible(builder.model, values) for values, _ in layouts)
    assert decomposition.constant == 1  # Offset 7 and fixed objective -6, exactly once.
    assert result.upper_bound == (-3 if negative else 25)
    if negative:
        assert feasible(original, result.hint_values)
        assert result.report["hint_objective"] == -3
    else:
        assert result.hint_values is None  # Relaxed markets violate the original shared food.
        assert result.report["hint_objective"] is None
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.solve(builder.model) == cp_model.OPTIMAL
    assert solver.objective_value == optimum


def test_complete_joint_hint_obeys_original_cross_rows_and_restores_fixed_values(monkeypatch):
    builder, _ = compact_groups(monkeypatch, requirement=-4)
    original = builder.model.clone()
    result = strengthen(builder, 5, 0, 1)
    assert feasible(original, result.hint_values)
    assert result.hint_values[builder.fixed_for_test.index] == 2
    assert result.report["hint_objective"] == objective_value(original, result.hint_values) == 25
    assert result.upper_bound == 25
    assert result.report["status"] == "completed"  # Components do not claim a joint proof.


@pytest.mark.parametrize(
    "observed,component_bound",
    [(None, 20), (6, 6), (6.1, 7), (float("inf"), 20), (float(2**53), 20)],
)
def test_unknown_uses_domain_or_observed_bound_without_default_native_zero(
    monkeypatch, observed, component_bound
):
    builder, _ = compact_groups(monkeypatch)
    layouts = list(assignments(builder))

    def unknown(solver, model, *, on_search, **kwargs):
        if observed is not None:
            on_search(None, observed, 0.1)
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "solve_with_progress", unknown)
    result = strengthen(builder, 5, 0, 1)
    assert result.upper_bound == 1 + 4 * component_bound
    assert result.hint_values is None
    assert result.report["component_statuses"] == {"UNKNOWN": 4}
    assert result.report["cuts"] == (4 if component_bound < 20 else 0)
    assert all(feasible(builder.model, values) for values, _ in layouts)


def test_expired_overall_budget_preserves_last_bound_and_starts_no_more_native_solves(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    clock, allowances = [100.0], []
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])

    def exhaust(solver, model, *, on_search, **kwargs):
        allowances.append(solver.parameters.max_time_in_seconds)
        on_search(None, 6, 0.1)
        clock[0] += 40.1
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "solve_with_progress", exhaust)
    result = strengthen(builder, 100, 7, 1)
    assert allowances == [1]
    assert result.upper_bound == 67 and result.hint_values is None
    assert result.report["status"] == "partial"
    assert result.report["cuts"] == result.report["components_solved"] == 1
    assert result.report["component_statuses"] == {"UNKNOWN": 1, "NOT_RUN": 3}


def test_remaining_time_is_shared_across_every_component_after_extraction(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    clock, allowances, extractions = [100.0], [], []
    original_extract = bound_search.extract
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])

    def extract(*args):
        extractions.append(1)
        if len(extractions) == 4:
            clock[0] += 0.4
        return original_extract(*args)

    def consume_share(solver, model, *, on_search, **kwargs):
        allowance = solver.parameters.max_time_in_seconds
        allowances.append(allowance)
        clock[0] += allowance
        on_search(None, 6, allowance)
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "extract", extract)
    monkeypatch.setattr(bound_search, "solve_with_progress", consume_share)
    result = strengthen(builder, 2, 0, 1)
    assert allowances == pytest.approx([0.5, 0.5, 0.5, 0.1])
    assert result.report["components_solved"] == 4
    assert result.report["component_statuses"] == {"UNKNOWN": 4}
    assert result.upper_bound == 25 and result.hint_values is None
    assert result.report["seconds"] == pytest.approx(2)


def test_unused_component_time_is_redistributed_with_a_one_second_cap(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    clock, allowances = [100.0], []
    monkeypatch.setattr(bound_search, "perf_counter", lambda: clock[0])

    def finish_early(solver, model, *, on_search, **kwargs):
        allowances.append(solver.parameters.max_time_in_seconds)
        clock[0] += 0.2
        on_search(None, 6, 0.2)
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "solve_with_progress", finish_early)
    result = strengthen(builder, 2, 0, 1)
    assert allowances == pytest.approx([0.5, 0.6, 0.8, 1.0])
    assert result.report["components_solved"] == 4
    assert result.report["seconds"] == pytest.approx(0.8)


def test_parallel_components_share_machine_threads_with_one_native_worker_each(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    barrier, lock = Barrier(4), Lock()
    active, peak, native_workers, phases = [0], [0], [], []
    main_thread = get_ident()

    def search(solver, model, *, on_search, **kwargs):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
            native_workers.append(solver.parameters.num_search_workers)
        try:
            barrier.wait(timeout=3)
            on_search(None, 6, 0.1)
            return cp_model.UNKNOWN
        finally:
            with lock:
                active[0] -= 1

    def phase(message):
        assert get_ident() == main_thread
        phases.append(message)

    monkeypatch.setattr(bound_search, "solve_with_progress", search)
    result = strengthen(builder, 5, 0, 4, on_phase=phase)
    assert peak == [4] and active == [0]
    assert native_workers == [1, 1, 1, 1]
    assert result.report["parallelism"] == 4 and result.report["component_workers"] == 1
    assert result.upper_bound == 25 and result.report["components_solved"] == 4
    assert phases[-1] == "Bounding connected province group 4/4"


def test_parallel_budget_is_shared_by_remaining_waves_and_stays_capped(monkeypatch):
    builder, _ = compact_groups(monkeypatch, groups=8)
    allowances = {}
    monkeypatch.setattr(bound_search, "perf_counter", lambda: 100.0)

    def search(solver, model, *, on_search, **kwargs):
        name = next(
            variable.name
            for variable in model.proto.variables
            if variable.name.startswith("choice_")
        )
        allowances[int(name.removeprefix("choice_"))] = solver.parameters.max_time_in_seconds
        on_search(None, 6, 0.1)
        return cp_model.UNKNOWN

    monkeypatch.setattr(bound_search, "solve_with_progress", search)
    result = strengthen(builder, 2, 0, 2)
    assert [allowances[index] for index in range(8)] == pytest.approx(
        [0.5, 0.5, 2 / 3, 2 / 3, 1, 1, 1, 1]
    )
    assert result.report["components_solved"] == 8


def test_parallel_failure_cancels_queued_components_and_leaves_original_unchanged(monkeypatch):
    builder, _ = compact_groups(monkeypatch, groups=8)
    before, started, gate = str(builder.model.proto), [], Event()

    def component(original, part, *args):
        started.append(part.indices)
        if part.indices[0] == 1:
            raise RuntimeError("Unexpected component failure")
        gate.wait(0.05)
        return bound_search._ComponentResult(20, 20)

    monkeypatch.setattr(bound_search, "_component", component)
    with pytest.raises(RuntimeError, match="Unexpected component failure"):
        strengthen(builder, 5, 0, 2)
    assert len(started) < 8
    assert str(builder.model.proto) == before


def test_cancellation_between_groups_keeps_prior_cuts_and_domain_bounds(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    token, phases = Cancellation(), []

    def phase(message):
        phases.append(message)
        if message == "Bounding connected province group 2/4":
            token.cancel()

    result = strengthen(builder, 5, 0, 1, cancellation=token, on_phase=phase)
    assert result.upper_bound == 67 and result.hint_values is None
    assert result.report["component_statuses"] == {"OPTIMAL": 1, "NOT_RUN": 3}
    assert result.report["cuts"] == 1
    assert not any("group 3/4" in message for message in phases)


def test_cancellation_inside_a_native_call_keeps_its_certified_callback_bound(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    token, calls = Cancellation(), []

    def interrupt(solver, model, *, on_search, **kwargs):
        calls.append(1)
        on_search(None, 6, 0.1)
        token.cancel()
        raise Cancelled("Interrupted before a complete native assignment")

    monkeypatch.setattr(bound_search, "solve_with_progress", interrupt)
    result = strengthen(builder, 5, 0, 1, cancellation=token)
    assert len(calls) == 1
    assert result.upper_bound == 67 and result.report["cuts"] == 1
    assert result.hint_values is None


@pytest.mark.parametrize("seconds", [0, -1, float("nan"), float("inf")])
def test_empty_or_invalid_budget_does_not_run_native_search(monkeypatch, seconds):
    builder, _ = compact_groups(monkeypatch)
    before = str(builder.model.proto)

    def unexpected(*args, **kwargs):
        raise AssertionError("Native search must not start")

    monkeypatch.setattr(bound_search, "solve_with_progress", unexpected)
    if seconds == 0:
        result = strengthen(builder, seconds, 0, 1)
        assert result.report["status"] == "skipped" and result.upper_bound is None
    else:
        with pytest.raises(ValueError, match="nonnegative and finite"):
            strengthen(builder, seconds, 0, 1)
    assert str(builder.model.proto) == before


def test_infeasible_component_marks_original_model_without_claiming_joint_optimality(monkeypatch):
    builder, decomposition = compact_groups(monkeypatch)
    choice = builder.variables_for_test[0][0]
    rows = (builder.model.add(choice == 0).index, builder.model.add(choice == 1).index)
    first = decomposition.parts[0]
    decomposition = replace(
        decomposition,
        parts=(replace(first, rows=(*first.rows, *rows)), *decomposition.parts[1:]),
    )
    monkeypatch.setattr(bound_search, "partition", lambda _: decomposition)
    before = len(builder.model.proto.constraints)
    result = strengthen(builder, 5, 0, 1)
    assert result.report["status"] == "infeasible_relaxation"
    assert result.upper_bound is None and result.hint_values is None
    assert len(builder.model.proto.constraints) == before + 1
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    assert solver.solve(builder.model) == cp_model.INFEASIBLE


@pytest.mark.parametrize("unsupported", [UnsupportedPartition, UnsupportedNativeModel])
def test_unsupported_input_skips_benignly_without_changing_original_model(monkeypatch, unsupported):
    builder, _ = compact_groups(monkeypatch)
    before = str(builder.model.proto)

    def reject(*args, **kwargs):
        raise unsupported("Unsupported compact feature")

    monkeypatch.setattr(bound_search, "partition", reject)
    result = strengthen(builder, 5, 0, 1)
    assert result.report["status"] == "skipped"
    assert "Unsupported compact feature" in result.report["reason"]
    assert result.upper_bound is None and result.hint_values is None
    assert str(builder.model.proto) == before


def test_late_unsupported_component_leaves_original_model_unchanged(monkeypatch):
    builder, _ = compact_groups(monkeypatch)
    before, original, calls = str(builder.model.proto), bound_search.extract, []

    def extract(*args):
        calls.append(1)
        if len(calls) == 2:
            raise UnsupportedNativeModel("Unsupported second component")
        return original(*args)

    monkeypatch.setattr(bound_search, "extract", extract)
    result = strengthen(builder, 5, 0, 1)
    assert len(calls) == 2 and result.report["status"] == "skipped"
    assert str(builder.model.proto) == before


@pytest.mark.parametrize("failure", ["invalid_model", "runtime", "candidate", "bound"])
def test_invalid_native_results_and_unexpected_failures_are_not_hidden(monkeypatch, failure):
    builder, _ = compact_groups(monkeypatch)
    before, original = str(builder.model.proto), bound_search.solve_with_progress

    def search(solver, model, **kwargs):
        if failure == "invalid_model":
            return cp_model.MODEL_INVALID
        if failure == "runtime":
            raise RuntimeError("Unexpected native error")
        status = original(solver, model, **kwargs)
        if failure == "bound":
            kwargs["on_search"](None, 5, 0.1)
        return status

    monkeypatch.setattr(bound_search, "solve_with_progress", search)
    if failure == "candidate":
        monkeypatch.setattr(bound_search, "feasible", lambda *args: False)
    with pytest.raises((ValueError, RuntimeError)):
        strengthen(builder, 5, 0, 1)
    assert str(builder.model.proto) == before


def test_single_small_partition_does_not_trigger_component_search(monkeypatch):
    builder, _ = compact_groups(monkeypatch, groups=3)

    def unexpected(*args, **kwargs):
        raise AssertionError("Small partitions must use ordinary search")

    monkeypatch.setattr(bound_search, "solve_with_progress", unexpected)
    result = strengthen(builder, 5, 0, 1)
    assert result.report["status"] == "skipped" and result.upper_bound is None
