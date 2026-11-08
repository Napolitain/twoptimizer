"""Scoped static province economy, compiled exactly with binary products.

Wealth modifiers stack additively within each category. The default income
objective applies tax/corruption and subtracts upkeep. Campaign quantities which
cannot be inferred from the catalog are explicit scenario inputs.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import chain
from math import isfinite, lcm
from types import SimpleNamespace

from games.tw.attila.algebra import Indicator, Polynomial, add, multiply, rational, sum_polynomials
from games.tw.attila.compiler import PolynomialCompiler
from games.tw.attila.effect_index import EffectIndex
from games.tw.attila.effects import Reach, entries
from games.tw.attila.records import LayoutReport
from games.tw.context import GameContext


class Economy:
    def __init__(
        self,
        provinces,
        adjacency=None,
        scenario=None,
        technology_profile=None,
        *,
        context: GameContext | None = None,
    ):
        self.context = context if context is not None else provinces[0].context
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
        self.adjacency = adjacency if adjacency is not None else self.scenario.adjacency
        # Validate API-supplied adjacency too; never silently ignore absent neighbors.
        Scenario({"adjacency": self.adjacency}).bind(provinces)
        self.sources = list(self.buildings)
        region_by_id = {r.name: r for r in self.regions}
        for i, record in enumerate(self.scenario.external_effects):
            source = SimpleNamespace(
                name=f"@external_{i}",
                region=region_by_id[record.region],
                raw_effects={(record.effect, record.scope): record.amount},
            )
            self.sources.append(source)
        self.logic: dict[str, Indicator] = {}
        self._logic_variables = {}
        self._serial = 0
        self.products = {}
        self.compiler = PolynomialCompiler(self)
        self._fields = {}
        self._wealth = {}
        self._metrics = {}
        state = getattr(getattr(self.context.instance, "religion", None), "value", None)
        self.state_religion = {"eastern": "church_east", "tengris": "tengri"}.get(state, state)
        if self.state_religion == "any":
            self.state_religion = None
        self.base_fertility = {
            r.name: self.context.fertility if r.fertility is None else r.fertility
            for r in self.regions
        }
        if any(not isfinite(value) or value < 0 for value in self.base_fertility.values()):
            raise ValueError("Fertility must be finite and nonnegative")
        from games.tw.attila.traits import profile, rules
        from games.tw.models.model import RegionType

        faction = getattr(getattr(self.context.instance, "faction", None), "value", None)
        self.traits = profile(faction, self.scenario.faction_traits)
        self.farms_without_penalties = bool(rules(self.traits, "farms_without_penalties"))
        self.campaign = self.scenario.campaign
        selected_capitals = sum(r.region_type == RegionType.REGION_MAJOR for r in self.regions)
        self.capitals_held = (
            self.campaign.province_capitals_held
            if self.campaign.province_capitals_held is not None
            else selected_capitals
        )
        if self.capitals_held < selected_capitals:
            raise ValueError("province_capitals_held cannot be below the selected owned capitals")
        self._add_trait_sources()
        from games.tw.attila.modifiers import modifier_profile

        self.modifiers, semantic_effects = modifier_profile(
            self.context.instance, technology_profile, self.scenario.to_dict()
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
        self.effect_index = EffectIndex(self)

    def _record_omitted_effects(self):
        self.omitted = []
        for b in self.sources:
            for key, rule, scope, _ in self.effects(b):
                if (
                    rule.kind == "conditional_fertility_food"
                    and key not in self.scenario.conditional_targets
                ):
                    self.omitted.append((b.name, key, "requires_explicit_recipients"))
                elif rule.kind == "unmodeled" or scope == Reach.OTHER:
                    self.omitted.append((b.name, key, scope.value))
                elif scope == Reach.ADJACENT and not self.adjacency:
                    self.omitted.append((b.name, key, "adjacency_not_supplied"))
                elif scope == Reach.CONDITIONAL and key not in self.scenario.conditional_targets:
                    self.omitted.append((b.name, key, "requires_food_sharing_condition"))
                elif (
                    rule.kind.startswith("immigration_")
                    and not self.scenario.provinces
                    and not self.scenario.regions
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
            if rule and rule[0] in required and required[rule[0]] not in self.campaign.provided:
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
        mapping = self.scenario.conditional_targets.get(effect)
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
        for record in self.effect_index.by_region[region.name, kind]:
            if (category is None or category in record.rule.categories) and (
                recipient is None or record.scope != Reach.BUILDING or record.source is recipient
            ):
                result[self.decision(record.source)] += rational(record.value)
        self._fields[cache_key] = dict(result)
        return self._fields[cache_key]

    def fertility(self, region):
        return add({(): self.base_fertility[region.name]}, self.field(region, "fertility"))

    def wealth(self, region):
        if region.name in self._wealth:
            return self._wealth[region.name]
        total = {}
        for record in self.effect_index.wealth[region.name]:
            producer, rule, value = record.source, record.rule, record.value
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
                external = self.scenario.for_region(region).wealth_percent
                modifier = add(
                    modifier,
                    {(): rational(external.get("all", 0) + external.get(category, 0)) / 100},
                )
                total = add(total, multiply(base, add({(): 1}, modifier)))
        immigration = self.scenario.for_region(region).immigration_wealth
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
        if (
            rules(self.traits, "poor_fertility_food")
            and region.name in self.campaign.poor_fertility_regions
        ):
            trait_food += 15
        if rules(self.traits, "trade_food"):
            # This is a provincial total, credited once to its first region.
            province = next(p for p in self.provinces if p.name == self.owner[region.name])
            if region is province.regions[0]:
                trait_food += min(150, 30 * self.campaign.active_trade_routes)
        consumption = {key: -value for key, value in self.field(region, "food_consumption").items()}
        return add(
            add(
                add(self.field(region, "food"), consumption),
                {(): rational(self.scenario.for_region(region).food) + trait_food},
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
        for record in self.effect_index.by_province[province.name, kind]:
            result = add(result, {self.decision(record.source): record.value})
        return result

    def public_order(self, province):
        result = add(
            self.province_field(province, "public_order"),
            {(): self.scenario.for_province(province).public_order},
        )
        base = self.scenario.for_province(province).immigration_order
        if base:
            modifier = {
                key: value / 100
                for key, value in self.province_field(province, "immigration_order_percent").items()
            }
            result = add(result, multiply({(): base}, self.floor_zero(add({(): 1}, modifier))))
        religious = self.scenario.for_province(province).religious_order
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
                {(): self.scenario.for_region(region).sanitation},
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
            if info.identity == identity:
                return {(name,): 1}
        name = f"__gate_{self._serial}"
        self._serial += 1
        step = Fraction(1, lcm(*(rational(v).denominator for v in terms.values())))
        self.logic[name] = Indicator(identity, terms, lower, upper, step)
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
            rational(self.scenario.for_province(self.owner[region.name]).corruption_percent) / 100
        )
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
        for record in self.effect_index.by_kind["metric"]:
            if not aliases.intersection(record.rule.categories):
                continue
            recipients = [
                r for r in regions if self.applies(record.source, r, record.scope, record.effect)
            ]
            count = (
                bool(recipients)
                if faction_metric
                else len(recipients)
                if region_metric
                else len({self.owner[r.name] for r in recipients})
            )
            if count:
                result = add(result, {self.decision(record.source): record.value * count})
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
        for record in self.effect_index.by_kind["tariff_percent"]:
            if record.scope == Reach.FACTION:
                tariffs = add(tariffs, {self.decision(record.source): rational(record.value) / 100})
        total = multiply({(): self.scenario.base_tariffs}, add({(): 1}, tariffs))
        for resource, price in self.scenario.resource_prices.items():
            quantity = self.floor_zero(self.metric(f"resource:{resource}"))
            if resource in self.scenario.resource_demand:
                quantity = self.cap(quantity, self.scenario.resource_demand[resource])
            total = add(total, multiply(quantity, {(): price}))
        bonus = sum(rule[1] for rule in rules(self.traits, "trade_income_percent"))
        return multiply(total, {(): 1 + rational(bonus) / 100})

    def other_income(self):
        from games.tw.attila.traits import rules

        tribute_bonus = sum(rule[1] for rule in rules(self.traits, "tribute_percent"))
        tribute = rational(self.campaign.base_tribute) * (1 + rational(tribute_bonus) / 100)
        subsidy = (
            500
            if rules(self.traits, "peace_subsidy") and self.campaign.at_peace_with_sassanids
            else 0
        )
        return {(): tribute + subsidy}

    def project_cost(self):
        from games.tw.attila.traits import rules

        total = {}
        region_by_id = {r.name: r for r in self.regions}
        for project in self.scenario.projects:
            region = region_by_id[project.region]
            modifiers = self.field(
                region,
                "conversion_cost_percent" if project.conversion else "construction_percent",
            )
            if project.sanitation and not project.conversion:
                modifiers = add(modifiers, self.field(region, "sanitation_cost_percent"))
            if project.main_settlement:
                modifiers = add(
                    modifiers,
                    {
                        (): sum(
                            rule[1]
                            for rule in rules(
                                self.traits,
                                "main_conversion" if project.conversion else "main_construction",
                            )
                        )
                    },
                )
            if not project.conversion:
                category = "main" if project.main_settlement else project.category
                if category:
                    modifiers = add(modifiers, self.field(region, "project_cost_percent", category))
                    if category in ("industry", "agriculture"):
                        modifiers = add(
                            modifiers,
                            self.field(region, "project_cost_percent", "industry_agriculture"),
                        )
            factor = self.floor_zero(add({(): 1}, {k: v / 100 for k, v in modifiers.items()}))
            total = add(total, multiply({(): project.base_cost}, factor))
        return total

    def tax_factor(self, region):
        tax = {key: value / 100 for key, value in self.field(region, "tax_percent").items()}
        baseline = rational(self.scenario.for_province(self.owner[region.name]).tax_percent) / 100
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
            amount = rational(b.metadata["metadata"]["upkeep"])
            if amount:
                total[(b.get_name(),)] = amount
        return total

    def objective(self, mode="income"):
        if mode not in {"wealth", "income"}:
            raise ValueError("Unknown economy objective")
        regional = (
            self.tax_income(region) if mode == "income" else self.wealth(region)
            for region in self.regions
        )
        extra = self._income_extras() if mode == "income" else self._objective_weights()
        return sum_polynomials(chain(regional, extra))

    def non_tax_income(self):
        """Exact objective remainder without expanding and subtracting all regional taxes."""
        return sum_polynomials(self._income_extras())

    def _income_extras(self):
        yield {k: -v for k, v in self.upkeep().items()}
        yield self.export_income()
        yield self.other_income()
        yield from self._objective_weights()

    def _objective_weights(self):
        for weight in self.scenario.weights:
            yield multiply(
                self.metric(
                    weight.metric,
                    weight.scope,
                    weight.recipient,
                ),
                {(): weight.value},
            )

    def compile(self, terms, solver):
        return self.compiler.compile(terms, solver)

    def install_constraints(self, solver):
        self.compiler.install_constraints(solver)

    def evaluate(self, terms: Polynomial, selected) -> float:
        cache = {}

        def enabled(name):
            if name not in self.logic:
                return name in selected
            if name not in cache:
                expression = self.logic[name].expression
                cache[name] = (
                    sum(v for k, v in expression.items() if all(enabled(n) for n in k)) >= 0
                )
            return cache[name]

        return float(
            sum(value for monomial, value in terms.items() if all(enabled(key) for key in monomial))
        )

    def evaluate_layout(self, selected, mode="income") -> LayoutReport:
        from games.tw.attila.reporting import evaluate_layout

        return evaluate_layout(self, selected, mode)
