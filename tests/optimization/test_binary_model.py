"""Check solver results against enumeration and independent feasibility validation."""

from itertools import product

import numpy as np
import pytest

from games.optimization.competition import ALGORITHMS, BinaryModel, integer_row, solve
from games.tw.attila.comparison import ComparisonOptions, compare_model


def model(profit, matrix, lower, upper):
    return BinaryModel(
        tuple(f"x{i}" for i in range(len(profit))),
        np.array(profit, dtype=float),
        np.array(matrix, dtype=float),
        np.array(lower, dtype=float),
        np.array(upper, dtype=float),
    )


def enumerate_optimum(problem):
    return max(
        (
            problem.profit @ values
            for values in product((0, 1), repeat=len(problem.names))
            if problem.feasible(values)
        ),
        default=None,
    )


@pytest.mark.parametrize("seed", range(5))
def test_exact_methods_against_enumeration(seed):
    rng = np.random.default_rng(seed)
    # Mixed signs and equalities exercise food-like and mandatory constraints.
    matrix = rng.integers(-4, 6, size=(4, 7)) / 4
    witness = rng.integers(0, 2, size=7)
    totals = matrix @ witness
    problem = model(
        rng.integers(-2, 20, size=7) / 4,
        matrix,
        totals - [0, 1, 2, 0],
        np.add(totals, [0, 1, 2, 0]),
    )
    expected = enumerate_optimum(problem)
    for algorithm in ALGORITHMS:
        result = solve(problem, algorithm)
        assert result.objective == pytest.approx(expected), (algorithm, result)
        assert problem.feasible(result.values)
        if result.bound is not None:
            assert result.bound == pytest.approx(expected)


def test_exact_methods_agree_on_knapsack_bound_and_integrality():
    problem = model([100, 60, 60], [[50, 25, 25]], [-np.inf], [50])
    report = compare_model(problem, ComparisonOptions(algorithms=ALGORITHMS, seconds=1))
    assert report["upper_bound"] == pytest.approx(120)
    assert {row["algorithm"] for row in report["results"]} == {"cp-sat", "highs"}
    assert all(row["objective"] == 120 for row in report["results"])
    fractional = model([10, 9], [[2, 2]], [-np.inf], [3])
    for algorithm in ALGORITHMS:
        result = solve(fractional, algorithm)
        assert result.objective == result.bound == pytest.approx(10)
        assert not result.relaxation and fractional.feasible(result.values)
    assert not fractional.feasible([1, 0.5])
    assert fractional.feasible([1, 0.5], integral=False)


def test_infeasible_has_no_incumbent_or_objective():
    problem = model([1], [[1]], [2], [np.inf])
    for algorithm in ALGORITHMS:
        result = solve(problem, algorithm)
        assert result.status == "INFEASIBLE"
        assert result.objective is None and result.values is None


@pytest.mark.parametrize("algorithm", ["cbc", "scip", "glop", "greedy", "beam", "multistart"])
def test_removed_algorithms_are_rejected(algorithm):
    with pytest.raises(ValueError, match="choose cp-sat or highs"):
        solve(model([1], [[1]], [0], [1]), algorithm)


def test_validation_and_exact_scaling():
    assert integer_row([0.125, -0.25, 1.5]) == [1, -2, 12]
    with pytest.raises(ValueError, match="safe CP-SAT"):
        integer_row([1e-20, 1.0])
    problem = model([1], [[1]], [0], [1])
    for values in ([0.5], [2], [float("nan")], []):
        assert not problem.feasible(values)
    with pytest.raises(ValueError):
        solve(problem, "cp-sat", seconds=0)


def test_independent_validation_clears_invalid_incumbent_and_bound(monkeypatch):
    from games.optimization import competition

    problem = model([1], [[1]], [0], [1])
    bogus = competition.Result("highs", "OPTIMAL", objective=1, bound=1, values=[0.5])
    monkeypatch.setattr(competition, "highs_solve", lambda *args, **kwargs: bogus)
    result = solve(problem, "highs")
    assert result.status == "INVALID_SOLUTION"
    assert result.objective is result.bound is result.values is None
