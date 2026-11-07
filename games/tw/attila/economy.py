"""Scoped static province economy, compiled exactly with binary products.

Wealth modifiers stack additively within each category. Tax modifiers apply to
that wealth only for the optional net-income objective. This models building
contributions, not campaign corruption, trade agreements or population income.
"""

from collections import defaultdict
from fractions import Fraction
from math import isfinite, lcm
from types import SimpleNamespace

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
    def __init__(self, provinces, adjacency=None, scenario=None):
        self.provinces = provinces
        self.regions = [r for p in provinces for r in p.regions]
        self.buildings = [b for r in self.regions for b in r.buildings]
        self.by_id = {b.get_name(): b for b in self.buildings}
        if len(self.by_id) != len(self.buildings) or any(
            name.startswith(("__", "@external_")) for name in self.by_id
        ):
            raise ValueError(
                "Building identifiers must be unique and not use reserved prefixes"
            )
        self.owner = {r.name: p.name for p in provinces for r in p.regions}
        from games.tw.attila.scenario import Scenario

        self.scenario = (
            scenario if isinstance(scenario, Scenario) else Scenario(scenario)
        ).bind(provinces)
        self.adjacency = (
            adjacency
            if adjacency is not None
            else self.scenario.data.get("adjacency", {})
        )
        # Validate API-supplied adjacency too; never silently ignore absent neighbors.
        Scenario({"adjacency": self.adjacency}).bind(provinces)
        self.sources = list(self.buildings)
        region_by_id = {r.name: r for r in self.regions}
        for i, record in enumerate(self.scenario.data.get("external_effects", [])):
            source = SimpleNamespace(
                name=f"@external_{i}",
                region=region_by_id[record["region"]],
                raw_effects={(record["effect"], record["scope"]): record["amount"]},
            )
            self.sources.append(source)
        self.logic = {}
        self._logic_variables = {}
        self._serial = 0
        self.products = {}
        self._fields = {}
        self._wealth = {}
        self._metrics = {}
        from games.tw.games import Games

        state = getattr(getattr(Games.instance, "religion", None), "value", None)
        self.state_religion = {"eastern": "church_east", "tengris": "tengri"}.get(
            state, state
        )
        if self.state_religion == "any":
            self.state_religion = None
        self.base_fertility = {
            r.name: Games.fertility if r.fertility is None else r.fertility
            for r in self.regions
        }
        if any(
            not isfinite(value) or value < 0 for value in self.base_fertility.values()
        ):
            raise ValueError("Fertility must be finite and nonnegative")
        self.omitted = []
        for b in self.sources:
            for key, rule, scope, _ in entries(b):
                if (
                    rule.kind == "conditional_fertility_food"
                    and key not in self.scenario.data.get("conditional_targets", {})
                ):
                    self.omitted.append((b.name, key, "requires_explicit_recipients"))
                elif rule.kind == "unmodeled" or scope == Reach.OTHER:
                    self.omitted.append((b.name, key, scope.value))
                elif scope == Reach.ADJACENT and not adjacency:
                    self.omitted.append((b.name, key, "adjacency_not_supplied"))
                elif scope == Reach.CONDITIONAL and key not in self.scenario.data.get(
                    "conditional_targets", {}
                ):
                    self.omitted.append(
                        (b.name, key, "requires_food_sharing_condition")
                    )
                elif (
                    rule.kind.startswith("immigration_")
                    and not self.scenario.data.get("provinces")
                    and not self.scenario.data.get("regions")
                ):
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

    def applies(self, source, target_region, scope, effect, recipient=None):
        mapping = self.scenario.data.get("conditional_targets", {}).get(effect)
        if mapping is not None and (
            scope == Reach.CONDITIONAL
            or effect == "att_effect_food_production_fertility_neighbouring"
        ):
            return self.owner[target_region.name] in mapping.get(
                self.owner[source.region.name], ()
            )
        if effect == "att_effect_food_production_fertility_neighbouring":
            return False
        return self.targets(source, target_region, scope, recipient)

    @staticmethod
    def decision(source):
        return () if source.name.startswith("@external_") else (source.get_name(),)

    def field(self, region, kind, category=None, recipient=None):
        cache_key = (
            region.name,
            kind,
            category,
            None if recipient is None else recipient.name,
        )
        if cache_key in self._fields:
            return self._fields[cache_key]
        result = defaultdict(Fraction)
        for b in self.sources:
            for effect, rule, scope, value in entries(b):
                if (
                    rule.kind == kind
                    and (category is None or category in rule.categories)
                    and self.applies(b, region, scope, effect, recipient)
                ):
                    result[self.decision(b)] += rational(value)
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
        for producer in self.sources:
            for effect, rule, scope, value in entries(producer):
                if rule.kind not in ("wealth", "fertility_wealth") or not self.applies(
                    producer, region, scope, effect
                ):
                    continue
                base = {self.decision(producer): value}
                if rule.kind == "fertility_wealth":
                    base = multiply(base, self.fertility(region))
                for category in rule.categories:
                    modifier = {
                        key: value / 100
                        for key, value in self.field(
                            region, "wealth_percent", category, producer
                        ).items()
                    }
                    external = self.scenario.region(region, "wealth_percent", {})
                    modifier = add(
                        modifier,
                        {
                            (): rational(
                                external.get("all", 0) + external.get(category, 0)
                            )
                            / 100
                        },
                    )
                    total = add(total, multiply(base, add({(): 1}, modifier)))
        immigration = self.scenario.region(region, "immigration_wealth")
        if immigration:
            modifier = {
                key: value / 100
                for key, value in self.field(
                    region, "immigration_wealth_percent"
                ).items()
            }
            total = add(
                total,
                multiply({(): immigration}, self.floor_zero(add({(): 1}, modifier))),
            )
        self._wealth[region.name] = total
        return total

    def food(self, region):
        consumption = {
            key: -value for key, value in self.field(region, "food_consumption").items()
        }
        return add(
            add(
                add(self.field(region, "food"), consumption),
                {(): self.scenario.region(region, "food")},
            ),
            multiply(
                add(
                    self.field(region, "fertility_food"),
                    self.field(region, "conditional_fertility_food"),
                ),
                self.fertility(region),
            ),
        )

    def province_field(self, province, kind):
        result = {}
        for source in self.sources:
            for effect, rule, scope, value in entries(source):
                if rule.kind == kind and any(
                    self.applies(source, r, scope, effect) for r in province.regions
                ):
                    result = add(result, {self.decision(source): value})
        return result

    def public_order(self, province):
        result = add(
            self.province_field(province, "public_order"),
            {(): self.scenario.province(province, "public_order")},
        )
        base = self.scenario.province(province, "immigration_order")
        if base:
            modifier = {
                key: value / 100
                for key, value in self.province_field(
                    province, "immigration_order_percent"
                ).items()
            }
            result = add(
                result, multiply({(): base}, self.floor_zero(add({(): 1}, modifier)))
            )
        return result

    def sanitation(self, region):
        return add(
            add(
                self.field(region, "sanitation"),
                {(): self.scenario.region(region, "sanitation")},
            ),
            {key: -value for key, value in self.field(region, "squalor").items()},
        )

    def indicator(self, terms):
        """Exact Boolean predicate terms >= 0 on the rational coefficient grid."""
        terms = add({}, terms)
        lower = terms.get((), 0) + sum(min(0, v) for k, v in terms.items() if k)
        upper = terms.get((), 0) + sum(max(0, v) for k, v in terms.items() if k)
        if lower >= 0:
            return {(): 1}
        if upper < 0:
            return {}
        identity = tuple(sorted(terms.items()))
        for name, info in self.logic.items():
            if info[0] == identity:
                return {(name,): 1}
        name = f"__gate_{self._serial}"
        self._serial += 1
        step = Fraction(1, lcm(*(rational(v).denominator for v in terms.values())))
        self.logic[name] = (identity, terms, lower, upper, step)
        return {(name,): 1}

    def floor_zero(self, terms):
        return multiply(terms, self.indicator(terms))

    def cap(self, terms, maximum):
        return add(
            terms,
            {k: -v for k, v in self.floor_zero(add(terms, {(): -maximum})).items()},
        )

    def corruption(self, region):
        base = (
            rational(
                self.scenario.province(self.owner[region.name], "corruption_percent")
            )
            / 100
        )
        if not base:
            return {}
        modifiers = {
            key: value / 100
            for key, value in self.field(region, "corruption_percent").items()
        }
        return self.cap(
            self.floor_zero(multiply({(): base}, add({(): 1}, modifiers))), 1
        )

    def metric(self, metric, scope="faction", target="faction"):
        from games.tw.attila.effects import METRICS

        if metric not in METRICS or scope not in {"region", "province", "faction"}:
            raise ValueError("Unknown metric or scope")
        known = (
            {r.name for r in self.regions}
            if scope == "region"
            else {p.name for p in self.provinces}
            if scope == "province"
            else {"faction"}
        )
        if target not in known:
            raise ValueError("Unknown metric target")
        aliases = {metric}
        if self.state_religion:
            if metric == "religion:state":
                aliases.add("religion:" + self.state_religion)
            if metric == "religion:" + self.state_religion:
                aliases.add("religion:state")
        cache_key = (metric, scope, target)
        if cache_key in self._metrics:
            return self._metrics[cache_key]
        regions = (
            [r for r in self.regions if r.name == target]
            if scope == "region"
            else [r for r in self.regions if self.owner[r.name] == target]
            if scope == "province"
            else self.regions
        )
        result = {}
        # Aggregate effects over their natural recipients, not over arbitrary
        # iteration counts. Global research/caps apply once to the faction.
        faction_metric = metric == "research_percent" or metric.startswith("agent_cap:")
        region_metric = (
            metric.startswith(("resource:", "religion:")) or metric == "roads"
        )
        for source in self.sources:
            for effect, rule, reach_, value in entries(source):
                if rule.kind != "metric" or not aliases.intersection(rule.categories):
                    continue
                recipients = [
                    r for r in regions if self.applies(source, r, reach_, effect)
                ]
                count = (
                    bool(recipients)
                    if faction_metric
                    else len(recipients)
                    if region_metric
                    else len({self.owner[r.name] for r in recipients})
                )
                if count:
                    result = add(result, {self.decision(source): value * count})
        if metric.startswith("agent_enable:"):
            result = self.indicator(add(result, {(): -1}))
        self._metrics[cache_key] = result
        return result

    def export_income(self):
        tariffs = {}
        for source in self.sources:
            for _, rule, scope, value in entries(source):
                if rule.kind == "tariff_percent" and scope == Reach.FACTION:
                    tariffs = add(
                        tariffs, {self.decision(source): rational(value) / 100}
                    )
        total = multiply(
            {(): self.scenario.data.get("base_tariffs", 0)}, add({(): 1}, tariffs)
        )
        for resource, price in self.scenario.data.get("resource_prices", {}).items():
            quantity = self.floor_zero(self.metric(f"resource:{resource}"))
            if resource in self.scenario.data.get("resource_demand", {}):
                quantity = self.cap(
                    quantity, self.scenario.data["resource_demand"][resource]
                )
            total = add(total, multiply(quantity, {(): price}))
        return total

    def project_cost(self):
        total = {}
        region_by_id = {r.name: r for r in self.regions}
        for project in self.scenario.data.get("projects", []):
            region = region_by_id[project["region"]]
            modifiers = self.field(
                region,
                "conversion_cost_percent"
                if project.get("conversion")
                else "construction_percent",
            )
            if project.get("sanitation") and not project.get("conversion"):
                modifiers = add(
                    modifiers, self.field(region, "sanitation_cost_percent")
                )
            factor = self.floor_zero(
                add({(): 1}, {k: v / 100 for k, v in modifiers.items()})
            )
            total = add(total, multiply({(): project["base_cost"]}, factor))
        return total

    def objective(self, mode="wealth"):
        total = {}
        for region in self.regions:
            wealth = self.wealth(region)
            if mode == "income":
                tax = {
                    key: value / 100
                    for key, value in self.field(region, "tax_percent").items()
                }
                base_tax = (
                    rational(
                        self.scenario.province(
                            self.owner[region.name], "tax_percent", 100
                        )
                    )
                    / 100
                )
                wealth = multiply(
                    multiply(wealth, self.floor_zero(add({(): base_tax}, tax))),
                    add({(): 1}, {k: -v for k, v in self.corruption(region).items()}),
                )
            total = add(total, wealth)
        if mode == "income":
            for b in self.buildings:
                if b.metadata is None:
                    raise ValueError(f"Missing imported upkeep metadata for {b.name}")
                total = add(total, {(b.get_name(),): -b.metadata["metadata"]["upkeep"]})
        if mode == "income":
            total = add(total, self.export_income())
        for weight in self.scenario.data.get("weights", []):
            total = add(
                total,
                multiply(
                    self.metric(
                        weight["metric"],
                        weight["scope"],
                        weight.get("target", "faction"),
                    ),
                    {(): weight["value"]},
                ),
            )
        return total

    def variable(self, name, solver):
        if name not in self.logic:
            return self.by_id[name].lp_variable
        if name not in self._logic_variables:
            _, terms, lower, upper, step = self.logic[name]
            variable = solver.create_auxiliary(name)
            self._logic_variables[name] = variable
            expression = self.compile(terms, solver)
            solver.create_constraint(
                name + "_lower",
                expression + [float(lower) * variable],
                constraint_fn=lambda x: x >= float(lower),
            )
            solver.create_constraint(
                name + "_upper",
                expression + [-float(upper + step) * variable],
                constraint_fn=lambda x: x <= -float(step),
            )
        return self._logic_variables[name]

    def compile(self, terms, solver):
        result = []
        for monomial, coefficient in terms.items():
            if not monomial:
                result.append(float(coefficient))
                continue
            key = (monomial[0],)
            variable = self.variable(key[0], solver)
            for name in monomial[1:]:
                key = tuple(sorted((*key, name)))
                if key not in self.products:
                    self.products[key] = solver.create_product(
                        variable,
                        self.variable(name, solver),
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
                    constraint_fn=lambda total, r=region: (
                        total >= self.scenario.region(r, "minimum_sanitation", 1)
                    ),
                )
            solver.create_constraint(
                f"{province.name}_Scoped_Food",
                self.compile(
                    add(food, {(): self.scenario.province(province, "food")}), solver
                ),
                constraint_fn=lambda total, p=province: (
                    total >= self.scenario.province(p, "minimum_food")
                ),
            )
            solver.create_constraint(
                f"{province.name}_Scoped_Order",
                self.compile(self.public_order(province), solver),
                constraint_fn=lambda total, p=province: (
                    total >= self.scenario.province(p, "minimum_public_order")
                ),
            )

        for i, target in enumerate(self.scenario.data.get("targets", [])):
            terms = self.metric(
                target["metric"], target["scope"], target.get("target", "faction")
            )
            solver.create_constraint(
                f"Scenario_Target_{i}",
                self.compile(terms, solver),
                constraint_fn=lambda x, t=target: x >= t["value"],
            )
        if "project_budget" in self.scenario.data:
            solver.create_constraint(
                "Project_Budget",
                self.compile(self.project_cost(), solver),
                constraint_fn=lambda x: x <= self.scenario.data["project_budget"],
            )

    def evaluate(self, terms, selected):
        cache = {}

        def enabled(name):
            if name not in self.logic:
                return name in selected
            if name not in cache:
                expression = self.logic[name][1]
                cache[name] = (
                    sum(v for k, v in expression.items() if all(enabled(n) for n in k))
                    >= 0
                )
            return cache[name]

        return float(
            sum(
                value
                for monomial, value in terms.items()
                if all(enabled(key) for key in monomial)
            )
        )

    def evaluate_layout(self, selected, mode="wealth"):
        from games.tw.attila.effects import METRICS

        return {
            "state_religion": self.state_religion,
            "metric_semantics": "Scoped effect totals and capabilities; not a forecast of conversion or research completion",
            "targets": [
                {
                    **target,
                    "actual": self.evaluate(
                        self.metric(
                            target["metric"],
                            target["scope"],
                            target.get("target", "faction"),
                        ),
                        selected,
                    ),
                }
                for target in self.scenario.data.get("targets", [])
            ],
            "weighted_metrics": [
                {
                    **target,
                    "actual": self.evaluate(
                        self.metric(
                            target["metric"],
                            target["scope"],
                            target.get("target", "faction"),
                        ),
                        selected,
                    ),
                }
                for target in self.scenario.data.get("weights", [])
            ],
            "metrics": {
                metric: self.evaluate(self.metric(metric), selected)
                for metric in sorted(METRICS)
                if self.metric(metric)
            },
            "export_income": self.evaluate(self.export_income(), selected),
            "project_cost": self.evaluate(self.project_cost(), selected),
            "objective_kind": "weighted_" + mode
            if self.scenario.data.get("weights")
            else mode,
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
            "corruption_percent": {
                r.name: 100 * self.evaluate(self.corruption(r), selected)
                for r in self.regions
            },
            "province_food": {
                p.name: sum(self.evaluate(self.food(r), selected) for r in p.regions)
                + self.scenario.province(p, "food")
                for p in self.provinces
            },
            "public_order": {
                p.name: self.evaluate(self.public_order(p), selected)
                for p in self.provinces
            },
        }
