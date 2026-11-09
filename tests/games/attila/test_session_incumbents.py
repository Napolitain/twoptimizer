"""Repeat-search candidates remain feasible and never masquerade as new proofs."""

from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import numpy as np
import pytest
from ortools.sat.python import cp_model

import twoptimizer.attila_session as session_module
from games.optimization.cancellation import Cancelled
from games.optimization.competition import BinaryModel, Result
from games.optimization.sparse import SparseConstraints
from games.tw.attila.joint_search import _install_hint
from games.tw.attila.model import ModelSnapshot
from twoptimizer.attila_incumbents import model_identity
from twoptimizer.attila_session import AttilaSession, PreparedAttila, signature
from twoptimizer.models import RunConfig


def prepared_model():
    model = BinaryModel(
        ("a", "b"),
        np.array([10.0, 20.0]),
        np.array([[1.0, 1.0]]),
        np.array([1.0]),
        np.array([1.0]),
        offset=-3,
    )
    return PreparedAttila(ModelSnapshot(model, 0, None), ("p",), ("Province",))


def candidate(*, value=0, bound=17, algorithm="cp-sat", status="FEASIBLE"):
    return Result(
        algorithm,
        status,
        objective=(7, 17)[value],
        bound=bound,
        values=[int(value == 0), int(value == 1)],
    )


def config(algorithm="cp-sat"):
    return RunConfig(game="attila", algorithm=algorithm, workers=1, seconds=1)


def test_retains_best_layout_and_strongest_matching_bound_across_backends(monkeypatch):
    prepared = prepared_model()
    state = AttilaSession()
    responses = iter([candidate(), Result("highs", "UNKNOWN", bound=15)])
    calls = []

    def search(model, algorithm, **options):
        calls.append(options.get("hint_values"))
        return next(responses)

    monkeypatch.setattr(session_module, "solve", search)
    first, _, reused = state.solve(config(), prepared)
    assert not reused
    # Caller-owned output must not alias session-owned candidate data.
    assert first.values is not None
    first.values[:] = [0, 0]
    second, _, reused = state.solve(config("highs"), prepared)
    assert not reused and calls == [None, [1, 0]]
    assert second.status == "FEASIBLE" and second.algorithm == "highs"
    assert second.objective == 7 and second.bound == 15
    assert second.values == [1, 0] and prepared.snapshot.model.feasible(second.values)
    assert second.model_stats["native_status"] == "UNKNOWN"
    assert second.model_stats["warm_start"] == {"validated": True, "retained": True}
    assert state.proofs == {}


def test_keeps_an_improved_candidate_with_previous_stronger_bound(monkeypatch):
    prepared = prepared_model()
    state = AttilaSession(incumbents={signature(prepared.snapshot.model): candidate(bound=20)})
    monkeypatch.setattr(session_module, "solve", lambda *a, **k: candidate(value=1, bound=25))
    result, _, reused = state.solve(config(), prepared)
    assert not reused and result.objective == 17 and result.bound == 20
    assert result.values == [0, 1]
    assert result.model_stats["warm_start"]["retained"] is False


def test_changed_mathematical_model_does_not_reuse_candidate_or_bound(monkeypatch):
    prepared = prepared_model()
    state = AttilaSession(incumbents={signature(prepared.snapshot.model): candidate()})
    prepared.snapshot.model.profit[0] = 50
    calls = []

    def search(model, algorithm, **options):
        calls.append(options.get("hint_values"))
        return Result(algorithm, "UNKNOWN")

    monkeypatch.setattr(session_module, "solve", search)
    result, _, _ = state.solve(config(), prepared)
    assert calls == [None]
    assert result.status == "UNKNOWN" and result.bound is None and result.values is None


def test_model_identity_distinguishes_equal_bytes_with_different_numeric_types():
    model = prepared_model().snapshot.model
    integers = replace(model, profit=np.array([1, 2], dtype=np.int64))
    floating = replace(model, profit=integers.profit.view(np.float64))
    assert integers.profit.tobytes() == floating.profit.tobytes()
    assert signature(integers) != signature(floating)


