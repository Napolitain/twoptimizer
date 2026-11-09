"""Experimental native products preserve the complete canonical integer model."""

import pytest
from ortools.linear_solver import linear_solver_pb2, pywraplp
from ortools.sat.python import cp_model

from games.optimization.cancellation import Cancellation
from games.tw.three_kingdoms import joint_bounds, optimization
from games.tw.three_kingdoms.catalog import load_data
from games.tw.three_kingdoms.incumbent import layout_from
from games.tw.three_kingdoms.integer import Arithmetic, Quantity
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.native_products import lower
from games.tw.three_kingdoms.scenario import Commandery, Scenario


def exported(solver):
    proto = linear_solver_pb2.MPModelProto()
    solver.ExportModelToProto(proto)
    return proto


def solve_native(proto, metadata):
    original = proto.SerializeToString()
    problem = lower(proto, metadata)
    assert problem.model.validate() == ""
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 5
    assert solver.solve(problem.model) == cp_model.OPTIMAL
    values = problem.values(solver)
    assert proto.SerializeToString() == original
    return problem, values, solver.objective_value


@pytest.mark.parametrize(("x_value", "y_value", "z_value"), [(-3, -2, 5), (3, 2, -5), (0, 1, 4)])
def test_signed_affine_and_nested_products_reconstruct_canonical_rows(x_value, y_value, z_value):
    solver = pywraplp.Solver.CreateSolver("SAT")
    arithmetic = Arithmetic(solver)
    x, y, z = (
        solver.IntVar(lo, hi, name) for lo, hi, name in [(-3, 3, "x"), (-2, 2, "y"), (-5, 5, "z")]
    )
    for variable, value in ((x, x_value), (y, y_value), (z, z_value)):
        solver.Add(variable == value)
    first = arithmetic.product(Quantity(2 * x - y + 3, -5, 11), Quantity(z - 4, -9, 1), "first")
    second = arithmetic.product(first, Quantity(x + 1, -2, 4), "second")
    positive = arithmetic.maximum_zero(second, "positive")
    solver.Maximize(positive.expression)
    problem, values, objective = solve_native(exported(solver), arithmetic.products)
    expected = (2 * x_value - y_value + 3) * (z_value - 4)
    assert values[first.expression.index()] == expected
    assert values[second.expression.index()] == expected * (x_value + 1)
    assert objective == max(0, expected * (x_value + 1))
    assert problem.stats["native_product_count"] == 2
    assert problem.stats["removed_product_variables"] > 0


def test_product_auxiliary_referenced_by_added_cut_keeps_exact_linear_definition():
    solver = pywraplp.Solver.CreateSolver("SAT")
    arithmetic = Arithmetic(solver)
    x, y = solver.IntVar(0, 3, "x"), solver.IntVar(0, 4, "y")
    quantity = arithmetic.product(Quantity(x, 0, 3), Quantity(y, 0, 4), "product")
    solver.Maximize(quantity.expression)
    proto = exported(solver)
    bit = arithmetic.products[0].bits[0]
    row = proto.constraint.add(name="later_certified_cut", lower_bound=0, upper_bound=0)
    row.var_index.append(bit)
    row.coefficient.append(1)
    problem, values, objective = solve_native(proto, arithmetic.products)
    assert problem.stats["native_product_count"] == 0
    assert problem.stats["retained_linear_products"] == 1
    assert values[bit] == 0
    assert objective == 8  # x must be even, so x=2 rather than x=3.


def test_constant_factor_and_cancelled_terms_need_no_unsafe_name_parsing():
    solver = pywraplp.Solver.CreateSolver("SAT")
    arithmetic = Arithmetic(solver)
    x = solver.IntVar(-2, 3, "name_without_product_convention")
    value = arithmetic.product(Quantity(x, -2, 3), Quantity.constant(-2), "arbitrary")
    solver.Maximize(value.expression)
    problem, _, objective = solve_native(exported(solver), arithmetic.products)
    assert objective == 4
    assert problem.stats["native_product_count"] == 0


