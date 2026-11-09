"""Experimental CP-SAT product lowering with exact canonical-assignment recovery.

The linear reference and its certified cuts remain authoritative. Only explicitly
recorded product definitions whose auxiliaries have no other uses are replaced.
Every native candidate is reconstructed and checked against all reference rows.
"""

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite

from ortools.linear_solver import linear_solver_pb2
from ortools.sat.python import cp_model

from games.tw.three_kingdoms.product_metadata import Product, integer


def _eligible(proto, products):
    rows = defaultdict(set)
    for number, row in enumerate(proto.constraint):
        for index, coefficient in zip(row.var_index, row.coefficient, strict=True):
            if coefficient:
                rows[index].add(number)
    factors = {
        index
        for product in products
        for factor in (product.left, product.right)
        for index, _ in factor.terms
    }
    return tuple(
        product
        for product in products
        if all(
            rows[index] <= set(product.rows)
            and not proto.variable[index].objective_coefficient
            and index not in factors
            for index in product.auxiliaries
        )
    )


def _linear_rows(model, variables, proto, removed):
    for number, row in enumerate(proto.constraint):
        if number in removed:
            continue
        expression = sum(
            integer(c) * variables[i]
            for i, c in zip(row.var_index, row.coefficient, strict=True)
            if c
        )
        if isfinite(row.lower_bound):
            model.add(expression >= integer(row.lower_bound))
        if isfinite(row.upper_bound):
            model.add(expression <= integer(row.upper_bound))


def _factor(model, variables, factor, label):
    expression = factor.offset + sum(c * variables[i] for i, c in factor.terms)
    if len(factor.terms) <= 1:
        return expression
    variable = model.new_int_var(factor.lower, factor.upper, label)
    model.add(variable == expression)
    return variable


def _validate_values(proto, values):
    for source, value in zip(proto.variable, values, strict=True):
        if not source.lower_bound <= value <= source.upper_bound:
            raise AssertionError("Native product recovery violated a reference variable domain")
    for row in proto.constraint:
        amount = sum(
            integer(c) * values[i] for i, c in zip(row.var_index, row.coefficient, strict=True)
        )
        if not row.lower_bound <= amount <= row.upper_bound:
            raise AssertionError("Native product recovery violated a reference constraint")


@dataclass(slots=True)
class NativeProducts:
    model: cp_model.CpModel
    variables: dict[int, cp_model.IntVar]
    lowered: tuple[Product, ...]
    original: linear_solver_pb2.MPModelProto
    retained: int

    def values(self, solver):
        values = [0] * len(self.original.variable)
        for index, variable in self.variables.items():
            values[index] = solver.value(variable)
        for product in self.lowered:
            left, right = product.left.value(values), product.right.value(values)
            if values[product.target] != left * right:
                raise AssertionError("Native product disagrees with exact operand multiplication")
            bits = left - product.left.lower
            for number, (bit, selected) in enumerate(
                zip(product.bits, product.selected, strict=True)
            ):
                values[bit] = (bits >> number) & 1
                values[selected] = right * values[bit]
        _validate_values(self.original, values)
        return values

    def add_hints(self, hints):
        for index, variable in self.variables.items():
            name = self.original.variable[index].name
            if name in hints:
                self.model.add_hint(variable, hints[name])

    @property
    def stats(self):
        return {
            "formulation": "native_products",
            "variables": len(self.model.proto.variables),
            "constraints": len(self.model.proto.constraints),
            "native_product_count": len(self.lowered),
            "retained_linear_products": self.retained,
            "removed_product_variables": len(self.original.variable) - len(self.variables),
        }


def lower(proto, products):
    lowered = _eligible(proto, products)
    removed_variables = {i for product in lowered for i in product.auxiliaries}
    removed_rows = {i for product in lowered for i in product.rows}
    model = cp_model.CpModel()
    variables = {}
    for index, source in enumerate(proto.variable):
        if not source.is_integer:
            raise ValueError("Native products require integer reference variables")
        if index not in removed_variables:
            variables[index] = model.new_int_var(
                integer(source.lower_bound), integer(source.upper_bound), source.name
            )
    _linear_rows(model, variables, proto, removed_rows)
    for number, product in enumerate(lowered):
        left = _factor(model, variables, product.left, f"product:{number}:left")
        right = _factor(model, variables, product.right, f"product:{number}:right")
        model.add_multiplication_equality(variables[product.target], [left, right])
    model.maximize(
        integer(proto.objective_offset)
        + sum(
            integer(source.objective_coefficient) * variables[index]
            for index, source in enumerate(proto.variable)
            if source.objective_coefficient
        )
    )
    return NativeProducts(model, variables, lowered, proto, len(products) - len(lowered))
