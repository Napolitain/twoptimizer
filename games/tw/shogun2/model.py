"""Static Shogun 2 domestic tax income, with shared food and local slots.

All coefficients come from the public catalog/rules or explicit scenario inputs.
Growth is disclosed, not silently converted to current income or future wealth.
"""

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path

from ortools.linear_solver import pywraplp

from games.tw.competition import BinaryModel, solve
from games.tw.shogun2.effects import (
    family,
    level,
    parse,
    unavailable_reason,
    unique_key,
    values,
)

ROOT = Path(__file__).parents[1]
CATALOG_PATH = ROOT / "multigame/data/shogun2.json"
RULES_PATH = Path(__file__).parent / "data/rules.json"
TOWN = {"crafts", "stealth", "buddhist", "christian", "ikko"}
DEDICATED = {"castle", "farming", "infrastructure", "port", "specialty"}


def fraction(value):
    return Fraction(str(value))


def load_data():
    return json.loads(CATALOG_PATH.read_text()), json.loads(RULES_PATH.read_text())


@dataclass(frozen=True)
class Province:
    id: str
    town_wealth: float = 0
    base_tax_percent: float = 30
    administration: float = 1
    order_offset: float = -4  # Normal-tax unrest; other unrest must be supplied.
    minimum_order: float = 0
    farm_multiplier: float | None = None  # None uses the source's native soil.


@dataclass(frozen=True)
class Scenario:
    clan: str
    provinces: tuple[Province, ...]
    all_arts: bool = True
    religion: str | None = None
    nanban_contact: bool = False


