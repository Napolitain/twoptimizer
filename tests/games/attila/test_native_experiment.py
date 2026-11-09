"""Compare opt-in native products against the unchanged economic reference."""

from dataclasses import replace
from fractions import Fraction
from itertools import product
from types import SimpleNamespace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.optimization.cancellation import Cancellation, Cancelled
from games.optimization.competition import BinaryModel, solve
from games.optimization.native_model import feasible
from games.tw.attila import joint_search
from games.tw.attila.bound_search import strengthen
from games.tw.attila.compact import Builder, CompactIncome, UnsupportedCompact
from games.tw.attila.construction import Construction
from games.tw.attila.native_experiment import NativeProductPlan, with_native_products
from games.tw.attila.region import Region
from tests.support.attila import building, province


def algebra_builder(*, native_products=True):
    names = ("a", "b", "c")
    reference = BinaryModel(
        names=names,
        profit=np.zeros(3),
        matrix=np.empty((0, 3)),
        lower=np.array([]),
        upper=np.array([]),
    )
    plan = SimpleNamespace(definitions={}, definition_rows=(), aliases={})
    return Builder(plan, reference, native_products=native_products)


def economic_reference(context, *, holdings=1, cubic=True):
    problem = Construction(
        objective="income",
        scenario={"regions": {f"r{i}": {"minimum_sanitation": 0} for i in range(holdings)}},
        context=context,
    )
    for number in range(holdings):
        region = Region(f"r{number}", context=context)
        problem.add_province(province(f"p{number}", region))
        candidates = [
            building(
                region,
                f"r{number}_factory",
                ("economy_gdp_industry", "building_to_building_own", 100),
                ("public_order_base", "province_to_province_own", -1),
                upkeep=7,
            ),
            building(
                region,
                f"r{number}_tax",
                ("province_tax_rate", "province_to_province_own", 20),
                ("public_order_politics", "faction_to_province_own", 1),
                upkeep=11,
            ),
        ]
        if cubic:
            candidates.append(
                building(
                    region,
                    f"r{number}_bonus",
                    ("economy_gdp_mod_industry", "province_to_region_own", 25),
                    upkeep=5,
                )
            )
        for candidate in candidates:
            candidate.lp_variable = problem.builder.solver.BoolVar(candidate.get_name())
        problem.builder.solver.Add(sum(candidate.lp_variable for candidate in candidates) <= 3)
    problem.add_objective()
    return problem.builder.binary_model()


def test_new_boolean_products_are_native_and_reuse_the_same_auxiliary():
    builder = algebra_builder()
    target = builder.monomial((0, 1, 2))
    assert builder.monomial((0, 1, 2)) is target
    builder.model.maximize(target)
    assert builder.model.validate() == ""
    assert len(builder.model.proto.constraints) == 1
    assert builder.model.proto.constraints[0].has_int_prod()
    for bits in product((0, 1), repeat=3):
        values = {builder.variables[index].index: bit for index, bit in enumerate(bits)}
        values[target.index] = int(all(bits))
        assert feasible(builder.model, values)
        values[target.index] = 1 - values[target.index]
        assert not feasible(builder.model, values)


def test_signed_rational_repeated_factors_preserve_exact_multiplicity():
    builder = algebra_builder()
    left = builder.expression({(): Fraction(-2, 3), ("a",): 1}, "left")
    right = builder.expression({(): Fraction(4, 5), ("b",): -1}, "right")
    target = builder.product((left, right, left), "income")
    assert isinstance(left.variable, cp_model.IntVar)
    assert isinstance(right.variable, cp_model.IntVar)
    assert isinstance(target.variable, cp_model.IntVar)
    builder.model.maximize(target.variable)
    assert builder.model.validate() == ""
    assert sum(row.has_int_prod() for row in builder.model.proto.constraints) == 1
    assert not any(row.enforcement_literal for row in builder.model.proto.constraints)
    for a, b in product((0, 1), repeat=2):
        expected = (-2 + 3 * a) ** 2 * (4 - 5 * b)
        values = {
            builder.variables[0].index: a,
            builder.variables[1].index: b,
            left.variable.index: -2 + 3 * a,
            right.variable.index: 4 - 5 * b,
            target.variable.index: expected,
        }
        assert feasible(builder.model, values)
        assert expected * target.unit == (Fraction(-2, 3) + a) ** 2 * (Fraction(4, 5) - b)
        values[target.variable.index] += 1
        assert not feasible(builder.model, values)


@pytest.mark.parametrize("invalid", [None, 1, "native"])
def test_experiment_selector_rejects_ambiguous_values(invalid):
    with pytest.raises(ValueError, match="Boolean experiment selector"):
        algebra_builder(native_products=invalid)


