"""Exact integer linearization of provincial wealth, tax and shared food."""

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from time import perf_counter

from ortools.linear_solver import linear_solver_pb2, pywraplp
from ortools.sat.python import cp_model

from games.tw.rome2.effects import CATEGORIES, Effect, fact_effect, raw_effect

CATALOG = Path(__file__).parent / "data/economy_catalog.json"
LOCAL_SCOPES = {
    "this_building",
    "this_region",
    "this_province",
    "regions_in_this_province",
}
GLOBAL_SCOPES = {"this_faction", "in_all_your_regions", "in_all_your_provinces"}


def variable_name(variable):
    return variable.name() if callable(variable.name) else variable.name


class NativeCP:
    def __init__(self):
        self.model = cp_model.CpModel()
        self.variables = []

    def BoolVar(self, name):
        variable = self.model.new_bool_var(name)
        self.variables.append(variable)
        return variable

    def IntVar(self, lower, upper, name):
        variable = self.model.new_int_var(lower, upper, name)
        self.variables.append(variable)
        return variable

    def Add(self, expression):
        return self.model.add(expression)

    def Maximize(self, expression):
        self.model.maximize(expression)

    def multiply(self, result, left, right):
        self.model.add_multiplication_equality(result, [left, right])


class NativeSCIP:
    def __init__(self):
        from pyscipopt import Model

        self.model = Model("Rome II")
        self.model.hideOutput()
        self.variables = []

    def BoolVar(self, name):
        variable = self.model.addVar(name, vtype="B")
        self.variables.append(variable)
        return variable

    def IntVar(self, lower, upper, name):
        variable = self.model.addVar(name, vtype="I", lb=lower, ub=upper)
        self.variables.append(variable)
        return variable

    def Add(self, expression):
        if isinstance(expression, bool):
            if expression:
                return None
            from pyscipopt import quicksum

            expression = quicksum([]) >= 1
        return self.model.addCons(expression)

    def Maximize(self, expression):
        self.model.setObjective(expression, "maximize")

    def multiply(self, result, left, right):
        self.model.addCons(result == left * right)


def load_data():
    return json.loads(CATALOG.read_text())


@dataclass(frozen=True)
class Site:
    id: str
    major: bool = False
    port: bool = False
    resource: str | None = None
    slots: int | None = None  # Ordinary slots; excludes primary and port plots.

    @property
    def capacity(self):
        return self.slots if self.slots is not None else 4 if self.major else 2


@dataclass(frozen=True)
class Scenario:
    faction: str
    sites: tuple[Site, ...]
    name: str = "Controlled province"
    all_technologies: bool = False
    core_level: int = 4
    maximum_level: int = 4
    tax_points: int = 0  # Normal taxation = 100% of modified wealth.
    corruption_points: int = 0
    order_offset: int = 0
    minimum_order: int = 0
    external_food: int = 0
    party: int | None = None  # None chooses the best playable source profile.
    technology_profile: str = "public"
    modifiers: tuple[dict, ...] = ()
    world_profile: str | None = None


def branch(building):
    return re.sub(r"_\d+(?:_[a-z]+)?$", "", building["id"])


def placement(building, occurrence, site):
    if "allowed_regions" in occurrence and site.id not in occurrence["allowed_regions"]:
        return None
    category, title = occurrence["category"], occurrence["chain_title"]
    if category in {"Provincial Capital", "Minor Settlement"}:
        if site.major:
            return "primary" if category == "Provincial Capital" else None
        resource = re.sub(r"[^a-z]", "", (site.resource or "Minor Settlement").lower())
        resource = {"oliveoil": "olive"}.get(resource, resource)
        actual = re.sub(r"[^a-z]", "", title.lower())
        actual = {"oliveoil": "olive"}.get(actual, actual)
        return (
            "primary" if category == "Minor Settlement" and resource == actual else None
        )
    if category == "Port":
        return "port" if site.port else None
    if title == "City Centre" and not site.major:
        return None
    if title == "Town Centre" and site.major:
        return None
    barbarian = occurrence["culture"] == "rom_Barbarian"
    if (
        category in {"Sanitation", "Water", "Tax"} or title == "Tax"
    ) and not site.major:
        return None
    if not barbarian and category == "Agricultural" and site.major:
        return None
    if (
        not barbarian
        and category == "Industrial"
        and (title == "Minor Settlement") == site.major
    ):
        return None
    if category == "Military" and title == "Siege" and not site.major:
        return None
    return "ordinary"


