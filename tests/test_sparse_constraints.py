"""Sparse storage preserves the exact coefficients, validation and proof hashes."""

import numpy as np
import pytest

from games.tw.competition import BinaryModel, solve
from games.tw.faction_comparison import signature
from games.tw.sparse import SparseConstraints


def test_sparse_duplicate_terms_empty_rows_columns_and_fingerprints():
    sparse = SparseConstraints([([0, 0, 1], [0.25, 0.75, 0]), ([], []), ([1], [-2])], 2)
    dense = np.array([[1.0, 0.0], [0.0, 0.0], [0.0, -2.0]])
    np.testing.assert_array_equal(np.asarray(sparse), dense)
    np.testing.assert_array_equal(sparse @ [1, 1], dense @ [1, 1])
    np.testing.assert_array_equal(sparse[:, 0], dense[:, 0])
    np.testing.assert_array_equal(sparse[:, -1], dense[:, -1])
    np.testing.assert_array_equal(sparse[-1], dense[-1])
    args = (
        ("a", "b"),
        np.array([2.0, 3.0]),
        sparse,
        np.array([-np.inf] * 3),
        np.array([1.0, 0.0, 0.0]),
    )
    model = BinaryModel(*args)
    original = BinaryModel(args[0], args[1], dense, args[3], args[4])
    assert signature(model) == signature(original)
    for invalid in ((slice(None), 2), 3, -4):
        with pytest.raises(IndexError):
            sparse[invalid]


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_sparse_solvers_match_dense_and_uncapped_calls_complete(algorithm):
    dense = np.array([[2.0, 2.0], [1.0, 0.0]])
    sparse = SparseConstraints([([0, 1], [2.0, 2.0]), ([0], [1.0])], 2)
    args = (
        ("a", "b"),
        np.array([10.0, 9.0]),
        sparse,
        np.array([-np.inf, 0.0]),
        np.array([3.0, 1.0]),
    )
    compressed = BinaryModel(*args)
    original = BinaryModel(args[0], args[1], dense, args[3], args[4])
    expected = solve(original, algorithm, seconds=None)
    result = solve(compressed, algorithm, seconds=None)
    assert result.status == expected.status
    assert result.objective == pytest.approx(expected.objective)
    assert result.bound == pytest.approx(expected.bound)
    assert compressed.feasible(result.values, integral=not result.relaxation)


def test_exact_solve_and_hashing_never_materialize_dense_storage(monkeypatch):
    sparse = SparseConstraints([([0, 1], [2.0, 2.0])], 2)
    model = BinaryModel(
        ("a", "b"), np.array([10.0, 9.0]), sparse, np.array([-np.inf]), np.array([3.0])
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Exact solving must not materialize a dense matrix")

    monkeypatch.setattr(sparse, "toarray", forbidden)
    signature(model)
    for algorithm in ("cp-sat", "highs"):
        assert solve(model, algorithm, seconds=None).status == "OPTIMAL"


def test_unlimited_cp_sat_does_not_set_a_time_limit(monkeypatch):
    from ortools.sat.python import cp_model

    observed = []
    original = cp_model.CpSolver.solve

    def capture(self, model, *args, **kwargs):
        observed.append(self.parameters.max_time_in_seconds)
        return original(self, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", capture)
    model = BinaryModel(
        ("a",),
        np.array([1.0]),
        SparseConstraints([([0], [1.0])], 1),
        np.array([0.0]),
        np.array([1.0]),
    )
    assert solve(model, "cp-sat").status == "OPTIMAL"
    assert observed == [float("inf")]
    assert solve(model, "cp-sat", seconds=1).status == "OPTIMAL"
    assert 0 < observed[-1] <= 1
