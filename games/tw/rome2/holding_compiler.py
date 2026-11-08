"""Compile a single exact income problem over Rome II provinces."""

from collections import defaultdict

from ortools.linear_solver import linear_solver_pb2, pywraplp

from games.tw.rome2.backends import NativeCP
from games.tw.rome2.building_constraints import install
from games.tw.rome2.compiler import EffectTerms, RomeCompiler, variable_name
from games.tw.rome2.effects import CATEGORIES, raw_effect
from games.tw.rome2.holding_scopes import ADJACENT_SCOPES, recipients
from games.tw.rome2.linear import LinearProducts
from games.tw.rome2.model import GLOBAL_SCOPES, LOCAL_SCOPES
from games.tw.rome2.placement import branch


class ProvinceVariables:
    """Scope auxiliary names while retaining globally unique building decisions."""

    def __init__(self, solver, prefix):
        self.solver, self.prefix = solver, prefix

    def IntVar(self, lower, upper, name):
        return self.solver.IntVar(lower, upper, self.prefix + ":" + name)

    def Add(self, expression):
        return self.solver.Add(expression)

    def multiply(self, result, left, right):
        return self.solver.multiply(result, left, right)


class HoldingProducts(LinearProducts):
    """Share indexed site groups instead of rescanning every owned decision."""

    def __init__(self, economy, solver, choices, parties, site_index):
        self.site_index, self.selectors, self.capacities = site_index
        self.party_names = {variable_name(variable) for variable in parties.values()}
        super().__init__(economy, solver, choices, parties)

    def site_groups(self, site):
        return self.site_index[site.id]

    @staticmethod
    def index(economy, choices):
        groups = {
            site.id: (defaultdict(list), defaultdict(list)) for site in economy.scenario.sites
        }
        selectors = {}
        for pair, variable in choices.items():
            roles, branches = groups[pair[0]]
            role = economy.roles[pair]
            roles[role].append(variable)
            chain = branch(economy.candidates[pair[0]][pair[1]]) if role == "ordinary" else role
            selectors[variable_name(variable)] = (pair[0], role, chain)
            if role == "ordinary":
                branches[branch(economy.candidates[pair[0]][pair[1]])].append(variable)
        return groups, selectors, {site.id: site.capacity for site in economy.scenario.sites}

    def selection_upper(self, terms):
        amounts = defaultdict(int)
        for amount, variable in terms:
            amounts[variable_name(variable)] += amount
        groups, party_upper = defaultdict(dict), 0
        for name, amount in amounts.items():
            if name in self.selectors:
                site, role, chain = self.selectors[name]
                key = (role, chain)
                groups[site][key] = max(groups[site].get(key, 0), amount)
            elif name in self.party_names:
                party_upper = max(party_upper, amount)
        return party_upper + sum(self._site_upper(site, values) for site, values in groups.items())

    def _site_upper(self, site, groups):
        ordinary = sorted(
            (amount for (role, _), amount in groups.items() if role == "ordinary"), reverse=True
        )
        return (
            groups.get(("primary", "primary"), 0)
            + groups.get(("port", "port"), 0)
            + sum(ordinary[: self.capacities[site]])
        )


