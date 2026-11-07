"""Scoped static province economy, compiled exactly with binary products.

Wealth modifiers stack additively within each category. Tax modifiers apply to
that wealth only for the optional net-income objective. This models building
contributions, not campaign corruption, trade agreements or population income.
"""

from collections import defaultdict
from fractions import Fraction
from math import isfinite

from games.tw.attila.effects import Reach, entries


def rational(value):
    return value if isinstance(value, Fraction) else Fraction(str(value))


def add(left, right):
    result = defaultdict(
        Fraction, {key: rational(value) for key, value in left.items()}
    )
    for key, value in right.items():
        result[key] += rational(value)
    return {key: value for key, value in result.items() if value}


def multiply(left, right):
    result = defaultdict(Fraction)
    for a, x in left.items():
        for b, y in right.items():
            # Decisions are Boolean: x*x == x. Sorted keys share auxiliaries.
            result[tuple(sorted(set(a) | set(b)))] += rational(x) * rational(y)
    return dict(result)


class Economy:
    def __init__(self, provinces, adjacency=None):
        self.provinces = provinces
        self.regions = [r for p in provinces for r in p.regions]
        self.buildings = [b for r in self.regions for b in r.buildings]
        self.by_id = {b.get_name(): b for b in self.buildings}
        self.owner = {r.name: p.name for p in provinces for r in p.regions}
        self.adjacency = adjacency or {}
        self.products = {}
        self._fields = {}
        self._wealth = {}
        from games.tw.games import Games

        self.base_fertility = {
            r.name: Games.fertility if r.fertility is None else r.fertility
            for r in self.regions
        }
        if any(
            not isfinite(value) or value < 0 for value in self.base_fertility.values()
        ):
            raise ValueError("Fertility must be finite and nonnegative")
        self.omitted = []
        for b in self.buildings:
            for key, rule, scope, _ in entries(b):
                if rule.kind == "unmodeled" or scope == Reach.OTHER:
                    self.omitted.append((b.name, key, scope.value))
                elif scope == Reach.ADJACENT and not adjacency:
                    self.omitted.append((b.name, key, "adjacency_not_supplied"))
                elif scope == Reach.CONDITIONAL:
                    self.omitted.append((b.name, key, "requires_food_sharing_condition"))
                elif rule.kind.startswith("immigration_"):
                    self.omitted.append(
                        (b.name, key, "requires_external_immigration_scenario")
                    )

    def targets(self, source, target_region, scope, recipient=None):
        if scope == Reach.BUILDING:
            return (
                source is recipient
                if recipient is not None
                else source.region is target_region
            )
        if scope == Reach.LOCAL:
            return source.region is target_region
        if scope == Reach.PROVINCE:
            return self.owner[source.region.name] == self.owner[target_region.name]
        if scope == Reach.FACTION:
            return True  # All provinces in one Problem belong to the same faction.
        if scope == Reach.ADJACENT:
            return self.owner[target_region.name] in self.adjacency.get(
                self.owner[source.region.name], ()
            )
        return False

    def field(self, region, kind, category=None, recipient=None):
        cache_key = (
            region.name,
            kind,
            category,
            None if recipient is None else recipient.get_name(),
        )
        if cache_key in self._fields:
            return self._fields[cache_key]
        result = defaultdict(Fraction)
        for b in self.buildings:
            for _, rule, scope, value in entries(b):
                if (
                    rule.kind == kind
                    and (category is None or category in rule.categories)
                    and self.targets(b, region, scope, recipient)
                ):
                    result[(b.get_name(),)] += rational(value)
        self._fields[cache_key] = dict(result)
        return self._fields[cache_key]

    def fertility(self, region):
        return add(
            {(): self.base_fertility[region.name]}, self.field(region, "fertility")
        )

    def wealth(self, region):
        if region.name in self._wealth:
            return self._wealth[region.name]
        total = {}
        for producer in self.buildings:
            for _, rule, scope, value in entries(producer):
                if rule.kind not in ("wealth", "fertility_wealth") or not self.targets(
                    producer, region, scope
                ):
                    continue
                base = {(producer.get_name(),): value}
                if rule.kind == "fertility_wealth":
                    base = multiply(base, self.fertility(region))
                for category in rule.categories:
                    modifier = {
                        key: value / 100
                        for key, value in self.field(
                            region, "wealth_percent", category, producer
                        ).items()
                    }
                    total = add(total, multiply(base, add({(): 1}, modifier)))
        self._wealth[region.name] = total
        return total

    def food(self, region):
        consumption = {
            key: -value for key, value in self.field(region, "food_consumption").items()
        }
        return add(
            add(self.field(region, "food"), consumption),
            multiply(self.field(region, "fertility_food"), self.fertility(region)),
        )

    def public_order(self, province):
        # Province/faction public order contributes once per province, not once
        # per receiving region. LOCAL contributions also feed that province.
        result = {}
        for b in self.buildings:
            for _, rule, scope, value in entries(b):
                if rule.kind == "public_order" and any(
                    self.targets(b, r, scope) for r in province.regions
                ):
                    result = add(result, {(b.get_name(),): value})
        return result

    def sanitation(self, region):
        return add(
            self.field(region, "sanitation"),
            {key: -value for key, value in self.field(region, "squalor").items()},
        )

    def objective(self, mode="wealth"):
        total = {}
        for region in self.regions:
            wealth = self.wealth(region)
            if mode == "income":
                tax = {
                    key: value / 100
                    for key, value in self.field(region, "tax_percent").items()
                }
                wealth = multiply(wealth, add({(): 1}, tax))
            total = add(total, wealth)
        if mode == "income":
            for b in self.buildings:
                if b.metadata is None:
                    raise ValueError(f"Missing imported upkeep metadata for {b.name}")
                total = add(total, {(b.get_name(),): -b.metadata["metadata"]["upkeep"]})
        return total

    def compile(self, terms, solver):
        result = []
        for monomial, coefficient in terms.items():
            if not monomial:
                result.append(float(coefficient))
                continue
            key = (monomial[0],)
            variable = self.by_id[key[0]].lp_variable
            for name in monomial[1:]:
                key = tuple(sorted((*key, name)))
                if key not in self.products:
                    self.products[key] = solver.create_product(
                        variable,
                        self.by_id[name].lp_variable,
                        f"__and_{len(self.products)}",
                    )
                variable = self.products[key]
            result.append(float(coefficient) * variable)
        return result

    def install_constraints(self, solver):
        for province in self.provinces:
            food = {}
            for region in province.regions:
                food = add(food, self.food(region))
                solver.create_constraint(
                    f"{region.name}_Scoped_Sanitation",
                    self.compile(self.sanitation(region), solver),
                    constraint_fn=lambda total: total >= 1,
                )
            solver.create_constraint(
                f"{province.name}_Scoped_Food",
                self.compile(food, solver),
                constraint_fn=lambda total: total >= 0,
            )
            solver.create_constraint(
                f"{province.name}_Scoped_Order",
                self.compile(self.public_order(province), solver),
                constraint_fn=lambda total: total >= 0,
            )

    @staticmethod
    def evaluate(terms, selected):
        return float(
            sum(
                value
                for monomial, value in terms.items()
                if all(key in selected for key in monomial)
            )
        )

    def evaluate_layout(self, selected, mode="wealth"):
        return {
            "objective": self.evaluate(self.objective(mode), selected),
            "regions": {
                r.name: {
                    "wealth": self.evaluate(self.wealth(r), selected),
                    "food": self.evaluate(self.food(r), selected),
                    "sanitation": self.evaluate(self.sanitation(r), selected),
                    "fertility": self.evaluate(self.fertility(r), selected),
                }
                for r in self.regions
            },
            "public_order": {
                p.name: self.evaluate(self.public_order(p), selected)
                for p in self.provinces
            },
        }