class Economy:
    def __init__(self, scenario, data=None):
        self.data = load_data() if data is None else data
        self.scenario = scenario
        if scenario.faction not in self.data["factions"]:
            raise ValueError("Faction has no imported official eligibility tree")
        if (
            not scenario.sites
            or len({s.id for s in scenario.sites}) != len(scenario.sites)
            or sum(s.major for s in scenario.sites) != 1
        ):
            raise ValueError("A province needs distinct sites and exactly one capital")
        if not 1 <= scenario.core_level <= scenario.maximum_level <= 4:
            raise ValueError("Supported ordinary/core building levels are 1 through 4")
        for value in (
            scenario.tax_points,
            scenario.corruption_points,
            scenario.order_offset,
            scenario.minimum_order,
            scenario.external_food,
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise TypeError("Scenario modifiers must be integer points")
        if (
            not 0 <= scenario.corruption_points <= 100
            or 100 + scenario.tax_points - scenario.corruption_points < 0
        ):
            raise ValueError("Supply a nonnegative net tax factor")
        if any(
            not isinstance(s.capacity, int) or s.capacity < 0 for s in scenario.sites
        ):
            raise ValueError("Invalid ordinary slot capacity")
        self.faction = self.data["factions"][scenario.faction]
        self.fixed = []
        for modifier in scenario.modifiers:
            if (
                modifier["kind"]
                not in {
                    "wealth_percent",
                    "tax_percent",
                    "order",
                    "food_per_provinces",
                    "food_per_regions",
                    "corruption_percent",
                }
                or not isinstance(modifier["value"], int)
                or set(modifier.get("targets", ())) - set(CATEGORIES)
            ):
                raise ValueError("Unsupported explicit scenario modifier")
            self.fixed.append(
                Effect(
                    modifier["kind"],
                    modifier["value"],
                    tuple(modifier.get("targets", ())),
                )
            )
        for text in self.faction["traits"]["culture_facts"]:
            if effect := fact_effect(text):
                self.fixed.append(effect)
        if scenario.all_technologies:
            if scenario.technology_profile not in {"public", "archived"}:
                raise ValueError("Select public or archived technology profile")
            coverage = self.data.get("technology_coverage", {}).get(
                scenario.faction, {}
            )
            if (
                scenario.technology_profile == "public"
                and coverage.get("complete_public_tree") is False
            ):
                raise ValueError(
                    "Public research tree is incomplete; use the explicit no-technologies baseline or an available archival profile"
                )
            trees = (
                self.data["technologies"]
                if scenario.technology_profile == "public"
                else self.data.get("technologies_archived", {})
            )
            if scenario.faction not in trees:
                raise ValueError(
                    "Requested research profile is unavailable for this faction"
                )
            for technology in trees[scenario.faction].values():
                for text in technology["facts"]:
                    if effect := fact_effect(text):
                        self.fixed.append(effect)
        self.effective_corruption = max(
            0, scenario.corruption_points + self.fixed_value("corruption_percent")
        )
        self.parties = {
            i: p
            for i, p in enumerate(self.faction["traits"]["parties"])
            if p["playable"]
        }
        if not self.parties:
            self.parties = {-1: {"facts": [], "playable": True}}
        if scenario.party is not None:
            if scenario.party not in self.parties:
                raise ValueError("Selected party is not a playable source profile")
            self.parties = {scenario.party: self.parties[scenario.party]}
        self.party_effects = {
            i: [e for t in p["facts"] if (e := fact_effect(t))]
            for i, p in self.parties.items()
        }

        def party_vector(index):
            effects = self.party_effects[index]
            return (
                tuple(
                    sum(
                        e.value
                        for e in effects
                        if e.kind == "wealth_percent" and c in e.targets
                    )
                    for c in CATEGORIES
                )
                + tuple(
                    sum(e.value for e in effects if e.kind == kind)
                    for kind in (
                        "minor_wealth_percent",
                        "tax_percent",
                        "food_per_regions",
                        "food_per_provinces",
                    )
                )
                + (
                    sum(
                        e.value
                        for e in effects
                        if e.kind in {"order", "own_culture_order"}
                    ),
                )
            )

        vectors = {i: party_vector(i) for i in self.parties}
        self.pruned_parties = [
            i
            for i in self.parties
            if any(
                i != j
                and all(b >= a for a, b in zip(vectors[i], vectors[j]))
                and (vectors[i] != vectors[j] or j < i)
                for j in self.parties
            )
        ]
        self.parties = {
            i: p for i, p in self.parties.items() if i not in self.pruned_parties
        }
        self.party_effects = {
            i: e for i, e in self.party_effects.items() if i in self.parties
        }
        self.candidates, self.roles, self.exclusions = {}, {}, Counter()
        for site in scenario.sites:
            choices = {}
            for key, building in self.data["buildings"].items():
                occurrences = [
                    o
                    for o in building["occurrences"]
                    if scenario.faction in o["factions"]
                ]
                if not occurrences:
                    continue
                if building["level"] > scenario.maximum_level:
                    self.exclusions["above_level_four_or_special_monument"] += 1
                    continue
                legal = [
                    role for o in occurrences if (role := placement(building, o, site))
                ]
                if not legal:
                    continue
                role = legal[0]
                if any(r != role for r in legal):
                    raise ValueError("Ambiguous building placement")
                if role == "primary" and building["level"] > scenario.core_level:
                    continue
                if not any(
                    (e := raw_effect(x["id"], x["value"]))
                    and e.kind
                    in {
                        "wealth",
                        "wealth_percent",
                        "tax_percent",
                        "order",
                        "food",
                        "income_flat",
                    }
                    for x in building["effects"]
                ):
                    self.exclusions[
                        "no_effect_on_current_income_or_enforced_constraints"
                    ] += 1
                    continue
                choices[key] = building
                self.roles[(site.id, key)] = role
            # Some resources (notably iron and horses) stop at level three.
            primary_level = max(
                (
                    b["level"]
                    for key, b in choices.items()
                    if self.roles[(site.id, key)] == "primary"
                ),
                default=0,
            )
            choices = {
                key: b
                for key, b in choices.items()
                if self.roles[(site.id, key)] != "primary"
                or b["level"] == primary_level
            }
            if not any(self.roles[(site.id, k)] == "primary" for k in choices):
                raise ValueError(
                    f"No legal core building for {site.id}; resource assignment may be unsupported"
                )
            if site.port and not any(
                self.roles[(site.id, k)] == "port" for k in choices
            ):
                raise ValueError("Missing port candidates")
            self.candidates[site.id] = choices

    def fixed_value(self, kind, category=None):
        return sum(
            e.value
            for e in self.fixed
            if e.kind == kind and (category is None or category in e.targets)
        )

    def receives(self, raw):
        # One owned province in this model. Adjacency recipients require a world
        # model; they are not counted as food for the originating province.
        if raw["scope"] in LOCAL_SCOPES | GLOBAL_SCOPES:
            return (
                len(self.scenario.sites)
                if raw["scope"] in {"regions_in_this_province", "in_all_your_regions"}
                else 1
            )
        return 0

    def build(self, native=False):
        solver = (
            NativeSCIP()
            if native == "scip-nonlinear"
            else NativeCP()
            if native
            else pywraplp.Solver.CreateSolver("CBC")
        )
        choices, decision_names = {}, {}
        for site in self.scenario.sites:
            by_branch = defaultdict(list)
            primary, ports, ordinary = [], [], []
            for key, building in self.candidates[site.id].items():
                variable = solver.BoolVar(site.id + ":" + key)
                choices[(site.id, key)] = variable
                decision_names[variable_name(variable)] = (site.id, key)
                role = self.roles[(site.id, key)]
                {"primary": primary, "port": ports, "ordinary": ordinary}[role].append(
                    variable
                )
                if role == "ordinary":
                    by_branch[branch(building)].append(variable)
            solver.Add(sum(primary) == 1)
            if ports:
                solver.Add(sum(ports) == 1)
            solver.Add(sum(ordinary) <= site.capacity)
            for variables in by_branch.values():
                solver.Add(sum(variables) <= 1)
        parties = {i: solver.BoolVar("party:" + str(i)) for i in self.parties}
        solver.Add(sum(parties.values()) == 1)
        # Identical sites are interchangeable under the province-wide effects.
        signatures = {}
        for site in self.scenario.sites:
            keys = tuple(self.candidates[site.id])
            group = (site.major, site.port, site.resource, site.capacity, keys)
            signature = sum(
                (i + 1) * choices[(site.id, key)] for i, key in enumerate(keys)
            )
            if group in signatures:
                solver.Add(signatures[group] <= signature)
            signatures[group] = signature
        food = (
            self.scenario.external_food
            + self.fixed_value("food_per_provinces")
            + len(self.scenario.sites) * self.fixed_value("food_per_regions")
        )
        order = (
            self.scenario.order_offset
            + self.fixed_value("order")
            + self.fixed_value("own_culture_order")
        )
        base = {c: [] for c in CATEGORIES}
        minor_base = {c: [] for c in CATEGORIES}
        minor_modifiers = []
        minor_sites = {s.id for s in self.scenario.sites if not s.major}
        modifiers = {c: [] for c in CATEGORIES}
        tax = []
        flat_income = []
        for pair, variable in choices.items():
            building = self.candidates[pair[0]][pair[1]]
            for raw in building["effects"]:
                effect = raw_effect(raw["id"], raw["value"])
                if effect is None or not self.receives(raw):
                    continue
                if effect.kind == "wealth":
                    base[effect.targets[0]].append((effect.value, variable))
                    if pair[0] in minor_sites:
                        minor_base[effect.targets[0]].append((effect.value, variable))
                elif effect.kind == "wealth_percent":
                    for category in effect.targets:
                        modifiers[category].append((effect.value, variable))
                elif effect.kind == "food":
                    food += effect.value * self.receives(raw) * variable
                elif effect.kind == "order":
                    order += effect.value * variable
                elif effect.kind == "tax_percent":
                    tax.append((effect.value, variable))
                elif effect.kind == "income_flat":
                    flat_income.append((effect.value, variable))
                elif effect.kind == "minor_wealth_percent":
                    minor_modifiers.append((effect.value, variable))
        for i, variable in parties.items():
            for effect in self.party_effects[i]:
                if effect.kind == "wealth_percent":
                    for category in effect.targets:
                        modifiers[category].append((effect.value, variable))
                elif effect.kind == "food_per_provinces":
                    food += effect.value * variable
                elif effect.kind == "food_per_regions":
                    food += effect.value * len(self.scenario.sites) * variable
                elif effect.kind in {"order", "own_culture_order"}:
                    order += effect.value * variable
                elif effect.kind == "tax_percent":
                    tax.append((effect.value, variable))
                elif effect.kind == "minor_wealth_percent":
                    minor_modifiers.append((effect.value, variable))
        solver.Add(food >= 0)
        solver.Add(order >= self.scenario.minimum_order)
        aux_counter = 0

        def selection_upper(terms):
            amounts = defaultdict(int)
            for amount, variable in terms:
                amounts[variable_name(variable)] += amount
            upper = 0
            for site in self.scenario.sites:
                groups = defaultdict(list)
                for pair, variable in choices.items():
                    if pair[0] == site.id:
                        groups[self.roles[pair]].append(
                            max(0, amounts[variable_name(variable)])
                        )
                upper += max(groups["primary"], default=0) + max(
                    groups["port"], default=0
                )
                upper += sum(sorted(groups["ordinary"], reverse=True)[: site.capacity])
            upper += max(
                (max(0, amounts[variable_name(v)]) for v in parties.values()), default=0
            )
            return upper

        def selected_product(expression, selector, upper):
            nonlocal aux_counter
            aux_counter += 1
            y = solver.IntVar(0, upper, f"selected_product:{aux_counter}")
            solver.Add(y <= upper * selector)
            solver.Add(y <= expression)
            solver.Add(y >= expression - upper * (1 - selector))
            return y

        wealth, upper_wealth, combined_upper_terms = [], 0, []
        for category in CATEGORIES:
            if not base[category]:
                continue
            expression = sum(amount * variable for amount, variable in base[category])
            upper = selection_upper(base[category])
            constant = 100 + self.fixed_value("wealth_percent", category)
            grouped = defaultdict(int)
            for amount, variable in modifiers[category]:
                grouped[variable_name(variable)] += amount
            lookup = {variable_name(v): v for _, v in modifiers[category]}
            if constant + sum(min(0, a) for a in grouped.values()) < 0:
                raise ValueError(
                    "Negative wealth modifiers need an explicit zero-floor rule"
                )
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
                    == constant
                    + sum(amount * lookup[name] for name, amount in grouped.items())
                )
                solver.multiply(w, b, rate)
            else:
                solver.Add(
                    w
                    == constant * expression
                    + sum(
                        amount * selected_product(expression, lookup[name], upper)
                        for name, amount in grouped.items()
                        if amount
                    )
                )
            wealth.append(w)
            upper_wealth += upper_category
            minor_constant = self.fixed_value("minor_wealth_percent")
            if minor_base[category] and (minor_constant or minor_modifiers):
                minor_expression = sum(a * v for a, v in minor_base[category])
                minor_upper = selection_upper(minor_base[category])
                extra_upper = minor_upper * (
                    minor_constant + selection_upper(minor_modifiers)
                )
                combined_upper_terms.extend(
                    (
                        amount * (minor_constant + selection_upper(minor_modifiers)),
                        variable,
                    )
                    for amount, variable in minor_base[category]
                )
                extra = solver.IntVar(
                    0, extra_upper, "minor_wealth_hundredths:" + category
                )
                if native:
                    b_minor = solver.IntVar(0, minor_upper, "minor_base:" + category)
                    r_minor = solver.IntVar(
                        minor_constant,
                        minor_constant + selection_upper(minor_modifiers),
                        "minor_rate:" + category,
                    )
                    solver.Add(b_minor == minor_expression)
                    solver.Add(
                        r_minor
                        == minor_constant + sum(a * v for a, v in minor_modifiers)
                    )
                    solver.multiply(extra, b_minor, r_minor)
                else:
                    solver.Add(
                        extra
                        == minor_constant * minor_expression
                        + sum(
                            a * selected_product(minor_expression, v, minor_upper)
                            for a, v in minor_modifiers
                        )
                    )
                wealth.append(extra)
                upper_wealth += extra_upper
        total_wealth = sum(wealth)
        upper_wealth = min(upper_wealth, selection_upper(combined_upper_terms))
        factor = (
            100
            + self.scenario.tax_points
            - self.effective_corruption
            + self.fixed_value("tax_percent")
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
            solver.Add(
                rate == factor + sum(amount * variable for amount, variable in tax)
            )
            solver.multiply(income, w, rate)
        else:
            income = factor * total_wealth + sum(
                amount * selected_product(total_wealth, variable, upper_wealth)
                for amount, variable in tax
            )
        solver.Maximize(
            income + sum(amount * 10000 * variable for amount, variable in flat_income)
        )
        self.decisions, self.party_variables = (
            decision_names,
            {variable_name(v): i for i, v in parties.items()},
        )
        if native:
            return solver
        proto = linear_solver_pb2.MPModelProto()
        solver.ExportModelToProto(proto)
        return proto

    def evaluate(self, layout, party):
        if set(layout) != set(self.candidates) or party not in self.parties:
            raise ValueError("Layout/party coverage differs")
        base = Counter()
        minor_base = Counter()
        modifiers = Counter()
        fixed = self.fixed + self.party_effects[party]
        for effect in fixed:
            if effect.kind == "wealth_percent":
                for c in effect.targets:
                    modifiers[c] += effect.value
        food = self.scenario.external_food + sum(
            e.value * (len(self.scenario.sites) if e.kind == "food_per_regions" else 1)
            for e in fixed
            if e.kind in {"food_per_regions", "food_per_provinces"}
        )
        order = self.scenario.order_offset + sum(
            e.value for e in fixed if e.kind in {"order", "own_culture_order"}
        )
        tax = (
            self.scenario.tax_points
            - self.effective_corruption
            + sum(e.value for e in fixed if e.kind == "tax_percent")
        )
        sites = {}
        flat_income = 0
        for site in self.scenario.sites:
            keys = layout[site.id]
            if (
                len(keys) != len(set(keys))
                or set(keys) - self.candidates[site.id].keys()
            ):
                raise ValueError("Duplicate or unavailable building")
            roles = Counter(self.roles[(site.id, key)] for key in keys)
            if (
                roles["primary"] != 1
                or roles["port"] != int(site.port)
                or roles["ordinary"] > site.capacity
            ):
                raise ValueError("Invalid primary, port or ordinary slot occupancy")
            branches = Counter(
                branch(self.candidates[site.id][key])
                for key in keys
                if self.roles[(site.id, key)] == "ordinary"
            )
            if any(n > 1 for n in branches.values()):
                raise ValueError("Repeated branch in one settlement")
            local_food, local_order, growth = 0, 0, 0
            for key in keys:
                for raw in self.candidates[site.id][key]["effects"]:
                    effect = raw_effect(raw["id"], raw["value"])
                    if effect is None or not self.receives(raw):
                        continue
                    if effect.kind == "wealth":
                        base[effect.targets[0]] += effect.value
                        if not site.major:
                            minor_base[effect.targets[0]] += effect.value
                    elif effect.kind == "wealth_percent":
                        for c in effect.targets:
                            modifiers[c] += effect.value
                    elif effect.kind == "food":
                        local_food += effect.value * self.receives(raw)
                    elif effect.kind == "order":
                        local_order += effect.value
                    elif effect.kind == "tax_percent":
                        tax += effect.value
                    elif effect.kind == "income_flat":
                        flat_income += effect.value
                    elif effect.kind == "growth":
                        growth += effect.value
            food += local_food
            order += local_order
            sites[site.id] = {
                "buildings": sorted(keys),
                "ordinary_slots_used": roles["ordinary"],
                "ordinary_slots_available": site.capacity,
                "food_contribution": local_food,
                "order_contribution": local_order,
                "growth_contribution_unvalued": growth,
            }
        if food < 0 or order < self.scenario.minimum_order:
            raise ValueError("Food deficit or insufficient province public order")
        minor_percent = sum(e.value for e in fixed if e.kind == "minor_wealth_percent")
        categories = {
            c: {
                "base": base[c],
                "modifier_percent": modifiers[c],
                "minor_base": minor_base[c],
                "minor_bonus_percent": minor_percent,
                "modified": float(
                    Fraction(
                        base[c] * (100 + modifiers[c]) + minor_base[c] * minor_percent,
                        100,
                    )
                ),
            }
            for c in CATEGORIES
        }
        wealth = sum(
            Fraction(
                base[c] * (100 + modifiers[c]) + minor_base[c] * minor_percent, 100
            )
            for c in CATEGORIES
        )
        income = wealth * Fraction(100 + tax, 100)
        return {
            "domestic_tax_income": float(income),
            "domestic_net_income": float(income) + flat_income,
            "building_maintenance": -flat_income,
            "effective_corruption_points": self.effective_corruption,
            "modified_wealth": float(wealth),
            "tax_modifier_percent_net": tax,
            "food_surplus": food,
            "public_order": order,
            "categories": categories,
            "party_index": party,
            "party_facts": self.parties[party]["facts"],
            "sites": sites,
        }

    def fingerprint(self):
        self._prepared = self.build(native=True)
        proto = copy.deepcopy(self._prepared.model.proto)
        for variable in proto.variables:
            variable.name = ""
        self._fingerprint = hashlib.sha256(str(proto).encode()).hexdigest()
        return self._fingerprint

    def reuse_optimum(self, reference):
        if (
            reference["solver"]["status"] != "OPTIMAL"
            or reference.get("proof_fingerprint") != self.fingerprint()
        ):
            raise ValueError("Optimality proof does not describe this compiled model")
        layout = {site.id: [] for site in self.scenario.sites}
        party = None
        selected = set(reference["selected_decision_indices"])
        for variable in self._prepared.variables:
            if variable.index in selected:
                if variable.name in self.decisions:
                    site, key = self.decisions[variable.name]
                    layout[site].append(key)
                if variable.name in self.party_variables:
                    party = self.party_variables[variable.name]
        economics = self.evaluate(layout, party)
        if (
            abs(
                economics["domestic_net_income"]
                - reference.get("domestic_net_income", reference["domestic_tax_income"])
            )
            > 1e-5
        ):
            raise AssertionError("Reused optimum has different original economics")
        return {
            "scenario": asdict(self.scenario),
            "solver": {
                **reference["solver"],
                "seconds": 0,
                "proof_reused_from": reference["scenario"]["faction"],
            },
            "exclusions": dict(self.exclusions),
            "proof_fingerprint": self._fingerprint,
            "selected_decision_indices": reference["selected_decision_indices"],
            **economics,
        }

    def warm_values(self, reference):
        """Validate an incumbent and reconstruct exact native auxiliary values."""
        layout = {key: row["buildings"] for key, row in reference["sites"].items()}
        economics = self.evaluate(layout, reference["party_index"])
        if (
            abs(economics["domestic_net_income"] - reference["domestic_net_income"])
            > 1e-5
        ):
            raise ValueError("Warm start does not match original economics")
        values = {
            name: int(key in layout[site])
            for name, (site, key) in self.decisions.items()
        }
        values.update(
            {
                name: int(party == reference["party_index"])
                for name, party in self.party_variables.items()
            }
        )
        total = 0
        for category, row in economics["categories"].items():
            values["base:" + category] = row["base"]
            values["rate:" + category] = 100 + row["modifier_percent"]
            values["wealth_hundredths:" + category] = row["base"] * (
                100 + row["modifier_percent"]
            )
            values["minor_base:" + category] = row["minor_base"]
            values["minor_rate:" + category] = row["minor_bonus_percent"]
            values["minor_wealth_hundredths:" + category] = (
                row["minor_base"] * row["minor_bonus_percent"]
            )
            total += (
                values["wealth_hundredths:" + category]
                + values["minor_wealth_hundredths:" + category]
            )
        values["total_wealth_hundredths"] = total
        values["tax_factor"] = 100 + economics["tax_modifier_percent_net"]
        values["income_ten_thousandths"] = total * values["tax_factor"]
        return values

    def optimize(self, algorithm="cp-sat", seconds=10, workers=1, incumbent=None):
        start = perf_counter()
        if algorithm == "portfolio":
            first = self.optimize("cp-sat", seconds * 0.35, workers, incumbent)
            if first["solver"]["status"] == "OPTIMAL":
                first["solver"]["algorithm"] = "portfolio"
                first["solver"]["proof_backend"] = "cp-sat"
                return first
            seed = first if "sites" in first else incumbent
            second = self.optimize(
                "scip-nonlinear",
                max(0.01, seconds - (perf_counter() - start)),
                workers,
                seed,
            )
            feasible = [r for r in (first, second) if "sites" in r]
            if not feasible:
                return second
            result = copy.deepcopy(
                max(feasible, key=lambda r: r["domestic_net_income"])
            )
            bounds = [
                r["solver"]["bound"]
                for r in (first, second)
                if r["solver"]["bound"] is not None
            ]
            proven = next(
                (r for r in (first, second) if r["solver"]["status"] == "OPTIMAL"), None
            )
            result["solver"].update(
                algorithm="portfolio",
                seconds=perf_counter() - start,
                bound=min(bounds) if bounds else None,
                status="OPTIMAL" if proven else "FEASIBLE",
                proof_backend=proven["solver"]["algorithm"] if proven else None,
                stages=[first["solver"], second["solver"]],
            )
            return result
        if algorithm == "scip-nonlinear":
            problem = self.build(native="scip-nonlinear")
            solver = problem.model
            solver.setParam("limits/time", seconds)
            solver.setParam("numerics/feastol", 1e-9)
            if incumbent is not None:
                values = self.warm_values(incumbent)
                solution = solver.createSol()
                for variable in problem.variables:
                    solver.setSolVal(solution, variable, values[variable.name])
                if not solver.addSol(solution):
                    raise ValueError("SCIP rejected independently validated warm start")
            solver.optimize()
            status = str(solver.getStatus()).upper()
            label = (
                "OPTIMAL"
                if status == "OPTIMAL"
                else "INFEASIBLE"
                if status == "INFEASIBLE"
                else "FEASIBLE"
                if solver.getNSols()
                else "UNKNOWN"
            )
            report = {
                "scenario": asdict(self.scenario),
                "solver": {
                    "algorithm": algorithm,
                    "status": label,
                    "seconds": perf_counter() - start,
                    "objective": None,
                    "bound": None,
                    "variables": len(problem.variables),
                    "constraints": solver.getNConss(),
                },
                "exclusions": dict(self.exclusions),
            }
            if solver.getNSols():
                layout = {site.id: [] for site in self.scenario.sites}
                party = None
                for variable in problem.variables:
                    if solver.getVal(variable) > 0.5:
                        if variable.name in self.decisions:
                            site, key = self.decisions[variable.name]
                            layout[site].append(key)
                        if variable.name in self.party_variables:
                            party = self.party_variables[variable.name]
                economics = self.evaluate(layout, party)
                objective = solver.getObjVal() / 10000
                if abs(objective - economics["domestic_net_income"]) > 1e-5:
                    raise AssertionError(
                        "Independent economics disagrees with nonlinear SCIP"
                    )
                report["solver"].update(
                    objective=objective, bound=solver.getDualbound() / 10000
                )
                report.update(economics)
            return report
        if algorithm == "cp-sat":
            if not hasattr(self, "_prepared"):
                self.fingerprint()
            problem = self._prepared
            if incumbent is not None:
                values = self.warm_values(incumbent)
                problem.model.clear_hints()
                for variable in problem.variables:
                    problem.model.add_hint(variable, values[variable.name])
            error = problem.model.validate()
            if error:
                raise ValueError(error)
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = seconds
            solver.parameters.num_search_workers = workers
            solver.parameters.random_seed = 0
            status = solver.solve(problem.model)
            report = {
                "scenario": asdict(self.scenario),
                "solver": {
                    "algorithm": algorithm,
                    "status": solver.status_name(status),
                    "seconds": perf_counter() - start,
                    "objective": None,
                    "bound": None,
                    "variables": len(problem.model.proto.variables),
                    "constraints": len(problem.model.proto.constraints),
                },
                "exclusions": dict(self.exclusions),
            }
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                layout = {site.id: [] for site in self.scenario.sites}
                party = None
                for variable in problem.variables:
                    if solver.value(variable) > 0:
                        if variable.name in self.decisions:
                            site, key = self.decisions[variable.name]
                            layout[site].append(key)
                        if variable.name in self.party_variables:
                            party = self.party_variables[variable.name]
                economics = self.evaluate(layout, party)
                objective = solver.objective_value / 10000
                if abs(objective - economics["domestic_net_income"]) > 1e-5:
                    raise AssertionError("Independent economics disagrees with CP-SAT")
                report["solver"].update(
                    objective=objective, bound=solver.best_objective_bound / 10000
                )
                report.update(economics)
                report["proof_fingerprint"] = self._fingerprint
                report["selected_decision_indices"] = [
                    v.index
                    for v in problem.variables
                    if (v.name in self.decisions or v.name in self.party_variables)
                    and solver.value(v)
                ]
            return report
        proto = self.build()
        if algorithm not in {"cp-sat", "cbc", "scip"}:
            raise ValueError("Choose cp-sat, cbc or scip")
        solver = pywraplp.Solver.CreateSolver(
            {"cp-sat": "SAT", "cbc": "CBC", "scip": "SCIP"}[algorithm]
        )
        error = solver.LoadModelFromProtoKeepNames(proto)
        if error:
            raise ValueError(error)
        solver.SetTimeLimit(max(1, int(seconds * 1000)))
        if algorithm == "cp-sat":
            solver.SetSolverSpecificParametersAsString(
                f"num_search_workers: {workers}\nrandom_seed: 0"
            )
        status = solver.Solve()
        label = {
            solver.OPTIMAL: "OPTIMAL",
            solver.FEASIBLE: "FEASIBLE",
            solver.INFEASIBLE: "INFEASIBLE",
            solver.NOT_SOLVED: "UNKNOWN",
            solver.MODEL_INVALID: "MODEL_INVALID",
            solver.ABNORMAL: "ABNORMAL",
        }.get(status, "UNKNOWN")
        report = {
            "scenario": asdict(self.scenario),
            "solver": {
                "algorithm": algorithm,
                "status": label,
                "seconds": perf_counter() - start,
                "objective": None,
                "bound": None,
                "variables": len(proto.variable),
                "constraints": len(proto.constraint),
            },
            "exclusions": dict(self.exclusions),
        }
        if status in (solver.OPTIMAL, solver.FEASIBLE):
            if not solver.VerifySolution(1e-5, False):
                raise AssertionError(
                    "Solver returned an invalid integer model solution"
                )
            layout = {site.id: [] for site in self.scenario.sites}
            selected_party = None
            for variable in solver.variables():
                if variable.solution_value() > 0.5:
                    if variable.name() in self.decisions:
                        site, key = self.decisions[variable.name()]
                        layout[site].append(key)
                    if variable.name() in self.party_variables:
                        selected_party = self.party_variables[variable.name()]
            economics = self.evaluate(layout, selected_party)
            objective = solver.Objective().Value() / 10000
            if abs(objective - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError(
                    "Independent economics disagrees with solver objective"
                )
            report["solver"].update(
                objective=objective, bound=solver.Objective().BestBound() / 10000
            )
            report.update(economics)
        return report
