"""Exact selected-wealth products and implied selection bounds."""

from collections import defaultdict


def variable_name(variable):
    return variable.name() if callable(variable.name) else variable.name


def preserve_base_domain(solver, expression, terms):
    if any(amount < 0 for amount, _ in terms):
        solver.Add(expression >= 0)


def preserve_minor_domains(solver, expression, base, modifiers):
    preserve_base_domain(solver, expression, base)
    if any(amount < 0 for amount, _ in modifiers):
        solver.Add(sum(a * v for a, v in modifiers) >= 0)


class LinearProducts:
    def __init__(self, economy, solver, choices, parties):
        self.economy, self.solver = economy, solver
        self.choices, self.parties = choices, parties
        self.counter = 0
        self.groups = list(self.selection_groups())

    def site_groups(self, site):
        from games.tw.rome2.placement import branch

        roles, branches = defaultdict(list), defaultdict(list)
        for pair, variable in self.choices.items():
            if pair[0] == site.id:
                role = self.economy.roles[pair]
                roles[role].append(variable)
                if role == "ordinary":
                    branches[branch(self.economy.candidates[pair[0]][pair[1]])].append(variable)
        return roles, branches

    def selection_groups(self):
        for site in self.economy.scenario.sites:
            roles, branches = self.site_groups(site)
            yield roles["primary"], 1, True
            if roles["port"]:
                yield roles["port"], 1, True
            yield roles["ordinary"], site.capacity, False
            for variables in branches.values():
                yield variables, 1, False
        yield list(self.parties.values()), 1, True

    def selection_upper(self, terms):
        amounts = defaultdict(int)
        for amount, variable in terms:
            amounts[variable_name(variable)] += amount
        upper = sum(self.site_upper(site, amounts) for site in self.economy.scenario.sites)
        return upper + max(
            (max(0, amounts[variable_name(v)]) for v in self.parties.values()), default=0
        )

    def site_upper(self, site, amounts):
        roles, branches = self.site_groups(site)

        def maximum(variables):
            return max((max(0, amounts[variable_name(v)]) for v in variables), default=0)

        ordinary = sorted((maximum(v) for v in branches.values()), reverse=True)
        return maximum(roles["primary"]) + maximum(roles["port"]) + sum(ordinary[: site.capacity])

    def selected_product(self, expression, selector, upper):
        self.counter += 1
        result = self.solver.IntVar(0, upper, f"selected_product:{self.counter}")
        self.solver.Add(result <= upper * selector)
        self.solver.Add(result <= expression)
        self.solver.Add(result >= expression - upper * (1 - selector))
        return result

    def income(self, wealth, factor, tax, upper):
        if factor + sum(min(0, amount) for amount, _ in tax) < 0:
            self.solver.Add(factor + sum(a * v for a, v in tax) >= 0)
        return factor * wealth + self.weighted_products(wealth, tax, upper)

    def weighted_products(self, expression, terms, upper):
        amounts, lookup = defaultdict(int), {}
        for amount, variable in terms:
            name = variable_name(variable)
            amounts[name] += amount
            lookup[name] = variable
        products = {
            name: self.selected_product(expression, lookup[name], upper)
            for name, amount in amounts.items()
            if amount
        }
        self.strengthen(expression, products)
        return sum(amount * products[name] for name, amount in amounts.items() if amount)

    def strengthen(self, expression, products):
        # Multiply each existing selection rule by the same nonnegative wealth.
        # This strengthens fractional bounds and preserves every integer layout.
        for variables, capacity, exact in self.groups:
            names = [variable_name(variable) for variable in variables]
            present = [products[name] for name in names if name in products]
            if len(present) > capacity:
                self.solver.Add(sum(present) <= capacity * expression)
            if exact and present and len(present) == len(names):
                self.solver.Add(sum(present) == capacity * expression)
