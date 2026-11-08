"""Exact integer linearization of provincial wealth, tax and shared food."""

import copy
import hashlib
from collections import Counter
from fractions import Fraction

from games.tw.immutable import freeze
from games.tw.rome2 import building_constraints
from games.tw.rome2.catalog import load_data
from games.tw.rome2.effects import CATEGORIES, Effect, fact_effect, raw_effect
from games.tw.rome2.placement import branch, placement
from games.tw.rome2.records import (
    BuildingRecord,
    Catalog,
    CategoryEconomics,
    Economics,
    PartyRecord,
    SiteEconomics,
)
from games.tw.rome2.scenario import Scenario

LOCAL_SCOPES = {
    "this_building",
    "this_region",
    "this_province",
    "regions_in_this_province",
}
GLOBAL_SCOPES = {"this_faction", "in_all_your_regions", "in_all_your_provinces"}


def variable_name(variable):
    return variable.name() if callable(variable.name) else variable.name


class Economy:
    def __init__(self, scenario: Scenario, data: Catalog | None = None, *, required_candidates=()):
        self.data = load_data() if data is None else freeze(data)
        self.scenario = scenario
        self.required_candidates = (
            set(scenario.required_buildings)
            | set(scenario.retained_buildings)
            | set(required_candidates)
        )
        self.decisions: dict[str, tuple[str, str]] = {}
        self.party_variables: dict[str, int] = {}
        self._validate_scenario(scenario)
        self.faction = self.data["factions"][scenario.faction]
        self._load_modifiers(scenario)
        self.effective_corruption = max(
            0, scenario.corruption_points + self.fixed_value("corruption_percent")
        )
        self._load_parties(scenario)
        self._load_candidates(scenario)
        building_constraints.validate(scenario, self.data["buildings"], self.candidates)

    def _load_candidates(self, scenario):
        self.candidates: dict[str, dict[str, BuildingRecord]] = {}
        self.roles: dict[tuple[str, str], str] = {}
        self.exclusions = Counter()
        for site in scenario.sites:
            choices = self._site_candidates(scenario, site)
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
                or key in self.required_candidates
            }
            if not any(self.roles[(site.id, k)] == "primary" for k in choices):
                raise ValueError(
                    f"No legal core building for {site.id}; resource assignment may be unsupported"
                )
            if site.port and not any(self.roles[(site.id, k)] == "port" for k in choices):
                raise ValueError("Missing port candidates")
            self.candidates[site.id] = choices

    def _site_candidates(self, scenario, site):
        choices = {}
        for key, building in self.data["buildings"].items():
            occurrences = [o for o in building["occurrences"] if scenario.faction in o["factions"]]
            if not occurrences:
                continue
            if building["level"] > scenario.maximum_level:
                self.exclusions["above_level_four_or_special_monument"] += 1
                continue
            legal = [role for o in occurrences if (role := placement(building, o, site))]
            if not legal:
                continue
            role = legal[0]
            if any(r != role for r in legal):
                raise ValueError("Ambiguous building placement")
            if role == "primary" and building["level"] > scenario.core_level:
                continue
            if key not in self.required_candidates and not any(
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
                self.exclusions["no_effect_on_current_income_or_enforced_constraints"] += 1
                continue
            choices[key] = building
            self.roles[(site.id, key)] = role
        return choices

    def _load_parties(self, scenario):
        self.parties: dict[int, PartyRecord] = {
            i: p for i, p in enumerate(self.faction["traits"]["parties"]) if p["playable"]
        }
        if not self.parties:
            self.parties = {-1: {"facts": [], "playable": True}}
        if scenario.party is not None:
            if scenario.party not in self.parties:
                raise ValueError("Selected party is not a playable source profile")
            self.parties = {scenario.party: self.parties[scenario.party]}
        self.party_effects = {
            i: [e for t in p["facts"] if (e := fact_effect(t))] for i, p in self.parties.items()
        }

        def party_vector(index):
            effects = self.party_effects[index]
            return (
                tuple(
                    sum(e.value for e in effects if e.kind == "wealth_percent" and c in e.targets)
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
                + (sum(e.value for e in effects if e.kind in {"order", "own_culture_order"}),)
            )

        vectors = {i: party_vector(i) for i in self.parties}
        self.pruned_parties = [
            i
            for i in self.parties
            if any(
                i != j
                and all(b >= a for a, b in zip(vectors[i], vectors[j], strict=False))
                and (vectors[i] != vectors[j] or j < i)
                for j in self.parties
            )
        ]
        self.parties = {i: p for i, p in self.parties.items() if i not in self.pruned_parties}
        self.party_effects = {i: e for i, e in self.party_effects.items() if i in self.parties}

    def _load_modifiers(self, scenario):
        self.fixed = []
        for modifier in scenario.modifiers:
            if (
                modifier.kind
                not in {
                    "wealth_percent",
                    "tax_percent",
                    "order",
                    "food_per_provinces",
                    "food_per_regions",
                    "corruption_percent",
                }
                or not isinstance(modifier.value, int)
                or set(modifier.targets) - set(CATEGORIES)
            ):
                raise ValueError("Unsupported explicit scenario modifier")
            self.fixed.append(
                Effect(
                    modifier.kind,
                    modifier.value,
                    tuple(modifier.targets),
                )
            )
        for text in self.faction["traits"]["culture_facts"]:
            if effect := fact_effect(text):
                self.fixed.append(effect)
        self._load_technologies(scenario)

    def _load_technologies(self, scenario):
        if scenario.all_technologies:
            if scenario.technology_profile not in {"public", "archived"}:
                raise ValueError("Select public or archived technology profile")
            coverage = self.data.get("technology_coverage", {}).get(scenario.faction, {})
            if (
                scenario.technology_profile == "public"
                and coverage.get("complete_public_tree") is False
            ):
                raise ValueError(
                    "Public research tree is incomplete; use the explicit no-technologies"
                    " baseline or an available archival profile"
                )
            trees = (
                self.data["technologies"]
                if scenario.technology_profile == "public"
                else self.data.get("technologies_archived", {})
            )
            if scenario.faction not in trees:
                raise ValueError("Requested research profile is unavailable for this faction")
            for technology in trees[scenario.faction].values():
                for text in technology["facts"]:
                    if effect := fact_effect(text):
                        self.fixed.append(effect)

    def _validate_scenario(self, scenario):
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
        if any(not isinstance(s.capacity, int) or s.capacity < 0 for s in scenario.sites):
            raise ValueError("Invalid ordinary slot capacity")

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
        from games.tw.rome2.compiler import RomeCompiler

        return RomeCompiler(self).build(native)

    def evaluate(self, layout, party) -> Economics:
        if set(layout) != set(self.candidates) or party not in self.parties:
            raise ValueError("Layout/party coverage differs")
        building_constraints.validate_layout(self.scenario, layout)
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
        sites: dict[str, SiteEconomics] = {}
        flat_income = 0
        for site in self.scenario.sites:
            keys, roles = self._validate_site_layout(layout, site)
            local_food, local_order, growth, tax, flat_income = self._evaluate_buildings(
                keys, site, base, minor_base, modifiers, tax, flat_income
            )
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
        categories: dict[str, CategoryEconomics] = {
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
            Fraction(base[c] * (100 + modifiers[c]) + minor_base[c] * minor_percent, 100)
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
            "party_facts": list(self.parties[party]["facts"]),
            "sites": sites,
        }

    @staticmethod
    def _evaluate_wealth_effect(effect, site, base, minor_base, modifiers):
        if effect.kind == "wealth":
            base[effect.targets[0]] += effect.value
            if not site.major:
                minor_base[effect.targets[0]] += effect.value
            return True
        if effect.kind == "wealth_percent":
            for category in effect.targets:
                modifiers[category] += effect.value
            return True
        return False

    def _evaluate_buildings(self, keys, site, base, minor_base, modifiers, tax, flat_income):
        local_food, local_order, growth = 0, 0, 0
        for key in keys:
            for raw in self.candidates[site.id][key]["effects"]:
                effect = raw_effect(raw["id"], raw["value"])
                if effect is None or not self.receives(raw):
                    continue
                if self._evaluate_wealth_effect(effect, site, base, minor_base, modifiers):
                    continue
                if effect.kind == "food":
                    local_food += effect.value * self.receives(raw)
                elif effect.kind == "order":
                    local_order += effect.value
                elif effect.kind == "tax_percent":
                    tax += effect.value
                elif effect.kind == "income_flat":
                    flat_income += effect.value
                elif effect.kind == "growth":
                    growth += effect.value
        return local_food, local_order, growth, tax, flat_income

    def _validate_site_layout(self, layout, site):
        keys = layout[site.id]
        if len(keys) != len(set(keys)) or set(keys) - self.candidates[site.id].keys():
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
        return keys, roles

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
            "scenario": self.scenario.to_dict(),
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
        if abs(economics["domestic_net_income"] - reference["domestic_net_income"]) > 1e-5:
            raise ValueError("Warm start does not match original economics")
        values = {name: int(key in layout[site]) for name, (site, key) in self.decisions.items()}
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
            values["wealth_hundredths:" + category] = row["base"] * (100 + row["modifier_percent"])
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

    def optimize(
        self,
        algorithm="cp-sat",
        seconds=None,
        workers=None,
        incumbent=None,
        *,
        on_search=None,
        on_model=None,
        cancellation=None,
        on_phase=None,
    ):
        from games.tw.rome2.optimization import RomeOptimizer

        return RomeOptimizer(self).optimize(
            algorithm,
            seconds,
            workers,
            incumbent,
            on_search=on_search,
            on_model=on_model,
            cancellation=cancellation,
            on_phase=on_phase,
        )
