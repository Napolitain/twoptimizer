"""Experimental native Boolean products over the unchanged reference binary model."""

from dataclasses import dataclass, replace
from math import inf
from time import perf_counter

from ortools.sat.python import cp_model

from games.optimization.competition import BinaryModel, Result, _binary_cp_model
from games.optimization.search_progress import solve_with_progress
from games.optimization.sparse import SparseConstraints


@dataclass(frozen=True, slots=True)
class Product:
    target: int
    left: int
    right: int
    rows: tuple[int, ...]


def _row_signature(indices, coefficients, lower, upper):
    return (
        tuple(sorted(zip(map(int, indices), map(float, coefficients), strict=True))),
        lower,
        upper,
    )


def _expected_rows(product):
    target, left, right = product.target, product.left, product.right
    return {
        _row_signature((target, left), (1, -1), -inf, 0),
        _row_signature((target, right), (1, -1), -inf, 0),
        _row_signature((target, left, right), (1, -1, -1), -1, inf),
    }


def _linear_remainder(reference, products):
    rows = list(reference.row_entries())
    removed = set()
    for product in products:
        if len(product.rows) != 3 or removed.intersection(product.rows):
            raise ValueError("Native product rows must be three distinct owned constraints")
        actual = set()
        for index in product.rows:
            if not 0 <= index < len(rows):
                raise ValueError("Native product row is outside the reference model")
            actual.add(_row_signature(*rows[index], reference.lower[index], reference.upper[index]))
        if actual != _expected_rows(product):
            raise ValueError("Native product metadata disagrees with reference hull constraints")
        removed.update(product.rows)
    kept = [index for index in range(len(rows)) if index not in removed]
    return replace(
        reference,
        matrix=SparseConstraints((rows[index] for index in kept), len(reference.names)),
        lower=reference.lower[kept],
        upper=reference.upper[kept],
        cp_sat_plan=None,
    )


@dataclass(frozen=True, slots=True)
class NativeProducts:
    products: tuple[Product, ...]

    @classmethod
    def from_economy(cls, economy):
        indices = {name: index for index, name in enumerate(economy.binary.names)}
        return cls(
            tuple(
                Product(
                    indices[target], indices[left], indices[right], economy.product_rows[target]
                )
                for target, (left, right) in economy.product_factors.items()
            )
        )

    def build(self, reference: BinaryModel):
        linear = _linear_remainder(reference, self.products)
        problem, variables, scale = _binary_cp_model(linear)
        for product in self.products:
            problem.add_multiplication_equality(
                variables[product.target], [variables[product.left], variables[product.right]]
            )
        return problem, variables, scale

    def solve(
        self,
        reference,
        seconds,
        seed,
        workers,
        *,
        on_search=None,
        on_model=None,
        cancellation=None,
        on_phase=None,
        hint_values=None,
    ):
        started = perf_counter()
        if cancellation is not None:
            cancellation.checkpoint()
        problem, variables, scale = self.build(reference)
        if hint_values is not None:
            for variable, value in zip(variables, hint_values, strict=True):
                problem.add_hint(variable, round(value))
        if error := problem.validate():
            raise ValueError(error)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed
        if seconds is not None:
            solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - started))
        stats = {
            "formulation": "native_boolean_products",
            "variables": len(problem.proto.variables),
            "constraints": len(problem.proto.constraints),
            "products": len(self.products),
        }
        if on_model is not None:
            on_model(stats)
        searching = perf_counter()
        status = solve_with_progress(
            solver,
            problem,
            on_search=on_search,
            scale=scale,
            offset=reference.offset,
            cancellation=cancellation,
        )
        result = Result(
            "cp-sat",
            solver.status_name(status),
            timings={
                "model_conversion_seconds": searching - started,
                "search_seconds": perf_counter() - searching,
            },
            workers=workers,
            model_stats=stats,
            detail=solver.solution_info(),
        )
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            result.values = [solver.value(variable) for variable in variables]
            result.bound = solver.best_objective_bound * scale + reference.offset
        return result
