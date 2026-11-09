"""Compile ownership, resource eligibility and scoped economy into an exact MILP."""

from collections import defaultdict

from ortools.linear_solver import linear_solver_pb2, pywraplp

from games.tw.three_kingdoms.integer import Arithmetic, Quantity
from games.tw.three_kingdoms.optimization import SCALE
from games.tw.three_kingdoms.scopes import ECONOMIC, targets


class Compiler:
    def __init__(self, economy):
        self.economy = economy
        self.solver = pywraplp.Solver.CreateSolver("SAT")
        self.arithmetic = Arithmetic(self.solver)
        self.choices = {}
        self.terms = defaultdict(list)
        self.fixed = defaultdict(int)

    def compile(self):
        self._choices()
        self._resources()
        self._requirements()
        self._effect_terms()
        food, income = [], []
        for province in self.economy.scenario.commanderies:
            self._province_constraints(province)
            retention = self._retention(province)
            for county, region in self.economy.regions.items():
                if region["commandery"] == province.id:
                    food.append(self._county_food(county).expression)
                    wealth = self._county_wealth(county)
                    income.append(
                        self.arithmetic.product(wealth, retention, "net_income").expression
                    )
        self.solver.Add(sum(food) + self.economy.scenario.external_food * 100 >= 0)
        upkeep = sum(
            self.economy.candidates[county][key]["upkeep"] * variable
            for (county, key), variable in self.choices.items()
        )
        self.solver.Maximize(sum(income) - upkeep * SCALE)
        proto = linear_solver_pb2.MPModelProto()
        self.solver.ExportModelToProto(proto)
        self.economy.decisions = {v.name(): pair for pair, v in self.choices.items()}
        return proto

    def _choices(self):
        self.choices = {
            (county, key): self.solver.BoolVar(county + ":" + key)
            for county, buildings in self.economy.candidates.items()
            for key in buildings
        }
        unique = defaultdict(list)
        for county, buildings in self.economy.candidates.items():
            roles, groups = defaultdict(list), defaultdict(list)
            for key, building in buildings.items():
                variable = self.choices[(county, key)]
                roles[self.economy.role(county, building)].append(variable)
                groups[building["superchain"]].append(variable)
                if building["faction_unique"]:
                    unique[key].append(variable)
            self.solver.Add(sum(roles["primary"]) == 1)
            if roles["port"]:
                self.solver.Add(sum(roles["port"]) == 1)
            for variables in groups.values():
                self.solver.Add(sum(variables) <= 1)
            self._city_constraints(county, roles)
        for variables in unique.values():
            self.solver.Add(sum(variables) <= 1)

    def _city_constraints(self, county, roles):
        province = self.economy.provinces[self.economy.regions[county]["commandery"]]
        city_rules = self.economy.data["rules"]["city_levels"]
        if province.city_level is not None:
            slots = city_rules[str(province.city_level)]["slots"]
        else:
            capital = self.economy.data["commanderies"][province.id]["capital"]
            city_choices = [
                (building["level"], self.choices[(capital, key)])
                for key, building in self.economy.candidates[capital].items()
                if building["kind"] == "city"
            ]
            slots = sum(city_rules[str(level)]["slots"] * choice for level, choice in city_choices)
            for key, building in self.economy.candidates[county].items():
                if building["kind"] != "city" and building["minimum_city_level"]:
                    required = sum(
                        choice
                        for level, choice in city_choices
                        if level >= building["minimum_city_level"]
                    )
                    self.solver.Add(self.choices[(county, key)] <= required)
        self.solver.Add(sum(roles["district"] + roles["port"]) <= slots)

    def _resources(self):
        providers = defaultdict(list)
        for pair, variable in self.choices.items():
            building = self.economy.candidates[pair[0]][pair[1]]
            for resource in building["provided_resources"]:
                providers[resource].append(variable)
        external = set(self.economy.scenario.external_resources)
        for pair, variable in self.choices.items():
            required = self.economy.candidates[pair[0]][pair[1]]["required_resources"]
            resources = set(required["resources"])
            if required["operator"] == "OR":
                if resources and not resources & external:
                    self.solver.Add(variable <= sum(v for r in resources for v in providers[r]))
            else:
                for resource in resources - external:
                    self.solver.Add(variable <= sum(providers[resource]))

    def _requirements(self):
        for key in self.economy.scenario.required_buildings:
            self.solver.Add(sum(v for (_, b), v in self.choices.items() if b == key) >= 1)
        for key in self.economy.scenario.forbidden_buildings:
            self.solver.Add(sum(v for (_, b), v in self.choices.items() if b == key) == 0)

    def _add_effect(self, effect, county, variable=None):
        if effect["metric"] not in ECONOMIC:
            return
        destinations = targets(
            effect,
            county,
            self.economy.regions,
            self.economy.provinces,
            self.economy.scenario.adjacency or (),
        )
        for destination in destinations:
            key = (effect["metric"], destination, effect["category"])
            if variable is None:
                self.fixed[key] += effect["value"]
            else:
                self.terms[key].append((effect["value"], Quantity(variable, 0, 1)))

    def _effect_terms(self):
        for pair, variable in self.choices.items():
            for effect in self.economy.effects[pair]:
                self._add_effect(effect, pair[0], variable)
        source = next(iter(self.economy.regions))
        for effect in self.economy.fixed_effects():
            self._add_effect(effect, source)
        for province in self.economy.scenario.commanderies:
            population = self.economy.population_effects(province)
            self.fixed[("order", province.id, "")] += (
                population["public_order"] + province.order_offset
            )
            for county, region in self.economy.regions.items():
                if region["commandery"] == province.id:
                    self.fixed[("wealth_percent", county, "peasantry")] += population[
                        "peasantry_percent"
                    ]

    def quantity(self, metric, place, category="", offset=0):
        key = (metric, place, category)
        return self.arithmetic.sum(self.terms[key], offset + self.fixed[key])

    def _province_constraints(self, province):
        self.solver.Add(self.quantity("order", province.id).expression >= province.minimum_order)
        capacity = sum(
            effect["value"] * self.choices[pair]
            for pair, effects in self.economy.effects.items()
            if self.economy.regions[pair[0]]["commandery"] == province.id
            for effect in effects
            if effect["metric"] == "population_capacity"
        )
        self.solver.Add(
            capacity * self.economy.data["rules"]["population_unit"] >= province.population
        )

    def _retention(self, province):
        if not province.corruption_percent:
            return Quantity.constant(10_000)
        modifier = self.arithmetic.maximum_zero(
            self.quantity("corruption_percent", province.id, offset=100), "corruption_rate"
        )
        return self.arithmetic.maximum_zero(
            self.arithmetic.sum([(-province.corruption_percent, modifier)], 10_000), "retention"
        )

    def _categories(self, metric, county):
        return sorted(
            {
                category
                for kind, place, category in self.terms.keys() | self.fixed.keys()
                if kind == metric and place == county
            }
        )

    def _county_wealth(self, county):
        products = []
        for category in self._categories("wealth", county):
            base = self.quantity("wealth", county, category)
            rate = self.quantity("wealth_percent", county, category, offset=100)
            self.solver.Add(rate.expression >= 0)
            products.append((1, self.arithmetic.product(base, rate, "wealth")))
        return self.arithmetic.sum(products)

    def _county_food(self, county):
        products = []
        for category in self._categories("food", county):
            base = self.quantity("food", county, category)
            rate = self.quantity("food_percent", county, category, offset=100)
            self.solver.Add(rate.expression >= 0)
            products.append((1, self.arithmetic.product(base, rate, "food")))
        return self.arithmetic.sum(products)
