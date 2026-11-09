"""Equivalent CP-SAT income model with shared wealth, tax and corruption factors.

The original expanded MILP remains the reference for independent validation.
Only its explicit AND definitions are replaced. All other constraints are kept;
exclusive-choice linear branches and native integer products replace expanded
cubic income terms.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import floor, gcd, isfinite, lcm, prod
from time import perf_counter

from ortools.sat.python import cp_model

from games.tw.attila.algebra import add, rational

LIMIT = 2**60


class UnsupportedCompact(ValueError):
    """The existing expanded formulation is required or preferable."""


@dataclass(frozen=True)
class Selector:
    """An affine factor partitioned into proved exclusive groups or singletons."""

    baseline: int
    choices: tuple[tuple[int, int], ...]
    groups: tuple[tuple[tuple[int, int], ...], ...]


@dataclass(frozen=True)
class Value:
    variable: cp_model.IntVar | int
    unit: Fraction
    lower: int
    upper: int
    selector: Selector | None = None


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
        native_products=None,
    ):
        from games.tw.attila.joint_search import solve

        if cancellation is not None:
            cancellation.checkpoint()
        start = perf_counter()
        force_native = native_products is True
        holdings = len(self.economy.provinces)
        native_products = holdings >= 8 if native_products is None else native_products
        builder = Builder(
            self,
            reference,
            joint_bounds=holdings >= 4,
            native_products=native_products,
        )
        if not force_native and not any(
            reference.profit[index] and len(terms) > 2 for index, terms in builder.products.items()
        ):
            # The expanded Boolean relaxation remains stronger for the simpler
            # quadratic WRE/barbarian comparison objectives.
            raise UnsupportedCompact("Expanded model retained: no cubic income products")
        model, unit = builder.build()
        validation = model.validate()
        if validation:
            raise UnsupportedCompact(validation)
        return solve(
            builder,
            reference,
            unit,
            seconds=seconds,
            seed=seed,
            workers=workers,
            started=start,
            on_search=on_search,
            on_model=on_model,
            on_phase=on_phase,
            cancellation=cancellation,
            hint_values=hint_values,
        )


class Builder:
    def __init__(self, plan, reference, *, joint_bounds=True, native_products=False):
        if not isinstance(native_products, bool):
            raise ValueError("native_products must be a Boolean experiment selector")
        self.plan, self.reference = plan, reference
        self.joint_bounds = joint_bounds
        self.native_products = native_products
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
        self.row_supports: dict[int, tuple[int, ...]] = {}
        self.row_constraints: dict[int, tuple[int, ...]] = {}
        self.read_constraints()
        self.group_memberships = defaultdict(list)
        for group_index, (group, _) in enumerate(self.groups):
            for index in group:
                self.group_memberships[index].append(group_index)
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
            self.rows.append((row, indices, coefficients, lower, upper))
            self.row_supports[row] = tuple(map(int, indices))
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
            if self.native_products:
                self.model.add_multiplication_equality(variable, [self.variable(i) for i in terms])
            else:
                self.model.add_bool_and([self.variable(i) for i in terms]).only_enforce_if(variable)
                self.model.add_bool_or([self.variable(i).Not() for i in terms] + [variable])
            self.new_products[terms] = variable
        return self.new_products[terms]

    def simplify(self, terms):
        simplified = defaultdict(Fraction)
        for monomial, coefficient in terms.items():
            term = frozenset(self.indices[self.plan.aliases.get(name, name)] for name in monomial)
            if term & self.zeros or self.violates_groups(term):
                continue
            simplified[tuple(sorted(term - self.ones))] += rational(coefficient)
        return {term: value for term, value in simplified.items() if value}

    def violates_groups(self, term):
        counts = defaultdict(int)
        for index in term:
            for group_index in self.group_memberships.get(index, ()):
                counts[group_index] += 1
                if counts[group_index] > self.groups[group_index][1]:
                    return True
        return False

    def selection_upper(self, weights):
        """Safe bound from a disjoint cover of existing slot/chain constraints."""
        remaining = {i: c for i, c in weights.items() if c > 0}
        bound = 0
        relevant = sorted(
            {group for index in remaining for group in self.group_memberships.get(index, ())}
        )
        while remaining:
            best, gain = None, 0
            for group_index in relevant:
                group, capacity = self.groups[group_index]
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
        return Value(variable, unit, lower, upper, self.selector(integers))

    def selector(self, polynomial):
        """Recognize only choices justified by existing reference constraints."""
        choices = tuple((term[0], value) for term, value in polynomial.items() if term)
        if not choices or any(len(term) > 1 for term in polynomial):
            return None
        return Selector(polynomial.get((), 0), choices, self.selector_groups(choices))

    def selector_groups(self, choices):
        remaining = dict(choices)
        groups = []
        candidates = {
            group
            for index in remaining
            for group in self.group_memberships.get(index, ())
            if self.groups[group][1] == 1
        }
        for group_index in sorted(
            candidates, key=lambda index: (-len(self.groups[index][0] & remaining.keys()), index)
        ):
            selected = tuple(
                (index, remaining[index])
                for index in sorted(self.groups[group_index][0])
                if index in remaining
            )
            if len(selected) > 1:
                groups.append(selected)
                for index, _ in selected:
                    del remaining[index]
        groups.extend(((index, coefficient),) for index, coefficient in remaining.items())
        return tuple(groups)

    def selector_product(self, variable, values, name):
        selected_index = min(
            (index for index, value in enumerate(values) if value.selector is not None),
            key=lambda index: (
                len(values[index].selector.choices),
                len(values[index].selector.groups),
            ),
            default=None,
        )
        if selected_index is None:
            return False
        selected = values[selected_index]
        remaining = [
            Value(value.variable, Fraction(1), value.lower, value.upper, value.selector)
            for index, value in enumerate(values)
            if index != selected_index
        ]
        other = self.product(remaining, name + "__base")
        assert selected.selector is not None and other.unit == 1
        terms = [selected.selector.baseline * other.variable]
        for group_index, group in enumerate(selected.selector.groups):
            terms.append(self.selector_group(other, group, f"{name}__choice_{group_index}"))
        self.model.add(variable == sum(terms))
        return True

    def selector_group(self, other, group, name):
        coefficients = (0, *(coefficient for _, coefficient in group))
        endpoints = [
            endpoint * coefficient
            for endpoint in (other.lower, other.upper)
            for coefficient in coefficients
        ]
        lower, upper = min(endpoints), max(endpoints)
        checked(lower, upper)
        variable = self.model.new_int_var(lower, upper, name)
        inactive = []
        lower_terms, upper_terms = [], []
        for index, coefficient in group:
            choice = self.variable(index)
            self.model.add(variable == coefficient * other.variable).only_enforce_if(choice)
            inactive.append(choice.Not())
            if self.joint_bounds:
                ends = (coefficient * other.lower, coefficient * other.upper)
                lower_terms.append(min(ends) * choice)
                upper_terms.append(max(ends) * choice)
        self.model.add(variable == 0).only_enforce_if(inactive)
        if not self.joint_bounds:
            return variable
        # At most one group choice is active. These unconditional inequalities
        # expose its activity to the LP relaxation, including signed factors.
        self.model.add(variable >= sum(lower_terms))
        self.model.add(variable <= sum(upper_terms))
        if len(set(coefficients[1:])) == 1:
            coefficient = coefficients[1]
            ends = (coefficient * other.lower, coefficient * other.upper)
            unselected = 1 - sum(self.variable(index) for index, _ in group)
            self.model.add(variable >= coefficient * other.variable - max(ends) * unselected)
            self.model.add(variable <= coefficient * other.variable - min(ends) * unselected)
        else:
            # z = y*q with q in the coefficient interval. McCormick envelopes
            # also link the product to y when different upgrades have different
            # coefficients; the activity bounds above use each choice's range.
            choice_value = sum(coefficient * self.variable(index) for index, coefficient in group)
            lo, hi = min(coefficients), max(coefficients)
            self.model.add(
                variable >= other.lower * choice_value + lo * other.variable - other.lower * lo
            )
            self.model.add(
                variable >= other.upper * choice_value + hi * other.variable - other.upper * hi
            )
            self.model.add(
                variable <= other.upper * choice_value + lo * other.variable - other.upper * lo
            )
            self.model.add(
                variable <= other.lower * choice_value + hi * other.variable - other.lower * hi
            )
        return variable

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
            return Value(value.variable, unit, value.lower, value.upper, value.selector)
        lower, upper = 1, 1
        for value in dynamic:
            ends = [a * b for a in (lower, upper) for b in (value.lower, value.upper)]
            lower, upper = min(ends), max(ends)
        checked(lower, upper)
        variable = self.model.new_int_var(lower, upper, name)
        if self.native_products or not self.selector_product(variable, dynamic, name):
            self.model.add_multiplication_equality(variable, [value.variable for value in dynamic])
        return Value(variable, unit, lower, upper)

    def add_reference_rows(self):
        from games.tw.competition import integer_row

        for row, indices, coefficients, lower, upper in self.rows:
            bounds = [v for v in (lower, upper) if isfinite(v)]
            integers = integer_row([*coefficients, *bounds])
            expression = sum(c * self.variable(i) for i, c in zip(indices, integers, strict=False))
            position = len(indices)
            emitted = []
            if isfinite(lower):
                emitted.append(self.model.add(expression >= integers[position]).index)
                position += 1
            if isfinite(upper):
                emitted.append(self.model.add(expression <= integers[position]).index)
            self.row_constraints[row] = tuple(emitted)

    def build(self):
        for index in range(len(self.reference.names)):
            if index not in self.products:
                self.variable(index)
        self.add_reference_rows()
        economy = self.plan.economy
        extras = economy.non_tax_income()
        groups = {}
        for region in economy.regions:
            tax = economy.tax_factor(region)
            keep = add({(): 1}, {term: -c for term, c in economy.corruption(region).items()})
            key = (tuple(sorted(tax.items())), tuple(sorted(keep.items())))
            if self.joint_bounds:
                key = (economy.owner[region.name], *key)
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
        if self.joint_bounds:
            objectives.extend(
                Value(self.monomial(term) if term else 1, coefficient, 0 if term else 1, 1)
                for term, coefficient in self.simplify(extras).items()
            )
        else:
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
