"""Compile-only checks for exact products, with no native solver search."""

from copy import deepcopy
from itertools import product

from ortools.linear_solver import linear_solver_pb2, pywraplp

from games.tw.rome2.compiler import RomeCompiler
from games.tw.rome2.linear import LinearProducts
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import tiny_catalog


def _products(*, alternative_core=False, party=0):
    data = tiny_catalog()
    if alternative_core:
        building = deepcopy(data["buildings"]["rome_city_4"])
        building["id"] = "rome_other_city_4"
        data["buildings"][building["id"]] = building
    economy = Economy(Scenario("rom_rome", (Site("a", major=True, slots=1),), party=party), data)
    solver = pywraplp.Solver.CreateSolver("SAT")
    choices, _ = RomeCompiler(economy)._compile_choices(solver)
    parties = {index: solver.BoolVar("party:" + str(index)) for index in economy.parties}
    solver.Add(sum(parties.values()) == 1)
    return solver, LinearProducts(economy, solver, choices, parties), choices, parties


def _export(solver):
    proto = linear_solver_pb2.MPModelProto()
    solver.ExportModelToProto(proto)
    return proto


def _satisfies(proto, values):
    return all(
        row.lower_bound
        <= sum(
            amount * values[index]
            for index, amount in zip(row.var_index, row.coefficient, strict=True)
        )
        <= row.upper_bound
        for row in proto.constraint
    )


def test_forced_decisions_remain_but_their_wealth_products_need_no_auxiliaries():
    solver, products, choices, parties = _products()
    wealth = solver.IntVar(0, 10, "wealth")
    primary = choices["a", "rome_city_4"]
    expression = products.weighted_products(
        wealth, [(3, primary), (-2, primary), (5, parties[0])], 10
    )
    solver.Maximize(expression)
    proto = _export(solver)
    assert not any(variable.name.startswith("selected_product:") for variable in proto.variable)
    assert {variable.name for variable in proto.variable} >= {"a:rome_city_4", "party:0"}
    assert (
        next(
            variable for variable in proto.variable if variable.name == "wealth"
        ).objective_coefficient
        == 6
    )


def test_mixed_forced_and_optional_products_match_exact_arithmetic_exhaustively():
    solver, products, choices, parties = _products()
    wealth = solver.IntVar(0, 10, "wealth")
    alpha = choices["a", "rome_religious_alpha_4"]
    solver.Maximize(
        products.weighted_products(
            wealth,
            [(7, choices["a", "rome_city_4"]), (3, parties[0]), (2, alpha)],
            10,
        )
    )
    proto = _export(solver)
    auxiliaries = [
        variable.name
        for variable in proto.variable
        if variable.name.startswith("selected_product:")
    ]
    assert len(auxiliaries) == 1
    for wealth_value, (a, b), auxiliary in product((0, 3, 10), ((0, 0), (1, 0), (0, 1)), range(11)):
        assignment = {
            "a:rome_city_4": 1,
            "a:rome_religious_alpha_4": a,
            "a:rome_religious_beta_4": b,
            "party:0": 1,
            "wealth": wealth_value,
            auxiliaries[0]: auxiliary,
        }
        values = [assignment[variable.name] for variable in proto.variable]
        assert _satisfies(proto, values) == (auxiliary == wealth_value * a)
        if auxiliary == wealth_value * a:
            objective = sum(
                v.objective_coefficient * value
                for v, value in zip(proto.variable, values, strict=True)
            )
            assert objective == wealth_value * (10 + 2 * a)


def test_multiple_primary_and_party_choices_are_not_treated_as_fixed():
    solver, products, choices, parties = _products(alternative_core=True, party=None)
    wealth = solver.IntVar(0, 10, "wealth")
    solver.Maximize(
        products.weighted_products(wealth, [(3, choices["a", "rome_city_4"]), (5, parties[0])], 10)
    )
    assert sum(v.name.startswith("selected_product:") for v in _export(solver).variable) == 2


def test_optional_group_products_keep_the_shared_wealth_bound():
    solver, products, choices, _ = _products()
    wealth = solver.IntVar(0, 10, "wealth")
    solver.Maximize(
        products.weighted_products(
            wealth,
            [(1, choices["a", key]) for key in ("rome_religious_alpha_4", "rome_religious_beta_4")],
            10,
        )
    )
    proto = _export(solver)
    assignment = {
        "a:rome_city_4": 1,
        "a:rome_religious_alpha_4": 0.5,
        "a:rome_religious_beta_4": 0.5,
        "party:0": 1,
        "wealth": 5,
        "selected_product:1": 5,
        "selected_product:2": 5,
    }
    # Each product separately satisfies its McCormick inequalities, but the
    # shared ordinary slot cannot select twice the same five units of wealth.
    assert not _satisfies(proto, [assignment[v.name] for v in proto.variable])
    assignment["selected_product:2"] = 0
    assert _satisfies(proto, [assignment[v.name] for v in proto.variable])


def test_exact_party_products_partition_wealth():
    solver, products, _, parties = _products(party=None)
    wealth = solver.IntVar(0, 10, "wealth")
    solver.Maximize(products.weighted_products(wealth, [(1, v) for v in parties.values()], 10))
    proto = _export(solver)
    assignment = {
        "a:rome_city_4": 1,
        "a:rome_religious_alpha_4": 0,
        "a:rome_religious_beta_4": 0,
        "party:0": 0.5,
        "party:1": 0.5,
        "wealth": 5,
        "selected_product:1": 0,
        "selected_product:2": 0,
    }
    assert not _satisfies(proto, [assignment[v.name] for v in proto.variable])
    assignment["selected_product:2"] = 5
    assert _satisfies(proto, [assignment[v.name] for v in proto.variable])


def test_product_substitution_keeps_canonical_proof_model_identity():
    economy = Economy(
        Scenario("rom_rome", (Site("a", major=True, slots=1),), party=0), tiny_catalog()
    )
    # Captured from the native model before this linear-only reformulation.
    assert (
        economy.fingerprint() == "1e0e5aec9c69497d2b53eb23cf390f0371a228d83fd8d835769a98dee5f2a145"
    )
