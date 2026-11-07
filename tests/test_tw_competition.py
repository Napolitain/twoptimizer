"""Check solver results against enumeration and the engine's saved regression."""

from itertools import product
from pathlib import Path

import numpy as np
import pytest

from games.tw.benchmark import compare, load_attila, snapshot
from games.tw.competition import ALGORITHMS, BinaryModel, integer_row, solve
from games.tw.games import Games
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
    for algorithm in ("cbc", "scip", "cp-sat", "beam"):
        result = solve(problem, algorithm, width=128)
        if result.status == "UNAVAILABLE":
            continue
        assert result.objective == pytest.approx(expected), (algorithm, result)
        assert problem.feasible(result.values)
        if result.bound is not None:
            assert result.bound == pytest.approx(expected)


def test_greedy_counterexample_and_lp_bound():
    problem = model([100, 60, 60], [[50, 25, 25]], [-np.inf], [50])
    report = compare(problem, ALGORITHMS, 1, 0, 128, 16)
    rows = {r["algorithm"]: r for r in report["results"]}
    assert rows["greedy"]["objective"] <= 120
    assert rows["beam"]["objective"] == 120
    assert rows["multistart"]["objective"] == 120
    assert report["upper_bound"] == pytest.approx(120)
    fractional = model([10, 9], [[2, 2]], [-np.inf], [3])
    relaxation = solve(fractional, "glop")
    assert relaxation.relaxation
    assert relaxation.bound == pytest.approx(14.5)
    assert not fractional.feasible(relaxation.values)
    assert fractional.feasible(relaxation.values, integral=False)


def test_infeasible_is_distinct_from_heuristic_failure():
    problem = model([1], [[1]], [2], [np.inf])
    for algorithm in ("cbc", "cp-sat"):
        result = solve(problem, algorithm)
        assert result.status == "INFEASIBLE"
        assert result.objective is None
    assert solve(problem, "greedy").status == "NO_SOLUTION_FOUND"


def test_validation_and_exact_scaling():
    assert integer_row([0.125, -0.25, 1.5]) == [1, -2, 12]
    with pytest.raises(ValueError, match="safe CP-SAT"):
        integer_row([1e-20, 1.0])
    problem = model([1], [[1]], [0], [1])
    for values in ([0.5], [2], [float("nan")], []):
        assert not problem.feasible(values)
    with pytest.raises(ValueError):
        solve(problem, "greedy", seconds=0)


def test_attila_snapshot_matches_saved_engine_result():
    previous = (
        Games.instance,
        Games.buildings,
        Games.problem,
        Games.fertility,
        Games.USE_NAME,
    )
    try:
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
            problem, _ = snapshot(province, fertility, building_level=4, objective="legacy")
            result = solve(problem, "cp-sat")
            assert result.status == "OPTIMAL"
            assert result.objective == pytest.approx(
                float({k.strip(): v for k, v in expected.items()}[province.print_name])
            )
            assert all(not region.buildings for region in province.regions)
    finally:
        (
            Games.instance,
            Games.buildings,
            Games.problem,
            Games.fertility,
            Games.USE_NAME,
        ) = previous


@pytest.mark.parametrize("fertility,use_hash", [(0, False), (5, True)])
def test_default_cpsat_engine_all_provinces(fertility, use_hash, tmp_path):
    from games.tw.enums import NameType, ProblemState, SolverType
    from games.tw.problem import Problem
    from games.tw.solver_cpsat import SolverCpSat

    previous = (
        Games.instance,
        Games.buildings,
        Games.problem,
        Games.fertility,
        Games.USE_NAME,
    )
    try:
        parser = load_attila(
            AttilaGame.Factions.ATT_FACT_EASTERN_ROMAN_EMPIRE,
            AttilaGame.Religion.CHRIST_ORTHODOX,
            legacy=True,
        )
        Games.USE_NAME = NameType.HASH_NAME if use_hash else NameType.NAME
        Games.fertility = fertility
        expected = dict(
            line.split(":")
            for line in (Path(__file__).parent / f"result_fertility_{fertility}_ere.txt")
            .read_text()
            .splitlines()
        )
        expected = {k.strip(): float(v) for k, v in expected.items()}
        problem = Problem(objective="legacy")
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
                assert problem.problem.get_objective() == pytest.approx(
                    expected[province.print_name]
                )
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
                            original.get_name_output(),
                        )
                assert answers == [expected_answers[v.name()] for v in selected]
                problem.dump(str(tmp_path / "province.lp"))
                assert (tmp_path / "province.lp").stat().st_size > 0
            finally:
                province.clean()
    finally:
        (
            Games.instance,
            Games.buildings,
            Games.problem,
            Games.fertility,
            Games.USE_NAME,
        ) = previous


def test_cpsat_engine_does_not_expose_infeasible_solution():
    from games.tw.solver_cpsat import SolverCpSat

    solver = SolverCpSat()
    x = solver.solver.BoolVar("x")
    solver.solver.Add(x >= 2)
    with pytest.raises(RuntimeError, match="INFEASIBLE"):
        solver.solve()
    with pytest.raises(RuntimeError, match="No feasible"):
        solver.get_objective()
