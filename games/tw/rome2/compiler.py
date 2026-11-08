"""Exact construction of Rome II decision and product constraints."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ortools.linear_solver import linear_solver_pb2, pywraplp

from games.tw.rome2.backends import NativeCP
from games.tw.rome2.building_constraints import install
from games.tw.rome2.effects import CATEGORIES, raw_effect
from games.tw.rome2.linear import LinearProducts, preserve_base_domain, preserve_minor_domains
from games.tw.rome2.placement import branch

if TYPE_CHECKING:
    from games.tw.rome2.model import Economy


def variable_name(variable):
    return variable.name() if callable(variable.name) else variable.name


type WeightedTerms = list[tuple[int, Any]]


@dataclass(slots=True, kw_only=True)
class EffectTerms:
    """Per-build accumulators shared by building, party and wealth compilation."""

    base: dict[str, WeightedTerms]
    minor_base: dict[str, WeightedTerms]
    modifiers: dict[str, WeightedTerms]
    minor_sites: set[str]
    tax: WeightedTerms
    flat_income: WeightedTerms
    minor_modifiers: WeightedTerms
    food: Any
    order: Any


class RomeCompiler:
    def __init__(self, economy: Economy):
        self.economy = economy

    def build(self, native=False):
        if not isinstance(native, bool):
            raise ValueError("Native compilation must be a boolean CP-SAT selection")
        # MPSolver supplies expressions and protobuf export here; it never solves.
        solver = NativeCP() if native else pywraplp.Solver.CreateSolver("SAT")
        choices, decision_names = self._compile_choices(solver)
        parties = {i: solver.BoolVar("party:" + str(i)) for i in self.economy.parties}
        solver.Add(sum(parties.values()) == 1)
        # Identical sites are interchangeable under the province-wide effects.
        self._symmetry_constraints(choices, solver)
        food = (
            self.economy.scenario.external_food
            + self.economy.fixed_value("food_per_provinces")
            + len(self.economy.scenario.sites) * self.economy.fixed_value("food_per_regions")
        )
        order = (
            self.economy.scenario.order_offset
            + self.economy.fixed_value("order")
            + self.economy.fixed_value("own_culture_order")
        )
        base = {c: [] for c in CATEGORIES}
        minor_base = {c: [] for c in CATEGORIES}
        minor_modifiers = []
        minor_sites = {s.id for s in self.economy.scenario.sites if not s.major}
        modifiers = {c: [] for c in CATEGORIES}
        tax = []
        flat_income = []
        terms = EffectTerms(
            base=base,
            minor_base=minor_base,
            modifiers=modifiers,
            minor_sites=minor_sites,
            tax=tax,
            flat_income=flat_income,
            minor_modifiers=minor_modifiers,
            food=food,
            order=order,
        )
        self._compile_building_effects(choices, terms)
        self._compile_party_effects(parties, terms)
        food, order = terms.food, terms.order
        solver.Add(food >= 0)
        solver.Add(order >= self.economy.scenario.minimum_order)
        products = LinearProducts(self.economy, solver, choices, parties)

        def native_upper(terms):
            amounts = defaultdict(int)
            for amount, variable in terms:
                amounts[variable_name(variable)] += amount
            upper = 0
            for site in self.economy.scenario.sites:
                groups = defaultdict(list)
                for pair, variable in choices.items():
                    if pair[0] == site.id:
                        groups[self.economy.roles[pair]].append(
                            max(0, amounts[variable_name(variable)])
                        )
                upper += max(groups["primary"], default=0) + max(groups["port"], default=0)
                upper += sum(sorted(groups["ordinary"], reverse=True)[: site.capacity])
            upper += max((max(0, amounts[variable_name(v)]) for v in parties.values()), default=0)
            return upper

        selection_upper = native_upper if native else products.selection_upper

        wealth, upper_wealth, combined_upper_terms = self._compile_wealth(
            terms,
            selection_upper,
            solver,
            native,
            products.weighted_products,
        )
        total_wealth = sum(wealth)
        upper_wealth = min(upper_wealth, selection_upper(combined_upper_terms))
        factor = (
            100
            + self.economy.scenario.tax_points
            - self.economy.effective_corruption
            + self.economy.fixed_value("tax_percent")
        )
        if native:
            w = solver.IntVar(0, upper_wealth, "total_wealth_hundredths")
            rate = solver.IntVar(
                max(0, factor + sum(min(0, a) for a, _ in tax)),
                factor + selection_upper(tax),
                "tax_factor",
            )
            income = solver.IntVar(
                0,
                upper_wealth * (factor + selection_upper(tax)),
                "income_ten_thousandths",
            )
            solver.Add(w == total_wealth)
            solver.Add(rate == factor + sum(amount * variable for amount, variable in tax))
            solver.multiply(income, w, rate)
        else:
            income = products.income(total_wealth, factor, tax, upper_wealth)
        solver.Maximize(income + sum(amount * 10000 * variable for amount, variable in flat_income))
        self.economy.decisions, self.economy.party_variables = (
            decision_names,
            {variable_name(v): i for i, v in parties.items()},
        )
        if native:
            return solver
        proto = linear_solver_pb2.MPModelProto()
        if not isinstance(solver, pywraplp.Solver):
            raise TypeError("Binary model export requires an MPSolver")
        solver.ExportModelToProto(proto)
        return proto

    def _symmetry_constraints(self, choices, solver):
        signatures = {}
        for site in self.economy.scenario.sites:
            keys = tuple(self.economy.candidates[site.id])
            group = (site.major, site.port, site.resource, site.capacity, keys)
            signature = sum((i + 1) * choices[(site.id, key)] for i, key in enumerate(keys))
            if group in signatures:
                solver.Add(signatures[group] <= signature)
            signatures[group] = signature

    def _compile_wealth(
        self, terms: EffectTerms, selection_upper, solver, native, weighted_products
    ):
        base, modifiers = terms.base, terms.modifiers
        minor_base, minor_modifiers = terms.minor_base, terms.minor_modifiers
        wealth, upper_wealth, combined_upper_terms = [], 0, []
        for category in CATEGORIES:
            if not base[category]:
                continue
            expression = sum(amount * variable for amount, variable in base[category])
            upper = selection_upper(base[category])
            constant = 100 + self.economy.fixed_value("wealth_percent", category)
            grouped = defaultdict(int)
            for amount, variable in modifiers[category]:
                grouped[variable_name(variable)] += amount
            lookup = {variable_name(v): v for _, v in modifiers[category]}
            if constant + sum(min(0, a) for a in grouped.values()) < 0:
                raise ValueError("Negative wealth modifiers need an explicit zero-floor rule")
            rate_upper = constant + selection_upper(modifiers[category])
            upper_category = upper * rate_upper
            combined_upper_terms.extend(
                (amount * rate_upper, variable) for amount, variable in base[category]
            )
            w = solver.IntVar(0, upper_category, "wealth_hundredths:" + category)
            if native:
                b = solver.IntVar(0, upper, "base:" + category)
                rate = solver.IntVar(
                    constant + sum(min(0, v) for v in grouped.values()),
                    rate_upper,
                    "rate:" + category,
                )
                solver.Add(b == expression)
                solver.Add(
                    rate
                    == constant + sum(amount * lookup[name] for name, amount in grouped.items())
                )
                solver.multiply(w, b, rate)
            else:
                preserve_base_domain(solver, expression, base[category])
                solver.Add(
                    w
                    == constant * expression
                    + weighted_products(expression, modifiers[category], upper)
                )
            wealth.append(w)
            upper_wealth += upper_category
            minor_constant = self.economy.fixed_value("minor_wealth_percent")
            if minor_base[category] and (minor_constant or minor_modifiers):
                minor_expression = sum(a * v for a, v in minor_base[category])
                minor_upper = selection_upper(minor_base[category])
                extra_upper = minor_upper * (minor_constant + selection_upper(minor_modifiers))
                combined_upper_terms.extend(
                    (
                        amount * (minor_constant + selection_upper(minor_modifiers)),
                        variable,
                    )
                    for amount, variable in minor_base[category]
                )
                extra = solver.IntVar(0, extra_upper, "minor_wealth_hundredths:" + category)
                if native:
                    b_minor = solver.IntVar(0, minor_upper, "minor_base:" + category)
                    r_minor = solver.IntVar(
                        minor_constant,
                        minor_constant + selection_upper(minor_modifiers),
                        "minor_rate:" + category,
                    )
                    solver.Add(b_minor == minor_expression)
                    solver.Add(r_minor == minor_constant + sum(a * v for a, v in minor_modifiers))
                    solver.multiply(extra, b_minor, r_minor)
                else:
                    preserve_minor_domains(
                        solver, minor_expression, minor_base[category], minor_modifiers
                    )
                    solver.Add(
                        extra
                        == minor_constant * minor_expression
                        + weighted_products(minor_expression, minor_modifiers, minor_upper)
                    )
                wealth.append(extra)
                upper_wealth += extra_upper
        return wealth, upper_wealth, combined_upper_terms

    def _compile_party_effects(self, parties, terms: EffectTerms):
        for i, variable in parties.items():
            for effect in self.economy.party_effects[i]:
                if effect.kind == "wealth_percent":
                    for category in effect.targets:
                        terms.modifiers[category].append((effect.value, variable))
                elif effect.kind == "food_per_provinces":
                    terms.food += effect.value * variable
                elif effect.kind == "food_per_regions":
                    terms.food += effect.value * len(self.economy.scenario.sites) * variable
                elif effect.kind in {"order", "own_culture_order"}:
                    terms.order += effect.value * variable
                elif effect.kind == "tax_percent":
                    terms.tax.append((effect.value, variable))
                elif effect.kind == "minor_wealth_percent":
                    terms.minor_modifiers.append((effect.value, variable))

    @staticmethod
    def _compile_wealth_effect(effect, pair, variable, terms: EffectTerms):
        if effect.kind == "wealth":
            terms.base[effect.targets[0]].append((effect.value, variable))
            if pair[0] in terms.minor_sites:
                terms.minor_base[effect.targets[0]].append((effect.value, variable))
            return True
        if effect.kind == "wealth_percent":
            for category in effect.targets:
                terms.modifiers[category].append((effect.value, variable))
            return True
        return False

    def _compile_building_effects(self, choices, terms: EffectTerms):
        for pair, variable in choices.items():
            building = self.economy.candidates[pair[0]][pair[1]]
            for raw in building["effects"]:
                effect = raw_effect(raw["id"], raw["value"])
                if effect is None or not self.economy.receives(raw):
                    continue
                if self._compile_wealth_effect(effect, pair, variable, terms):
                    continue
                if effect.kind == "food":
                    terms.food += effect.value * self.economy.receives(raw) * variable
                elif effect.kind == "order":
                    terms.order += effect.value * variable
                elif effect.kind == "tax_percent":
                    terms.tax.append((effect.value, variable))
                elif effect.kind == "income_flat":
                    terms.flat_income.append((effect.value, variable))
                elif effect.kind == "minor_wealth_percent":
                    terms.minor_modifiers.append((effect.value, variable))

    def _compile_choices(self, solver):
        choices, decision_names = {}, {}
        for site in self.economy.scenario.sites:
            by_branch = defaultdict(list)
            primary, ports, ordinary = [], [], []
            for key, building in self.economy.candidates[site.id].items():
                variable = solver.BoolVar(site.id + ":" + key)
                choices[(site.id, key)] = variable
                decision_names[variable_name(variable)] = (site.id, key)
                role = self.economy.roles[(site.id, key)]
                {"primary": primary, "port": ports, "ordinary": ordinary}[role].append(variable)
                if role == "ordinary":
                    by_branch[branch(building)].append(variable)
            solver.Add(sum(primary) == 1)
            if ports:
                solver.Add(sum(ports) == 1)
            solver.Add(sum(ordinary) <= site.capacity)
            for variables in by_branch.values():
                solver.Add(sum(variables) <= 1)
        install(self.economy.scenario, choices, solver)
        return choices, decision_names
