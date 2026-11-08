"""HiGHS preparation cancellation and preservation of completed native results."""

from contextlib import contextmanager

import pytest
from ortools.linear_solver import linear_solver_pb2

from games.tw import highs_backend
from games.tw.cancellation import Cancellation, Cancelled


def binary_model():
    proto = linear_solver_pb2.MPModelProto(maximize=True, objective_offset=0.25)
    proto.variable.add(
        name="x", lower_bound=0, upper_bound=1, is_integer=True, objective_coefficient=2
    )
    return proto


def unexpected_search(*args, **kwargs):
    pytest.fail("Cancelled preparation must not start a native solve")


def test_precancelled_highs_skips_native_preparation(monkeypatch):
    cancellation = Cancellation()
    cancellation.cancel()
    monkeypatch.setattr(highs_backend, "_native_model", unexpected_search)
    with pytest.raises(Cancelled):
        highs_backend.solve_highs(binary_model(), workers=1, cancellation=cancellation)


def test_highs_rechecks_cancellation_after_scheduler_lock(monkeypatch):
    cancellation = Cancellation()

    @contextmanager
    def acquired_after_cancellation():
        cancellation.cancel()
        yield

    monkeypatch.setattr(highs_backend, "_SCHEDULER", acquired_after_cancellation())
    monkeypatch.setattr(highs_backend, "_native_model", unexpected_search)
    with pytest.raises(Cancelled):
        highs_backend.solve_highs(binary_model(), workers=1, cancellation=cancellation)


def test_cancel_during_highs_conversion_skips_native_search(monkeypatch):
    cancellation = Cancellation()
    convert = highs_backend._native_model

    def cancel_after_conversion(proto):
        model = convert(proto)
        cancellation.cancel()
        return model

    monkeypatch.setattr(highs_backend, "_native_model", cancel_after_conversion)
    monkeypatch.setattr(highs_backend.mathopt, "solve", unexpected_search)
    with pytest.raises(Cancelled):
        highs_backend.solve_highs(binary_model(), workers=1, cancellation=cancellation)


def test_highs_with_unrequested_token_preserves_native_optimum():
    cancellation = Cancellation()
    report = highs_backend.solve_highs(binary_model(), workers=1, cancellation=cancellation)
    assert report["status"] == "OPTIMAL"
    assert report["values"] == [1]
    assert report["objective"] == report["bound"] == 2.25
    assert not cancellation.requested


def test_late_highs_cancellation_keeps_validated_solution_and_bound(monkeypatch):
    cancellation = Cancellation()
    solve = highs_backend.mathopt.solve

    def cancel_before_validation(model, solver, *, params, model_params):
        result = solve(model, solver, params=params, model_params=model_params)
        cancellation.cancel()
        return result

    monkeypatch.setattr(highs_backend.mathopt, "solve", cancel_before_validation)
    report = highs_backend.solve_highs(binary_model(), workers=1, cancellation=cancellation)
    assert cancellation.requested
    assert report["status"] == "OPTIMAL"
    assert report["values"] == [1]
    assert report["objective"] == report["bound"] == 2.25