def test_wrapper_preserves_reference_and_forwards_search_controls(context, monkeypatch):
    reference = economic_reference(context)
    wrapped = with_native_products(reference)
    assert wrapped is not reference and wrapped.matrix is reference.matrix
    assert wrapped.profit is reference.profit and wrapped.names is reference.names
    assert isinstance(wrapped.cp_sat_plan, NativeProductPlan)
    assert wrapped.cp_sat_plan.original is reference.cp_sat_plan
    assert isinstance(reference.cp_sat_plan, CompactIncome)
    assert with_native_products(wrapped) is wrapped
    captured = {}
    answer = object()

    def delegated(*args, **options):
        captured.update(args=args, options=options)
        return answer

    monkeypatch.setattr(reference.cp_sat_plan, "solve", delegated)
    token, callback, hints = Cancellation(), object(), [0.0] * len(reference.names)
    assert (
        wrapped.cp_sat_plan.solve(
            wrapped, 4, 17, 1, cancellation=token, on_search=callback, hint_values=hints
        )
        is answer
    )
    assert captured == {
        "args": (wrapped, 4, 17, 1),
        "options": {
            "native_products": True,
            "cancellation": token,
            "on_search": callback,
            "hint_values": hints,
        },
    }
    with pytest.raises(ValueError, match="compact-income reference"):
        with_native_products(replace(reference, cp_sat_plan=None))


@pytest.mark.parametrize("cubic", [False, True])
def test_native_and_production_optima_match_the_same_reference(context, cubic):
    reference = economic_reference(context, cubic=cubic)
    before = tuple(array.copy() for array in (reference.profit, reference.lower, reference.upper))
    observed = []
    native = solve(
        with_native_products(reference), "cp-sat", seconds=5, workers=1, on_model=observed.append
    )
    baseline = solve(reference, "cp-sat", seconds=5, workers=1)
    expanded = solve(replace(reference, cp_sat_plan=None), "cp-sat", seconds=5, workers=1)
    for result in (native, baseline, expanded):
        assert result.status == "OPTIMAL"
        assert reference.feasible(result.values)
        assert result.objective == result.bound == (127 if cubic else 102)
    assert native.model_stats["product_encoding"] == "native"
    assert observed[0]["product_encoding"] == "native"
    assert "product_encoding" not in baseline.model_stats
    assert baseline.model_stats["formulation"] == (
        "factored_income" if cubic else "expanded_boolean"
    )
    for original, current in zip(
        before, (reference.profit, reference.lower, reference.upper), strict=True
    ):
        np.testing.assert_array_equal(original, current)


def test_native_joint_bounds_remain_valid_for_original_cross_province_order(context):
    reference = economic_reference(context, holdings=4)
    builder = Builder(reference.cp_sat_plan, reference, native_products=True)
    _, unit = builder.build()
    result = strengthen(builder, seconds=5, seed=0, workers=1)
    optimum = solve(replace(reference, cp_sat_plan=None), "cp-sat", seconds=5, workers=1)
    assert optimum.status == "OPTIMAL" and optimum.objective == 508
    assert result.upper_bound is not None and result.upper_bound * unit >= 508
    assert result.report["components"] == 4
    assert result.report["relaxed_rows"] == 4
    assert result.report["cuts"] > 0
    if result.hint_values is not None:
        assert feasible(builder.model, result.hint_values)


def test_native_cancellation_propagates_without_falling_back(context):
    model = with_native_products(economic_reference(context))
    token, observed = Cancellation(), []

    def cancel_after_compilation(stats):
        observed.append(stats)
        token.cancel()

    with pytest.raises(Cancelled):
        solve(
            model,
            "cp-sat",
            seconds=5,
            workers=1,
            cancellation=token,
            on_model=cancel_after_compilation,
        )
    assert len(observed) == 1 and observed[0]["product_encoding"] == "native"


@pytest.mark.parametrize("holdings", [7, 8, 62])
@pytest.mark.parametrize("requested", [None, False, True])
def test_automatic_cubic_policy_and_explicit_overrides(context, monkeypatch, holdings, requested):
    reference = economic_reference(context, holdings=holdings)
    monkeypatch.setattr(joint_search, "solve", lambda builder, *args, **kwargs: builder)
    options = {} if requested is None else {"native_products": requested}
    builder = reference.cp_sat_plan.solve(reference, 5, 0, 1, **options)
    assert builder.native_products is (holdings >= 8 if requested is None else requested)
    assert builder.joint_bounds is True


@pytest.mark.parametrize("holdings", [8, 62])
@pytest.mark.parametrize("requested", [None, False])
def test_auto_and_hybrid_preserve_quadratic_reference_eligibility(context, holdings, requested):
    reference = economic_reference(context, holdings=holdings, cubic=False)
    with pytest.raises(UnsupportedCompact, match="no cubic income products"):
        reference.cp_sat_plan.solve(reference, 5, 0, 1, native_products=requested)


def test_automatic_eight_province_native_result_matches_expanded_reference(context):
    reference = economic_reference(context, holdings=8)
    automatic = solve(reference, "cp-sat", seconds=5, workers=1)
    expanded = solve(replace(reference, cp_sat_plan=None), "cp-sat", seconds=5, workers=1)
    assert automatic.model_stats["product_encoding"] == "native"
    for result in (automatic, expanded):
        assert result.status == "OPTIMAL"
        assert result.objective == result.bound == 1016
        assert reference.feasible(result.values)