class HoldingCompiler:
    def __init__(self, economy):
        self.economy = economy
        self.effects = self._routed_effects()

    def _targets(self, scope, source):
        if scope in LOCAL_SCOPES:
            return (source,)
        if scope in GLOBAL_SCOPES:
            return tuple(self.economy.locals)
        if scope in ADJACENT_SCOPES:
            return tuple(
                key
                for key in self.economy.locals
                if frozenset((source, key)) in self.economy.borders
            )
        return ()

    def _routed_effects(self):
        effects = {key: [] for key in self.economy.locals}
        for site, choices in self.economy.candidates.items():
            source = self.economy.owners[site]
            for key, building in choices.items():
                for raw in building["effects"]:
                    effect = raw_effect(raw["id"], raw["value"])
                    if effect is None:
                        continue
                    for target in self._targets(raw["scope"], source):
                        count = recipients(
                            raw["scope"],
                            source,
                            target,
                            len(self.economy.locals[target].scenario.sites),
                            self.economy.borders,
                        )
                        effects[target].append(((site, key), effect, count, source == target))
        return effects

    def build(self, native=False):
        if not isinstance(native, bool):
            raise ValueError("Native compilation must be a boolean CP-SAT selection")
        # MPSolver supplies expressions and protobuf export here; it never solves.
        solver = NativeCP() if native else pywraplp.Solver.CreateSolver("SAT")
        choices, names = {}, {}
        for local in self.economy.locals.values():
            compiler = RomeCompiler(local)
            selected, decisions = compiler._compile_choices(solver)
            # Symmetry stays within one province; crossing a border can change effects.
            compiler._symmetry_constraints(selected, solver)
            choices.update(selected)
            names.update(decisions)
        install(self.economy.scenario, choices, solver)
        parties = {i: solver.BoolVar("party:" + str(i)) for i in self.economy.parties}
        solver.Add(sum(parties.values()) == 1)
        site_index = HoldingProducts.index(self.economy, choices)
        incomes, foods = [], []
        for key, local in self.economy.locals.items():
            scoped = ProvinceVariables(solver, key)
            terms = self._terms(key, local, choices, parties)
            solver.Add(terms.order >= local.scenario.minimum_order)
            products = HoldingProducts(self.economy, scoped, choices, parties, site_index)
            incomes.append(self._income(local, terms, products, scoped, native))
            foods.append(terms.food)
        solver.Add(sum(foods) >= 0)
        solver.Maximize(sum(incomes))
        self.economy.decisions = names
        self.economy.party_variables = {variable_name(v): i for i, v in parties.items()}
        if native:
            return solver
        proto = linear_solver_pb2.MPModelProto()
        if not isinstance(solver, pywraplp.Solver):
            raise TypeError("Joint linear model requires an MPSolver")
        solver.ExportModelToProto(proto)
        return proto

    def _terms(self, key, local, choices, parties):
        terms = EffectTerms(
            base={c: [] for c in CATEGORIES},
            minor_base={c: [] for c in CATEGORIES},
            modifiers={c: [] for c in CATEGORIES},
            minor_sites={s.id for s in local.scenario.sites if not s.major},
            tax=[],
            flat_income=[],
            minor_modifiers=[],
            food=local.scenario.external_food
            + local.fixed_value("food_per_provinces")
            + len(local.scenario.sites) * local.fixed_value("food_per_regions"),
            order=local.scenario.order_offset
            + local.fixed_value("order")
            + local.fixed_value("own_culture_order"),
        )
        RomeCompiler(local)._compile_party_effects(parties, terms)
        for pair, effect, count, is_source in self.effects[key]:
            self._effect(effect, pair, choices[pair], terms, count, is_source)
        return terms

    @staticmethod
    def _effect(effect, pair, variable, terms, count, is_source):
        if RomeCompiler._compile_wealth_effect(effect, pair, variable, terms):
            return
        if effect.kind == "food":
            terms.food += effect.value * count * variable
        elif effect.kind == "order":
            terms.order += effect.value * variable
        elif effect.kind == "tax_percent":
            terms.tax.append((effect.value, variable))
        elif effect.kind == "income_flat" and is_source:
            # A faction maintenance charge is paid once for its source building.
            terms.flat_income.append((effect.value, variable))
        elif effect.kind == "minor_wealth_percent":
            terms.minor_modifiers.append((effect.value, variable))

    @staticmethod
    def _income(local, terms, products, solver, native):
        wealth, upper, combined = RomeCompiler(local)._compile_wealth(
            terms, products.selection_upper, solver, native, products.weighted_products
        )
        total = sum(wealth)
        upper = min(upper, products.selection_upper(combined))
        factor = (
            100
            + local.scenario.tax_points
            - local.effective_corruption
            + local.fixed_value("tax_percent")
        )
        if native:
            income = HoldingCompiler._native_income(
                total, upper, factor, terms.tax, products, solver
            )
        else:
            income = products.income(total, factor, terms.tax, upper)
        return income + sum(a * 10000 * v for a, v in terms.flat_income)

    @staticmethod
    def _native_income(total, upper, factor, tax, products, solver):
        amounts = defaultdict(int)
        for amount, variable in tax:
            amounts[variable_name(variable)] += amount
        ceiling = factor + products.selection_upper(tax)
        wealth = solver.IntVar(0, upper, "total_wealth_hundredths")
        rate = solver.IntVar(
            max(0, factor + sum(min(0, a) for a in amounts.values())), ceiling, "tax_factor"
        )
        income = solver.IntVar(0, upper * ceiling, "income_ten_thousandths")
        solver.Add(wealth == total)
        solver.Add(rate == factor + sum(a * v for a, v in tax))
        solver.multiply(income, wealth, rate)
        return income
