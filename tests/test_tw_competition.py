"""Check solver results against enumeration and the engine's saved regression."""

from itertools import product
from pathlib import Path

import numpy as np
import pytest

from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.comparison import ComparisonOptions, compare_model
from games.tw.competition import ALGORITHMS, BinaryModel, integer_row, solve
from games.tw.models.game_attila import AttilaGame


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


def test_attila_snapshot_matches_saved_engine_result():
    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
        legacy=True,
    )
    province = next(iter(parser.provinces.values()))
    for fertility in (0, 5):
        expected = dict(
            line.split(":")
            for line in (Path(__file__).parent / f"result_fertility_{fertility}_ere.txt")
            .read_text()
            .splitlines()
        )
        problem = compile_scenario(
            [province], SnapshotOptions(fertility=fertility, building_level=4, objective="legacy")
        ).model
        result = solve(problem, "cp-sat")
        assert result.status == "OPTIMAL"
        assert result.objective == pytest.approx(
            float({k.strip(): v for k, v in expected.items()}[province.print_name])
        )
        assert all(not region.buildings for region in province.regions)


@pytest.mark.parametrize("fertility,use_hash", [(0, False), (5, True)])
def test_default_cpsat_engine_all_provinces(fertility, use_hash, tmp_path):
    from games.tw.enums import NameType, ProblemState, SolverType
    from games.tw.problem import Problem
    from games.tw.solver_cpsat import SolverCpSat

    parser = load_attila(
        AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
        AttilaGame.Religion.CHRIST_ORTHODOX,
        legacy=True,
    )
    parser.context.name_type = NameType.HASH_NAME if use_hash else NameType.NAME
    parser.context.fertility = fertility
    expected = dict(
        line.split(":")
        for line in (Path(__file__).parent / f"result_fertility_{fertility}_ere.txt")
        .read_text()
        .splitlines()
    )
    expected = {k.strip(): float(v) for k, v in expected.items()}
    problem = Problem(objective="legacy", context=parser.context)
    assert problem.solver_type == SolverType.CP_SAT
    assert isinstance(problem.problem, SolverCpSat)
    with pytest.raises(RuntimeError, match="No feasible"):
        problem.problem.get_objective()
    for province in parser.provinces.values():
        problem.reset_problem()
        problem.add_province(province)
        try:
            for region in province.regions:
                region.add_buildings()
                region.filter_city_level(4)
                region.filter_building_level(4)
                region.filter_military()
                problem.problem.filter_added({b.name: b for b in region.buildings})
            for region in province.regions:
                region.add_constraints()
            province.add_sanitation_constraint()
            province.add_food_constraint()
            province.add_public_order_constraint()
            problem.state = ProblemState.CONSTRAINTS_ADDED
            problem.add_objective()
            problem.solve()
            assert problem.problem.result is not None
            assert problem.problem.result.status == "OPTIMAL"
            assert problem.problem.get_objective() == pytest.approx(expected[province.print_name])
            answers = problem.get_problem_answers()
            selected = [v for v in problem.problem.variables() if v.solution_value() > 0.5]
            assert len(answers) == len(selected) > 0
            expected_answers = {}
            for region in province.regions:
                for building in region.buildings:
                    base_name = building.name.removeprefix(region.name + "_")
                    original = parser.buildings[parser.campaign.value[1]][base_name]
                    expected_answers[building.lp_variable.name()] = (
                        region.get_name_output(),
                        original.get_name_output(problem.context.name_type),
                    )
            assert answers == [expected_answers[v.name()] for v in selected]
            problem.dump(str(tmp_path / "province.lp"))
            assert (tmp_path / "province.lp").stat().st_size > 0
        finally:
            province.clean()


@pytest.mark.parametrize("algorithm", ["cp-sat", "highs"])
def test_native_engine_does_not_expose_infeasible_solution(algorithm):
    from games.tw.solver_cpsat import SolverCpSat
    from games.tw.solver_highs import SolverHighs

    solver = SolverCpSat() if algorithm == "cp-sat" else SolverHighs()
    x = solver.solver.BoolVar("x")
    solver.solver.Add(x >= 2)
    with pytest.raises(RuntimeError, match="INFEASIBLE"):
        solver.solve()
    with pytest.raises(RuntimeError, match="No feasible"):
        solver.get_objective()
    with pytest.raises(RuntimeError, match="No feasible"):
        solver.variables()[0].solution_value()


def test_independent_validation_clears_invalid_incumbent_and_bound(monkeypatch):
    from games.tw import competition

    problem = model([1], [[1]], [0], [1])
    bogus = competition.Result("highs", "OPTIMAL", objective=1, bound=1, values=[0.5])
    monkeypatch.setattr(competition, "highs_solve", lambda *args: bogus)
    result = solve(problem, "highs")
    assert result.status == "INVALID_SOLUTION"
    assert result.objective is result.bound is result.values is None
