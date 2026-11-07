"""Scoped static province economy, compiled exactly with binary products.

Wealth modifiers stack additively within each category. The default income
objective applies tax/corruption and subtracts upkeep. Campaign quantities which
cannot be inferred from the catalog are explicit scenario inputs.
"""

from collections import defaultdict
from fractions import Fraction
from math import isfinite, lcm
from types import SimpleNamespace

from games.tw.attila.effects import Reach, entries


def rational(value):
    return value if isinstance(value, Fraction) else Fraction(str(value))


def add(left, right):
    result = defaultdict(Fraction, {key: rational(value) for key, value in left.items()})
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
    def __init__(self, provinces, adjacency=None, scenario=None, technology_profile=None):
        self.catalogue_exclusions: list[dict] = []
        self.provinces = provinces
        self.regions = [r for p in provinces for r in p.regions]
        self.buildings = [b for r in self.regions for b in r.buildings]
        self.by_id = {b.get_name(): b for b in self.buildings}
        if len(self.by_id) != len(self.buildings) or any(
            name.startswith(("__", "@external_")) for name in self.by_id
        ):
            raise ValueError("Building identifiers must be unique and not use reserved prefixes")
        self.owner = {r.name: p.name for p in provinces for r in p.regions}
        from games.tw.attila.scenario import Scenario

        self.scenario = (scenario if isinstance(scenario, Scenario) else Scenario(scenario)).bind(
            provinces
        )
        self.adjacency = (
            adjacency if adjacency is not None else self.scenario.data.get("adjacency", {})
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
        self.state_religion = {"eastern": "church_east", "tengris": "tengri"}.get(state, state)
        if self.state_religion == "any":
            self.state_religion = None
        self.base_fertility = {
            r.name: Games.fertility if r.fertility is None else r.fertility for r in self.regions
        }
        if any(not isfinite(value) or value < 0 for value in self.base_fertility.values()):
            raise ValueError("Fertility must be finite and nonnegative")
        from games.tw.attila.traits import profile, rules
        from games.tw.models.model import RegionType

        faction = getattr(getattr(Games.instance, "faction", None), "value", None)
        self.traits = profile(faction, self.scenario.data.get("faction_traits", True))
        self.farms_without_penalties = bool(rules(self.traits, "farms_without_penalties"))
        self.campaign = self.scenario.data.get("campaign", {})
        selected_capitals = sum(r.region_type == RegionType.REGION_MAJOR for r in self.regions)
        self.capitals_held = self.campaign.get("province_capitals_held", selected_capitals)
        if self.capitals_held < selected_capitals:
            raise ValueError("province_capitals_held cannot be below the selected owned capitals")
        self._add_trait_sources()
        from games.tw.attila.modifiers import modifier_profile

        self.modifiers, semantic_effects = modifier_profile(
            Games.instance, technology_profile, self.scenario.data
        )
        if semantic_effects:
            self.sources.append(
                SimpleNamespace(
                    name="@external_modifiers",
                    region=self.regions[0],
                    semantic_effects=semantic_effects,
                )
            )
        self._record_trait_requirements()
        self._record_omitted_effects()

    def _record_omitted_effects(self):
        self.omitted = []
        for b in self.sources:
            for key, rule, scope, _ in self.effects(b):
                if rule.kind == "conditional_fertility_food" and key not in self.scenario.data.get(
                    "conditional_targets", {}
                ):
                    self.omitted.append((b.name, key, "requires_explicit_recipients"))
                elif rule.kind == "unmodeled" or scope == Reach.OTHER:
                    self.omitted.append((b.name, key, scope.value))
                elif scope == Reach.ADJACENT and not self.adjacency:
                    self.omitted.append((b.name, key, "adjacency_not_supplied"))
                elif scope == Reach.CONDITIONAL and key not in self.scenario.data.get(
                    "conditional_targets", {}
                ):
                    self.omitted.append((b.name, key, "requires_food_sharing_condition"))
                elif (
                    rule.kind.startswith("immigration_")
                    and not self.scenario.data.get("provinces")
                    and not self.scenario.data.get("regions")
                ):
                    self.omitted.append((b.name, key, "requires_external_immigration_scenario"))

    def _record_trait_requirements(self):
        for record in self.traits["traits"]:
            rule = record["rule"]
            if rule and rule[0] == "excluded_treasury_interest":
                record["status"] = "excluded_by_requested_objective"
            required = {
                "peace_subsidy": "at_peace_with_sassanids",
                "trade_food": "active_trade_routes",
                "poor_fertility_food": "poor_fertility_regions",
                "tribute_percent": "base_tribute",
            }
            if rule and rule[0] in required and required[rule[0]] not in self.campaign:
                record["status"] = "requires_campaign_input"
                record["required_input"] = required[rule[0]]

    def _add_trait_sources(self):
        from games.tw.attila.traits import rules

        effects = [(rule[1], rule[2]) for rule in rules(self.traits, "effect")]
        if rules(self.traits, "capital_sanitation"):
            effects.append(("att_effect_sanitation_buildings", self.capitals_held))
        if rules(self.traits, "venedian_penalty"):
            effects.extend(
                ("att_effect_economy_gdp_mod_" + category, -50)
                for category in ("commerce_all", "industry", "culture")
            )
        for i, (effect, value) in enumerate(effects):
            self.sources.append(
                SimpleNamespace(
                    name=f"@external_trait_{i}",
                    region=self.regions[0],
                    raw_effects={
                        (
                            effect,
                            "faction_to_region_own"
                            if effect != "att_effect_economy_trade_tariff_mod"
                            else "faction_to_faction_own",
                        ): value
                    },
                )
            )

    def effects(self, source):
        farm = source.name == "farm" or "_farm_" in source.name
        for effect, rule, scope, value in entries(source):
            if (
                self.farms_without_penalties
                and farm
                and (
                    (rule.kind == "squalor" and value > 0)
                    or (rule.kind == "public_order" and value < 0)
                )
            ):
                continue
            yield effect, rule, scope, value

    def targets(self, source, target_region, scope, recipient=None):
        if scope == Reach.BUILDING:
            return source is recipient if recipient is not None else source.region is target_region
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
            return self.owner[target_region.name] in mapping.get(self.owner[source.region.name], ())
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
            for effect, rule, scope, value in self.effects(b):
                if (
                    rule.kind == kind
                    and (category is None or category in rule.categories)
                    and self.applies(b, region, scope, effect, recipient)
                ):
                    result[self.decision(b)] += rational(value)
        self._fields[cache_key] = dict(result)
        return self._fields[cache_key]

    def fertility(self, region):
        return add({(): self.base_fertility[region.name]}, self.field(region, "fertility"))

    def wealth(self, region):
        if region.name in self._wealth:
            return self._wealth[region.name]
        total = {}
        for producer in self.sources:
            for effect, rule, scope, value in self.effects(producer):
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
                        {(): rational(external.get("all", 0) + external.get(category, 0)) / 100},
                    )
                    total = add(total, multiply(base, add({(): 1}, modifier)))
        immigration = self.scenario.region(region, "immigration_wealth")
        if immigration:
            modifier = {
                key: value / 100
                for key, value in self.field(region, "immigration_wealth_percent").items()
            }
            total = add(
                total,
                multiply({(): immigration}, self.floor_zero(add({(): 1}, modifier))),
            )
        self._wealth[region.name] = total
        return total

    def food(self, region):
        from games.tw.attila.traits import rules

        trait_food = 0
        if rules(self.traits, "poor_fertility_food") and region.name in self.campaign.get(
            "poor_fertility_regions", []
        ):
            trait_food += 15
        if rules(self.traits, "trade_food"):
            # This is a provincial total, credited once to its first region.
            province = next(p for p in self.provinces if p.name == self.owner[region.name])
            if region is province.regions[0]:
                trait_food += min(150, 30 * self.campaign.get("active_trade_routes", 0))
        consumption = {key: -value for key, value in self.field(region, "food_consumption").items()}
        return add(
            add(
                add(self.field(region, "food"), consumption),
                {(): rational(self.scenario.region(region, "food")) + trait_food},
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
            for effect, rule, scope, value in self.effects(source):
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
                for key, value in self.province_field(province, "immigration_order_percent").items()
            }
            result = add(result, multiply({(): base}, self.floor_zero(add({(): 1}, modifier))))
        religious = self.scenario.province(province, "religious_order")
        if religious:
            modifier = {
                key: value / 100
                for key, value in self.province_field(province, "religious_order_percent").items()
            }
            result = add(
                result,
                multiply({(): religious}, self.floor_zero(add({(): 1}, modifier))),
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
        base = rational(self.scenario.province(self.owner[region.name], "corruption_percent")) / 100
        if not base:
            return {}
        modifiers = {
            key: value / 100 for key, value in self.field(region, "corruption_percent").items()
        }
        return self.cap(self.floor_zero(multiply({(): base}, add({(): 1}, modifiers))), 1)

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
        aliases = self._metric_aliases(metric)
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
        faction_metric = metric.startswith(("research_", "agent_cap:"))
        region_metric = metric.startswith(("resource:", "religion:")) or metric == "roads"
        for source in self.sources:
            for effect, rule, reach_, value in self.effects(source):
                if rule.kind != "metric" or not aliases.intersection(rule.categories):
                    continue
                recipients = [r for r in regions if self.applies(source, r, reach_, effect)]
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

    def _metric_aliases(self, metric):
        aliases = {metric}
        if self.state_religion:
            if metric == "religion:state":
                aliases.add("religion:" + self.state_religion)
            if metric == "religion:" + self.state_religion:
                aliases.add("religion:state")
        return aliases

    def export_income(self):
        from games.tw.attila.traits import rules

        tariffs = {}
        for source in self.sources:
            for _, rule, scope, value in self.effects(source):
                if rule.kind == "tariff_percent" and scope == Reach.FACTION:
                    tariffs = add(tariffs, {self.decision(source): rational(value) / 100})
        total = multiply({(): self.scenario.data.get("base_tariffs", 0)}, add({(): 1}, tariffs))
        for resource, price in self.scenario.data.get("resource_prices", {}).items():
            quantity = self.floor_zero(self.metric(f"resource:{resource}"))
            if resource in self.scenario.data.get("resource_demand", {}):
                quantity = self.cap(quantity, self.scenario.data["resource_demand"][resource])
            total = add(total, multiply(quantity, {(): price}))
        bonus = sum(rule[1] for rule in rules(self.traits, "trade_income_percent"))
        return multiply(total, {(): 1 + rational(bonus) / 100})

    def other_income(self):
        from games.tw.attila.traits import rules

        tribute_bonus = sum(rule[1] for rule in rules(self.traits, "tribute_percent"))
        tribute = rational(self.campaign.get("base_tribute", 0)) * (
            1 + rational(tribute_bonus) / 100
        )
        subsidy = (
            500
            if rules(self.traits, "peace_subsidy")
            and self.campaign.get("at_peace_with_sassanids", False)
            else 0
        )
        return {(): tribute + subsidy}

    def project_cost(self):
        from games.tw.attila.traits import rules

        total = {}
        region_by_id = {r.name: r for r in self.regions}
        for project in self.scenario.data.get("projects", []):
            region = region_by_id[project["region"]]
            modifiers = self.field(
                region,
                "conversion_cost_percent" if project.get("conversion") else "construction_percent",
            )
            if project.get("sanitation") and not project.get("conversion"):
                modifiers = add(modifiers, self.field(region, "sanitation_cost_percent"))
            if project.get("main_settlement"):
                modifiers = add(
                    modifiers,
                    {
                        (): sum(
                            rule[1]
                            for rule in rules(
                                self.traits,
                                "main_conversion"
                                if project.get("conversion")
                                else "main_construction",
                            )
                        )
                    },
                )
            if not project.get("conversion"):
                category = "main" if project.get("main_settlement") else project.get("category")
                if category:
                    modifiers = add(modifiers, self.field(region, "project_cost_percent", category))
                    if category in ("industry", "agriculture"):
                        modifiers = add(
                            modifiers,
                            self.field(region, "project_cost_percent", "industry_agriculture"),
                        )
            factor = self.floor_zero(add({(): 1}, {k: v / 100 for k, v in modifiers.items()}))
            total = add(total, multiply({(): project["base_cost"]}, factor))
        return total

    def tax_factor(self, region):
        tax = {key: value / 100 for key, value in self.field(region, "tax_percent").items()}
        baseline = (
            rational(self.scenario.province(self.owner[region.name], "tax_percent", 100)) / 100
        )
        return self.floor_zero(add({(): baseline}, tax))

    def taxable_income(self, region):
        return multiply(self.wealth(region), self.tax_factor(region))

    def tax_income(self, region):
        return multiply(
            self.taxable_income(region),
            add({(): 1}, {k: -v for k, v in self.corruption(region).items()}),
        )

    def upkeep(self, region=None):
        total = {}
        for b in self.buildings:
            if region is not None and b.region is not region:
                continue
            if b.metadata is None:
                raise ValueError(f"Missing imported upkeep metadata for {b.name}")
            total = add(total, {(b.get_name(),): b.metadata["metadata"]["upkeep"]})
        return total

    def objective(self, mode="income"):
        if mode not in {"wealth", "income"}:
            raise ValueError("Unknown economy objective")
        total = {}
        for region in self.regions:
            total = add(
                total,
                self.tax_income(region) if mode == "income" else self.wealth(region),
            )
        if mode == "income":
            total = add(total, {k: -v for k, v in self.upkeep().items()})
            total = add(total, self.export_income())
            total = add(total, self.other_income())
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
                [*expression, float(lower) * variable],
                constraint_fn=lambda x: x >= float(lower),
            )
            solver.create_constraint(
                name + "_upper",
                [*expression, -float(upper + step) * variable],
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
                self.compile(add(food, {(): self.scenario.province(province, "food")}), solver),
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
            terms = self.metric(target["metric"], target["scope"], target.get("target", "faction"))
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
                    sum(v for k, v in expression.items() if all(enabled(n) for n in k)) >= 0
                )
            return cache[name]

        return float(
            sum(value for monomial, value in terms.items() if all(enabled(key) for key in monomial))
        )

    def evaluate_layout(self, selected, mode="income"):
        from games.tw.attila.effects import METRICS

        financials = {}
        for r in self.regions:
            wealth = self.evaluate(self.wealth(r), selected)
            taxable = self.evaluate(self.taxable_income(r), selected)
            tax = self.evaluate(self.tax_income(r), selected)
            upkeep = self.evaluate(self.upkeep(r), selected)
            financials[r.name] = {
                "wealth": wealth,
                "tax_multiplier": self.evaluate(self.tax_factor(r), selected),
                "tax_bonus_income": taxable - wealth,
                "corruption_loss": taxable - tax,
                "tax_income": tax,
                "building_upkeep": upkeep,
                "net_income": tax - upkeep,
            }
        exports = self.evaluate(self.export_income(), selected)
        totals = {
            key: sum(row[key] for row in financials.values())
            for key in (
                "wealth",
                "tax_bonus_income",
                "corruption_loss",
                "tax_income",
                "building_upkeep",
                "net_income",
            )
        }
        totals["trade_income"] = exports
        totals["other_recurring_income"] = self.evaluate(self.other_income(), selected)
        totals["net_income"] += exports + totals["other_recurring_income"]
        return {
            "finances": {"total": totals, "regions": financials},
            "faction_traits": self.traits,
            "catalogue_exclusions": getattr(self, "catalogue_exclusions", []),
            "imported_modifiers": self.modifiers,
            "assumptions": {
                "treasury_interest": "excluded_by_requested_objective",
                "province_capitals_held": self.capitals_held,
                "base_tax_percent_default": 100,
                "base_corruption_percent_default": 0,
                "unsupplied_trade_tribute_and_immigration_baselines": 0,
                "campaign": self.campaign,
                "technology_economic_bonuses": (
                    "imported; see imported_modifiers for active facts and omissions"
                ),
                "religion_economic_bonuses": (
                    "imported; conditional religious public order requires scenario input"
                ),
            },
            "state_religion": self.state_religion,
            "metric_semantics": (
                "Scoped effect totals and capabilities; not a forecast of conversion "
                "or research completion"
            ),
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
            "objective_kind": "weighted_" + mode if self.scenario.data.get("weights") else mode,
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
                r.name: 100 * self.evaluate(self.corruption(r), selected) for r in self.regions
            },
            "province_food": {
                p.name: sum(self.evaluate(self.food(r), selected) for r in p.regions)
                + self.scenario.province(p, "food")
                for p in self.provinces
            },
            "public_order": {
                p.name: self.evaluate(self.public_order(p), selected) for p in self.provinces
            },
        }