def test_sparse_cache_identity_never_hashes_implicit_dense_zeros(monkeypatch):
    model = prepared_model().snapshot.model
    sparse = SparseConstraints([([0, 1], [1.0, 1.0])], 2)
    model.matrix = sparse

    def forbidden(*args, **kwargs):
        pytest.fail("A session identity attempted a dense matrix hash")

    monkeypatch.setattr(sparse, "update_hash", forbidden)
    monkeypatch.setattr(sparse, "toarray", forbidden)
    original = model_identity(model)
    sparse.values[0] = 2
    assert model_identity(model) != original
    sparse.values[0] = 1
    assert model_identity(model) == original
    model.upper[0] = 2
    assert model_identity(model) != original


@pytest.mark.parametrize("has_candidate", [False, True])
def test_cancelled_search_only_returns_a_previously_validated_candidate(monkeypatch, has_candidate):
    prepared = prepared_model()
    prior = {signature(prepared.snapshot.model): candidate()} if has_candidate else {}
    state = AttilaSession(incumbents=prior)

    def search(*args, **kwargs):
        raise Cancelled("Cancelled before native search")

    monkeypatch.setattr(session_module, "solve", search)
    if not has_candidate:
        with pytest.raises(Cancelled):
            state.solve(config(), prepared)
        return
    result, _, _ = state.solve(config(), prepared)
    assert result.status == "FEASIBLE" and result.objective == 7 and result.bound == 17
    assert result.model_stats["native_status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "response",
    [Result("cp-sat", "INFEASIBLE"), candidate(value=0, bound=7, status="OPTIMAL")],
)
def test_contradictory_native_proof_is_rejected(monkeypatch, response):
    prepared = prepared_model()
    state = AttilaSession(incumbents={signature(prepared.snapshot.model): candidate(value=1)})
    monkeypatch.setattr(session_module, "solve", lambda *a, **k: response)
    with pytest.raises(RuntimeError, match="proof contradicts"):
        state.solve(config(), prepared)


@pytest.mark.parametrize(
    "corrupt",
    [
        {"values": [1, 1]},
        {"values": [0.5, 0.5]},
        {"objective": 8},
        {"bound": 6},
        {"status": "UNKNOWN"},
    ],
)
def test_cached_candidate_is_rechecked_before_any_native_search(monkeypatch, corrupt):
    prepared = prepared_model()
    stored = replace(candidate(), **corrupt)
    state = AttilaSession(incumbents={signature(prepared.snapshot.model): stored})

    def forbidden(*args, **kwargs):
        pytest.fail("A corrupt incumbent reached native search")

    monkeypatch.setattr(session_module, "solve", forbidden)
    with pytest.raises(ValueError):
        state.solve(config(), prepared)


def test_compact_hint_maps_original_indices_and_prefers_the_better_layout():
    reference = prepared_model().snapshot.model
    model = cp_model.CpModel()
    second = model.new_bool_var("b")
    first = model.new_bool_var("a")
    builder = SimpleNamespace(model=model, variables={0: first, 1: second})
    weaker = SimpleNamespace(hint_values={0: 0, 1: 1}, report={"hint_objective": 7})
    assert _install_hint(builder, reference, weaker, [0, 1], Fraction(1)) == 17
    assert dict(
        zip(model.proto.solution_hint.vars, model.proto.solution_hint.values, strict=True)
    ) == {
        first.index: 0,
        second.index: 1,
    }
    stronger = SimpleNamespace(hint_values={0: 1, 1: 0}, report={"hint_objective": 17})
    _install_hint(builder, reference, stronger, [1, 0], Fraction(1))
    assert dict(
        zip(model.proto.solution_hint.vars, model.proto.solution_hint.values, strict=True)
    ) == {
        first.index: 0,
        second.index: 1,
    }