@pytest.mark.parametrize("corruption", [0, 70])
def test_native_and_linear_commandery_optima_match_with_unchanged_reference(corruption):
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao",
            (
                Commandery(
                    "3k_main_province_changan", city_level=None, corruption_percent=corruption
                ),
            ),
        )
    )
    linear = model.optimize(seconds=5, workers=1)
    result = model.optimize(seconds=5, workers=1, native_products=True)
    assert result["solver"]["status"] == linear["solver"]["status"] == "OPTIMAL"
    assert result["domestic_income"] == pytest.approx(linear["domestic_income"])
    assert result["model_fingerprint"] == linear["model_fingerprint"]
    assert result["solver"]["model_stats"]["native_product_count"] > 0
    assert model.evaluate(layout_from(result))["domestic_income"] == result["domestic_income"]
    assert (
        result["solver"]["model_stats"]["variables"] < linear["solver"]["model_stats"]["variables"]
    )


def test_native_products_preserve_valid_component_bound_cuts(monkeypatch):
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao",
            (
                Commandery("3k_main_province_yingchuan", city_level=None),
                Commandery("3k_main_province_chenjun", city_level=None),
            ),
        )
    )
    baseline = model.optimize(seconds=5, workers=1)
    proto = model.compile()
    monkeypatch.setattr(joint_bounds, "_price", lambda *args: (300000, {"status": "test_price"}))
    strengthened, bound, _ = joint_bounds.strengthen(proto, 5, 1)
    problem, _, objective = solve_native(strengthened, model.products)
    assert objective / 1_000_000 == pytest.approx(baseline["domestic_income"])
    assert objective <= bound
    assert problem.stats["native_product_count"] > 0


def test_native_cancel_retains_linear_incumbent_and_bound():
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao", (Commandery("3k_main_province_yingchuan", city_level=None),)
        )
    )
    previous = model.optimize(seconds=5, workers=1)
    cancellation = Cancellation()
    cancellation.cancel()
    result = model.optimize(
        seconds=5, workers=1, native_products=True, incumbent=previous, cancellation=cancellation
    )
    assert result["solver"]["status"] == "FEASIBLE"
    assert result["solver"]["native_status"] == "UNKNOWN"
    assert result["domestic_income"] == previous["domestic_income"]
    assert result["solver"]["bound"] == previous["solver"]["bound"]


def test_native_selector_does_not_change_highs_or_accept_ambiguous_values():
    model = Economy(
        Scenario(
            "3k_main_faction_cao_cao", (Commandery("3k_main_province_yingchuan", city_level=None),)
        )
    )
    with pytest.raises(ValueError, match="CP-SAT-only"):
        model.optimize("highs", native_products=True)
    with pytest.raises(ValueError, match="boolean"):
        model.optimize(native_products="yes")


@pytest.mark.parametrize(
    ("count", "algorithm", "requested", "expected"),
    [
        (1, "cp-sat", None, False),
        (7, "cp-sat", None, False),
        (8, "cp-sat", None, True),
        (8, "cp-sat", False, False),
        (1, "cp-sat", True, True),
        (8, "highs", None, False),
        (8, "highs", False, False),
    ],
)
def test_automatic_selection_reaches_solver_boundary_without_changing_local_preparation(
    count, algorithm, requested, expected, monkeypatch
):
    keys = tuple(load_data()["commanderies"])[:count]
    model = Economy(
        Scenario("3k_main_faction_cao_cao", tuple(Commandery(key, city_level=None) for key in keys))
    )
    captured = []

    def native(proto, backend, seconds, workers, seed, options):
        captured.append(options["products"])
        return {
            "algorithm": backend,
            "status": "UNKNOWN",
            "values": None,
            "objective": None,
            "bound": None,
            "timings": {},
        }

    monkeypatch.setattr(optimization, "_native", native)
    result = model.optimize(algorithm, seconds=0.1, workers=1, native_products=requested)
    assert result["solver"]["status"] == "UNKNOWN"
    assert (captured[0] is not None) is expected
    if expected:
        assert captured[0] == model.products
        assert len(captured[0]) > 0
