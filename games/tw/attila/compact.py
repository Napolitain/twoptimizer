"""Equivalent CP-SAT income model with shared wealth, tax and corruption factors.

The original expanded MILP remains the reference for independent validation.
Only its explicit AND definitions are replaced. All other constraints are kept;
native integer products replace expanded cubic income terms.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import floor, gcd, isfinite, lcm, prod
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.attila.economy import add, rational

LIMIT = 2**60


class UnsupportedCompact(ValueError):
    """The existing expanded formulation is required or preferable."""


@dataclass(frozen=True)
class Value:
    variable: object
    unit: Fraction
    lower: int
    upper: int


def common_unit(values):
    denominator = lcm(*(value.denominator for value in values))
    divisor = reduce(gcd, (int(value * denominator) for value in values)) or 1
    return Fraction(abs(divisor), denominator)


def checked(*values):
    if any(abs(value) >= LIMIT for value in values):
        raise UnsupportedCompact("Compact integer domain exceeds safe scaling")


class CompactIncome:
    def __init__(self, economy, definitions, definition_rows):
        self.economy = economy
        self.definitions = dict(definitions)
        self.definition_rows = frozenset(definition_rows)
        # Capture SWIG variable names while their original solver is alive.
        self.aliases = {
            name: building.lp_variable.name() for name, building in economy.by_id.items()
        }

    def solve(self, reference, seconds, seed, workers):
        from games.tw.competition import Result

        start = perf_counter()
        builder = Builder(self, reference)
        if not any(
            reference.profit[index] and len(terms) > 2 for index, terms in builder.products.items()
        ):
            # The gain comes from factoring cubic income. For the simpler
            # quadratic objectives the expanded Boolean relaxation is stronger
            # and was faster in the WRE/barbarian comparison cases.
            raise UnsupportedCompact("Expanded model retained: no cubic income products")
        model, unit = builder.build()
        validation = model.validate()
        if validation:
            raise UnsupportedCompact(validation)
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = seed
        solver.parameters.linearization_level = 2
        if seconds is not None:
            solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - start))
        search_start = perf_counter()
        status = solver.solve(model)
        result = Result(
            "cp-sat",
            solver.status_name(status),
            workers=workers,
            timings={
                "model_conversion_seconds": search_start - start,
                "search_seconds": perf_counter() - search_start,
            },
            model_stats={
                "formulation": "factored_income",
                "variables": len(model.proto.variables),
                "constraints": len(model.proto.constraints),
                "reference_variables": len(reference.names),
                "reference_constraints": len(reference.lower),
                "income_groups": builder.income_groups,
            },
        )
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            values: list[float] = [0.0] * len(reference.names)
            for index, variable in builder.variables.items():
                values[index] = solver.value(variable)
            # Restore every expanded auxiliary, even ones the compact model did
            # not need, so the old matrix and independent evaluator can check it.
            for index, terms in builder.products.items():
                values[index] = int(all(values[i] for i in terms))
            native_objective = solver.objective_value * float(unit)
            original_objective = float(reference.profit @ values) + reference.offset
            if abs(native_objective - original_objective) > 1e-5:
                raise AssertionError("Compact and reference income objectives disagree")
            result.values = values
            result.bound = solver.best_objective_bound * float(unit)
        return result


class Builder:
    def __init__(self, plan, reference):
        self.plan, self.reference = plan, reference
        self.model = cp_model.CpModel()
        self.indices = {name: i for i, name in enumerate(reference.names)}
        if len(self.indices) != len(reference.names):
            raise UnsupportedCompact("Reference variables need unique names")
        self.definitions = {
            self.indices[name]: tuple(self.indices[parent] for parent in parents)
            for name, parents in plan.definitions.items()
        }
        self.products = {}

        def factors(index):
            if index not in self.definitions:
                return (index,)
            if index not in self.products:
                self.products[index] = tuple(
                    sorted({i for parent in self.definitions[index] for i in factors(parent)})
                )
            return self.products[index]

        for index in self.definitions:
            factors(index)
        self.product_lookup = {terms: index for index, terms in self.products.items()}
        self.variables, self.new_products = {}, {}
        self.fixed, self.groups = {}, []
        self.rows = []
        self.read_constraints()
        self.ones = {i for i, value in self.fixed.items() if value}
        self.zeros = {i for i, value in self.fixed.items() if not value}
        self.income_groups = 0

    def read_constraints(self):
        reference, plan = self.reference, self.plan
        for row, ((indices, coefficients), lower, upper) in enumerate(
            zip(reference.row_entries(), reference.lower, reference.upper, strict=True)
        ):
            if row in plan.definition_rows:
                continue
            self.rows.append((indices, coefficients, lower, upper))
            if len(indices) == 1:
                possible = [v for v in (0, 1) if lower <= coefficients[0] * v <= upper]
                if len(possible) == 1:
                    self.fixed[int(indices[0])] = possible[0]
            if (
                len(indices) > 1
                and all(c == 1 for c in coefficients)
                and isfinite(upper)
                and all(i not in self.products for i in indices)
            ):
                self.groups.append((frozenset(map(int, indices)), floor(upper)))

    def variable(self, index):
        if index not in self.variables:
            variable = self.model.new_bool_var(self.reference.names[index])
            self.variables[index] = variable
            if index in self.definitions:
                self.model.add_multiplication_equality(
                    variable, [self.variable(i) for i in self.definitions[index]]
                )
        return self.variables[index]

    def monomial(self, terms):
        if len(terms) == 1:
            return self.variable(terms[0])
        if terms in self.product_lookup:
            return self.variable(self.product_lookup[terms])
        if terms not in self.new_products:
            variable = self.model.new_bool_var(f"__compact_and_{len(self.new_products)}")
            self.model.add_bool_and([self.variable(i) for i in terms]).only_enforce_if(variable)
            self.model.add_bool_or([self.variable(i).Not() for i in terms] + [variable])
            self.new_products[terms] = variable
        return self.new_products[terms]

    def simplify(self, terms):
        simplified = defaultdict(Fraction)
        for monomial, coefficient in terms.items():
            term = frozenset(self.indices[self.plan.aliases.get(name, name)] for name in monomial)
            if term & self.zeros or any(
                len(term & group) > capacity for group, capacity in self.groups
            ):
                continue
            simplified[tuple(sorted(term - self.ones))] += rational(coefficient)
        return {term: value for term, value in simplified.items() if value}

    def selection_upper(self, weights):
        """Safe bound from a disjoint cover of existing slot/chain constraints."""
        remaining = {i: c for i, c in weights.items() if c > 0}
        bound = 0
        while remaining:
            best, gain = None, 0
            for group, capacity in self.groups:
                free = max(0, capacity - len(group & self.ones))
                entries = [(i, remaining[i]) for i in group if i in remaining]
                top = sum(sorted((c for _, c in entries), reverse=True)[:free])
                saving = sum(c for _, c in entries) - top
                if saving > gain:
                    best, gain = (entries, top), saving
            if best is None:
                return bound + sum(remaining.values())
            entries, top = best
            bound += top
            for index, _ in entries:
                del remaining[index]
        return bound

    def upper(self, polynomial):
        # For Boolean factors, a positive monomial is at most any one of its
        # factors. Assign it to one producer, then apply cardinality bounds.
        linear = {term[0]: abs(c) for term, c in polynomial.items() if len(term) == 1}
        weights = defaultdict(int)
        for term, coefficient in polynomial.items():
            if term and coefficient > 0:
                anchor = max(term, key=lambda i: (linear.get(i, 0), i))
                weights[anchor] += coefficient
        return polynomial.get((), 0) + self.selection_upper(weights)

    def expression(self, terms, name):
        polynomial = self.simplify(terms)
        if not polynomial:
            return Value(0, Fraction(1), 0, 0)
        unit = common_unit(list(polynomial.values()))
        integers = {term: int(c / unit) for term, c in polynomial.items()}
        lower = -self.upper({term: -c for term, c in integers.items()})
        upper = self.upper(integers)
        checked(lower, upper, sum(abs(c) for c in integers.values()))
        if lower == upper:
            return Value(lower, unit, lower, upper)
        variable = self.model.new_int_var(lower, upper, name)
        self.model.add(
            variable
            == sum(c * (self.monomial(term) if term else 1) for term, c in integers.items())
        )
        return Value(variable, unit, lower, upper)

    def product(self, values, name):
        unit = prod((value.unit for value in values), start=Fraction(1))
        dynamic = []
        for value in values:
            if value.lower == value.upper:
                unit *= value.lower
            else:
                dynamic.append(value)
        if not unit:
            return Value(0, Fraction(1), 0, 0)
        if not dynamic:
            return Value(1, unit, 1, 1)
        if len(dynamic) == 1:
            value = dynamic[0]
            return Value(value.variable, unit, value.lower, value.upper)
        lower, upper = 1, 1
        for value in dynamic:
            ends = [a * b for a in (lower, upper) for b in (value.lower, value.upper)]
            lower, upper = min(ends), max(ends)
        checked(lower, upper)
        variable = self.model.new_int_var(lower, upper, name)
        self.model.add_multiplication_equality(variable, [value.variable for value in dynamic])
        return Value(variable, unit, lower, upper)

    def build(self):
        from games.tw.competition import integer_row

        for index in range(len(self.reference.names)):
            if index not in self.products:
                self.variable(index)
        for indices, coefficients, lower, upper in self.rows:
            bounds = [v for v in (lower, upper) if isfinite(v)]
            integers = integer_row([*coefficients, *bounds])
            expression = sum(c * self.variable(i) for i, c in zip(indices, integers, strict=False))
            position = len(indices)
            if isfinite(lower):
                self.model.add(expression >= integers[position])
                position += 1
            if isfinite(upper):
                self.model.add(expression <= integers[position])
        economy = self.plan.economy
        extras = economy.objective("income")
        groups = {}
        for region in economy.regions:
            extras = add(extras, {term: -c for term, c in economy.tax_income(region).items()})
            tax = economy.tax_factor(region)
            keep = add({(): 1}, {term: -c for term, c in economy.corruption(region).items()})
            key = (tuple(sorted(tax.items())), tuple(sorted(keep.items())))
            wealth = groups.get(key, ({}, tax, keep))[0]
            groups[key] = (add(wealth, economy.wealth(region)), tax, keep)
        objectives = []
        for i, (wealth, tax, keep) in enumerate(groups.values()):
            factors = [
                self.expression(wealth, f"__wealth_{i}"),
                self.expression(tax, f"__tax_{i}"),
                self.expression(keep, f"__keep_{i}"),
            ]
            objectives.append(self.product(factors, f"__income_{i}"))
        self.income_groups = len(groups)
        objectives.append(self.expression(extras, "__other_income"))
        unit = common_unit([value.unit for value in objectives])
        coefficients = [int(value.unit / unit) for value in objectives]
        checked(
            sum(
                abs(c) * max(abs(v.lower), abs(v.upper))
                for c, v in zip(coefficients, objectives, strict=True)
            )
        )
        self.model.maximize(
            sum(c * value.variable for c, value in zip(coefficients, objectives, strict=True))
        )
        return self.model, unit
