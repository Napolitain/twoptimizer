"""Transfer linear preparation certificates into the native product formulation."""

from dataclasses import replace
from time import perf_counter

from games.optimization.cp_backend import NativeCP
from games.optimization.native_model import feasible, objective_terms, objective_value


def validated_values(problem, named_values):
    values = {}
    for index, variable in enumerate(problem.model.proto.variables):
        if variable.name in named_values:
            values[index] = named_values[variable.name]
        elif len(variable.domain) == 2 and variable.domain[0] == variable.domain[1]:
            # CP-SAT may insert unnamed constants for Add(True). They are not
            # domain decisions and need no reconstructed economic auxiliary.
            values[index] = variable.domain[0]
        else:
            raise ValueError("Native product assignment is missing a nonconstant variable")
    if not feasible(problem.model, values):
        raise AssertionError("Prepared provincial layout fails native product constraints")
    return values


def _seed(economy, problem, linear, hint):
    if hint is None:
        return None
    layout = {site.id: [] for site in economy.scenario.sites}
    party = None
    for index, variable in enumerate(linear.variable):
        if not hint[index]:
            continue
        if variable.name in economy.decisions:
            site, building = economy.decisions[variable.name]
            layout[site].append(building)
        if variable.name in economy.party_variables:
            party = economy.party_variables[variable.name]
    economics = economy.evaluate(layout, party)
    reconstructed = economy.warm_values(economics)
    return validated_values(problem, reconstructed)


def prepare(economy, problem, proto, seconds, workers, started, cancellation, on_phase):
    """Keep linear auxiliary cuts separate; transfer a total bound and validated seed."""
    from games.tw.rome2.joint_search import _strengthen

    remaining = None if seconds is None else seconds - (perf_counter() - started)
    if not hasattr(economy, "locals") or (remaining is not None and remaining < 45):
        return None
    proto = economy.build()
    # Component cuts refer to the linear model's auxiliary indices. Its scratch
    # model owns those cuts; they must never be applied by index to native products.
    scratch = NativeCP.from_linear(proto)
    bounds = _strengthen(scratch, proto, seconds, workers, started, cancellation, on_phase)
    if bounds is None:
        return None
    seed = _seed(economy, problem, proto, bounds.hint_values)
    if seed is not None and objective_value(problem.model, seed) != bounds.report["hint_income"]:
        raise AssertionError("Native seed income disagrees with the linear preparation")
    if bounds.upper_bound is not None:
        coefficients, constant = objective_terms(problem.model)
        problem.model.add(
            constant
            + sum(
                amount * problem.model.get_int_var_from_proto_index(index)
                for index, amount in coefficients.items()
            )
            <= bounds.upper_bound
        )
    return replace(
        bounds,
        hint_values=seed,
        report={
            **bounds.report,
            "linear_component_cuts": bounds.report.get("cuts", 0),
            "cuts": int(bounds.upper_bound is not None),
            "native_seed_validated": seed is not None,
            "transferred_to": "native_products",
        },
    )