class Economy:
    def __init__(self, scenario, catalog=None, rules=None):
        loaded = load_data() if catalog is None or rules is None else (catalog, rules)
        self.catalog, self.rules = loaded
        self.scenario = scenario
        if scenario.clan not in self.catalog["factions"]:
            raise ValueError("Unknown clan")
        self.religion = scenario.religion or self.rules["clan_religion"][scenario.clan]
        if self.religion not in {"christian", "buddhist", "ikko"}:
            raise ValueError("Unknown religion")
        if (scenario.clan == "ikko_ikki") != (self.religion == "ikko"):
            raise ValueError("Ikko religion requires the Ikko Ikki clan and vice versa")
        if not scenario.provinces or len({p.id for p in scenario.provinces}) != len(
            scenario.provinces
        ):
            raise ValueError("Choose at least one province, without duplicates")
        self.provinces = {}
        for province in scenario.provinces:
            location = dict(self.rules["provinces"][province.id])
            for amount in asdict(province).values():
                if amount is not None and not isinstance(amount, str):
                    fraction(amount)  # Reject NaN/inf as well as non-numbers.
            if (
                province.town_wealth < 0
                or not 0 <= province.base_tax_percent <= 100
                or not 0 <= province.administration <= 1
            ):
                raise ValueError(
                    "Invalid wealth, tax rate or administration multiplier"
                )
            if province.farm_multiplier is not None:
                if (
                    province.farm_multiplier
                    not in self.rules["fertility_multipliers"].values()
                ):
                    raise ValueError(
                        "Farm multiplier must be a sourced fertility multiplier"
                    )
                location["farm_multiplier"] = province.farm_multiplier
            self.provinces[province.id] = (province, location)
        self.arts = Counter()
        if scenario.all_arts:
            for art in self.catalog["technologies"].values():
                for text in art["facts"] + art.get("clan_facts", []):
                    if effect := parse(text):
                        self.arts[effect.kind] += effect.value
        self.farm_percent = self.arts["farm_percent"] + self.rules[
            "clan_farm_percent"
        ].get(scenario.clan, 0)
        self.candidates = {}

        def arts_available(building, seen=frozenset()):
            if scenario.all_arts:
                return True
            if building["id"] in seen:
                raise ValueError("Cyclic construction prerequisite")
            for url in building.get("requires", []):
                key = url.rsplit("/", 1)[-1].removesuffix(".html")
                if key in self.catalog["technologies"]:
                    return False
                if key in self.catalog["buildings"] and not arts_available(
                    self.catalog["buildings"][key], seen | {building["id"]}
                ):
                    return False
            return True

        for province_id, (_, location) in self.provinces.items():
            self.candidates[province_id] = {
                key: building
                for key, building in self.catalog["buildings"].items()
                if family(building) in TOWN | DEDICATED
                and arts_available(building)
                and unavailable_reason(
                    building,
                    location,
                    self.religion,
                    nanban_contact=scenario.nanban_contact,
                    clan=scenario.clan,
                )
                is None
            }

    def wealth(self, province_id, building):
        location = self.provinces[province_id][1]
        return (
            fraction(values(building, "wealth", "farms"))
            * fraction(location["farm_multiplier"])
            * (1 + fraction(self.farm_percent) / 100)
            + values(building, "wealth", "commerce")
            + values(building, "wealth", "mines")
        )

    def compile(self):
        solver = pywraplp.Solver.CreateSolver("CBC")
        variables = {}
        unique = defaultdict(list)
        objective = defaultdict(Fraction)
        products = {}

        def product(left, right):
            if left.name() == right.name():
                return left
            pair = tuple(sorted((left.name(), right.name())))
            if pair not in products:
                aux = solver.BoolVar("product:" + "&".join(pair))
                solver.Add(aux <= left)
                solver.Add(aux <= right)
                solver.Add(aux >= left + right - 1)
                products[pair] = aux
            return products[pair]

        food = []
        offset = Fraction(0)
        for province_id, buildings in self.candidates.items():
            province = self.provinces[province_id][0]
            groups = defaultdict(list)
            for key, building in buildings.items():
                variable = solver.BoolVar(province_id + ":" + key)
                variables[(province_id, key)] = variable
                groups[family(building)].append(variable)
                food.append(values(building, "food") * variable)
                if unique_id := unique_key(building):
                    unique[unique_id].append(variable)
            for group, choices in groups.items():
                if group in DEDICATED:
                    solver.Add(sum(choices) == 1)
                else:
                    solver.Add(sum(choices) <= 1)
            slots = sum(
                level(buildings[key]) * variables[(province_id, key)]
                for key in buildings
                if family(buildings[key]) == "castle"
            )
            town = sum(
                variables[(province_id, key)]
                for key in buildings
                if family(buildings[key]) in TOWN
            )
            solver.Add(town <= slots)
            order = sum(
                (values(b, "order") + values(b, "religious_order"))
                * variables[(province_id, key)]
                for key, b in buildings.items()
            )
            solver.Add(
                order + self.arts["order"] + province.order_offset
                >= province.minimum_order
            )
            base_wealth = fraction(province.town_wealth)
            base_tax = (
                fraction(province.base_tax_percent) + self.arts["tax_percent"]
            ) / 100
            administration = fraction(province.administration)
            offset += base_wealth * base_tax * administration
            wealth = [
                (key, self.wealth(province_id, b)) for key, b in buildings.items()
            ]
            taxes = [
                (key, fraction(values(b, "tax_percent")) / 100)
                for key, b in buildings.items()
                if values(b, "tax_percent")
            ]
            for key, amount in wealth:
                objective[variables[(province_id, key)].name()] += (
                    amount * base_tax * administration
                )
            for key, rate in taxes:
                tax_variable = variables[(province_id, key)]
                objective[tax_variable.name()] += base_wealth * rate * administration
                for wealth_key, amount in wealth:
                    if not amount:
                        continue
                    if key != wealth_key and family(buildings[key]) == family(
                        buildings[wealth_key]
                    ):
                        continue  # Mutually exclusive stages of the same chain.
                    term = product(tax_variable, variables[(province_id, wealth_key)])
                    objective[term.name()] += rate * amount * administration
        solver.Add(sum(food) + self.arts["food"] >= 0)
        for choices in unique.values():
            solver.Add(sum(choices) <= 1)
        lookup = {v.name(): v for v in solver.variables()}
        target = solver.Objective()
        target.SetMaximization()
        target.SetOffset(float(offset))
        for name, amount in objective.items():
            target.SetCoefficient(lookup[name], float(amount))
        self.binary = BinaryModel.from_solver(solver)
        self.decision_names = {v.name(): pair for pair, v in variables.items()}
        return self.binary

    def evaluate(self, layout):
        """Recompute original economics and constraints without product variables."""
        if set(layout) != set(self.provinces):
            raise ValueError("Layout province coverage differs")
        total_food = self.arts["food"]  # A faction effect, counted once.
        total_income = Fraction(0)
        unique = Counter()
        report = {}
        for province_id, keys in layout.items():
            if len(keys) != len(set(keys)):
                raise ValueError("Duplicate building")
            if set(keys) - self.candidates[province_id].keys():
                raise ValueError("Unavailable building")
            buildings = [self.candidates[province_id][key] for key in keys]
            groups = Counter(family(b) for b in buildings)
            available_groups = {
                family(b) for b in self.candidates[province_id].values()
            }
            if any(groups[g] != 1 for g in DEDICATED & available_groups) or any(
                n > 1 for n in groups.values()
            ):
                raise ValueError("Invalid chain occupancy")
            castle = next(b for b in buildings if family(b) == "castle")
            slots = level(castle)
            if sum(groups[g] for g in TOWN) > slots:
                raise ValueError("Castle has too few town slots")
            for building in buildings:
                if key := unique_key(building):
                    unique[key] += 1
            province, location = self.provinces[province_id]
            order = (
                fraction(province.order_offset)
                + self.arts["order"]
                + sum(
                    values(b, "order") + values(b, "religious_order") for b in buildings
                )
            )
            if order < fraction(province.minimum_order):
                raise ValueError("Insufficient public order")
            food = sum(values(b, "food") for b in buildings)
            total_food += food
            farm_wealth = sum(
                fraction(values(b, "wealth", "farms"))
                * fraction(location["farm_multiplier"])
                * (1 + fraction(self.farm_percent) / 100)
                for b in buildings
            )
            commerce = sum(values(b, "wealth", "commerce") for b in buildings)
            mines = sum(values(b, "wealth", "mines") for b in buildings)
            wealth = fraction(province.town_wealth) + farm_wealth + commerce + mines
            tax = (
                fraction(province.base_tax_percent)
                + self.arts["tax_percent"]
                + sum(values(b, "tax_percent") for b in buildings)
            )
            income = wealth * tax / 100 * fraction(province.administration)
            total_income += income
            report[province_id] = {
                "name": location["name"],
                "farm_multiplier": location["farm_multiplier"],
                "buildings": sorted(keys),
                "town_slots": slots,
                "town_wealth": province.town_wealth,
                "farm_wealth": float(farm_wealth),
                "commerce_wealth": commerce,
                "mine_wealth": mines,
                "taxable_wealth": float(wealth),
                "effective_tax_percent": float(tax),
                "administration_multiplier": province.administration,
                "tax_income": float(income),
                "local_food_balance": food,
                "public_order": float(order),
                "growth_components": {
                    "buildings": sum(values(b, "building_growth") for b in buildings),
                    "building_growth_bonus_percent": sum(
                        values(b, "growth_percent") for b in buildings
                    ),
                    "arts": self.arts["arts_growth"],
                },
            }
        if total_food < 0:
            raise ValueError("Faction food deficit")
        if any(n > 1 for n in unique.values()):
            raise ValueError("Unique building duplicated across provinces")
        for province in report.values():
            province["growth_components"]["shared_food_surplus"] = (
                total_food * self.rules["shared_surplus_growth_per_province"]
            )
        return {
            "domestic_tax_income": float(total_income),
            "food_surplus": total_food,
            "faction_arts_food": self.arts["food"],
            "farm_bonus_percent": self.farm_percent,
            "arts_tax_points": self.arts["tax_percent"],
            "religion": self.religion,
            "provinces": report,
        }

    def optimize(self, algorithm="cp-sat", seconds=None, workers=None):
        result = solve(self.compile(), algorithm, seconds=seconds, workers=workers)
        report = {
            "scenario": asdict(self.scenario),
            "solver": {k: v for k, v in asdict(result).items() if k != "values"},
        }
        if result.values is not None:
            layout = {p: [] for p in self.provinces}
            for name, value in zip(self.binary.names, result.values):
                if value > 0.5 and name in self.decision_names:
                    province, key = self.decision_names[name]
                    layout[province].append(key)
            economics = self.evaluate(layout)
            if abs(economics["domestic_tax_income"] - result.objective) > 1e-5:
                raise AssertionError("Independent tax evaluation disagrees with solver")
            report.update(economics)
        return report
