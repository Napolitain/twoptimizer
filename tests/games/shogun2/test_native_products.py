"""Native Boolean multiplication preserves the reference model and economic objective."""

from dataclasses import replace
from itertools import product

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.optimization.cancellation import Cancellation, Cancelled
from games.optimization.competition import BinaryModel, solve
from games.optimization.sparse import SparseConstraints
from games.tw.shogun2.model import Economy
from games.tw.shogun2.native_products import NativeProducts, Product
from games.tw.shogun2.scenario import Province, Scenario


def binary_product():
    model = BinaryModel(
        ("left", "right", "product"),
        np.array([0.125, 0.375, 1.5]),
        SparseConstraints([((0, 2), (-1, 1)), ((1, 2), (-1, 1)), ((0, 1, 2), (-1, -1, 1))], 3),
        np.array([-np.inf, -np.inf, -1]),
        np.array([0, 0, np.inf]),
        offset=2.25,
    )
    return model, NativeProducts((Product(2, 0, 1, (0, 1, 2)),))


@pytest.mark.parametrize("assignment", tuple(product((0, 1), repeat=3)))
def test_native_product_truth_table_matches_all_original_hull_constraints(assignment):
    reference, plan = binary_product()
    native, variables, _ = plan.build(reference)
    for variable, value in zip(variables, assignment, strict=True):
        native.add(variable == value)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    status = solver.solve(native)
    expected = reference.feasible(assignment)
    assert (status == cp_model.OPTIMAL) is expected
    assert expected == (assignment[2] == assignment[0] * assignment[1])


def test_native_objective_offset_scale_hint_and_matrix_check_are_preserved():
    reference, plan = binary_product()
    expected = solve(reference, "cp-sat", workers=1)
    fingerprint = reference.fingerprint()
    reference.cp_sat_plan = plan
    observations = []
    actual = solve(
        reference, "cp-sat", workers=1, hint_values=[1, 1, 1], on_model=observations.append
    )
    assert actual.status == expected.status == "OPTIMAL"
    assert actual.objective == expected.objective == pytest.approx(4.25)
    assert actual.bound == expected.bound == actual.objective
    assert reference.feasible(actual.values)
    assert reference.fingerprint() == fingerprint
    assert observations[-1]["formulation"] == "native_boolean_products"
    assert observations[-1]["constraints"] == 1


@pytest.mark.parametrize("corruption", ["coefficient", "bound", "duplicate", "out_of_range"])
def test_native_replacement_rejects_metadata_that_does_not_prove_original_product(corruption):
    reference, plan = binary_product()
    if corruption == "coefficient":
        reference.matrix.values[0] = -2
    elif corruption == "bound":
        reference.upper[0] = 1
    elif corruption == "duplicate":
        plan = NativeProducts((Product(2, 0, 1, (0, 0, 2)),))
    else:
        plan = NativeProducts((Product(2, 0, 1, (0, 1, 99)),))
    with pytest.raises(ValueError, match="product"):
        plan.build(reference)


@pytest.mark.parametrize("clan", ["oda", "chosokabe", "otomo"])
def test_native_and_linear_shogun_optima_match_under_original_evaluator(clan):
    scenario = Scenario(clan, (Province("jap_sado"), Province("jap_settsu"), Province("jap_owari")))
    linear = Economy(scenario).optimize(workers=1, seconds=5)
    native = Economy(scenario).optimize(
        workers=1, seconds=5, native_products=True, incumbent=linear
    )
    assert native["solver"]["status"] == linear["solver"]["status"] == "OPTIMAL"
    assert native["domestic_tax_income"] == pytest.approx(linear["domestic_tax_income"])
    assert native["solver"]["bound"] == pytest.approx(linear["solver"]["bound"])
    assert native["model_fingerprint"] == linear["model_fingerprint"]
    assert native["solver"]["model_stats"]["formulation"] == "native_boolean_products"
    layout = {key: row["buildings"] for key, row in native["provinces"].items()}
    assert (
        Economy(scenario).evaluate(layout)["domestic_tax_income"] == native["domestic_tax_income"]
    )


def test_native_selector_does_not_change_highs_path_or_default():
    scenario = Scenario("oda", (Province("jap_owari"),))
    default = Economy(scenario).optimize(workers=1)
    alternative = Economy(scenario).optimize("highs", workers=1)
    assert default["solver"]["model_stats"]["formulation"] == "expanded_boolean"
    assert alternative["solver"]["model_stats"]["formulation"] == "linear_mip"
    assert alternative["domestic_tax_income"] == pytest.approx(default["domestic_tax_income"])


@pytest.mark.parametrize("algorithm,option", [("highs", True), ("cp-sat", 1), ("cp-sat", "native")])
def test_native_selector_rejects_unsupported_or_nonboolean_requests(algorithm, option):
    economy = Economy(Scenario("oda", (Province("jap_owari"),)))
    with pytest.raises(ValueError, match="boolean CP-SAT"):
        economy.optimize(algorithm, native_products=option)


def test_cancellation_boundary_is_preserved_for_native_product_plan():
    reference, plan = binary_product()
    reference.cp_sat_plan = plan
    cancellation = Cancellation()
    with pytest.raises(Cancelled):
        solve(
            reference,
            "cp-sat",
            workers=1,
            cancellation=cancellation,
            on_model=lambda _: cancellation.cancel(),
        )


def test_native_cancellation_retains_revalidated_previous_layout():
    scenario = Scenario("oda", (Province("jap_sado"),))
    previous = Economy(scenario).optimize(workers=1)
    cancellation = Cancellation()
    retained = Economy(scenario).optimize(
        workers=1,
        native_products=True,
        incumbent=previous,
        cancellation=cancellation,
        on_model=lambda _: cancellation.cancel(),
    )
    assert cancellation.requested
    assert retained["solver"]["status"] == "FEASIBLE"
    assert retained["solver"]["native_status"] == "UNKNOWN"
    assert retained["domestic_tax_income"] == previous["domestic_tax_income"]
    assert retained["solver"]["bound"] == previous["solver"]["bound"]


def test_other_reference_constraints_remain_enforced_by_native_plan():
    reference, plan = binary_product()
    matrix = SparseConstraints([*reference.row_entries(), ((0, 1), (1, 1))], 3)
    reference = replace(
        reference,
        matrix=matrix,
        lower=np.append(reference.lower, -np.inf),
        upper=np.append(reference.upper, 1),
        cp_sat_plan=plan,
    )
    result = solve(reference, "cp-sat", workers=1)
    assert result.status == "OPTIMAL"
    assert result.objective == result.bound == pytest.approx(2.625)
    assert reference.feasible(result.values)
