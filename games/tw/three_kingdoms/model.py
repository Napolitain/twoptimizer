"""Static historical commandery economy with explicit ownership and scenario inputs."""

from collections import Counter

from games.tw.immutable import freeze
from games.tw.three_kingdoms.catalog import building_effects, load_data
from games.tw.three_kingdoms.product_metadata import Product
from games.tw.three_kingdoms.scenario import Scenario
from games.tw.three_kingdoms.scopes import ECONOMIC


class Economy:
    def __init__(self, scenario: Scenario, data=None):
        self.data = load_data() if data is None else freeze(data)
        self.scenario = scenario
        self._validate_scenario()
        self.faction = self.data["factions"][scenario.faction]
        self.provinces = {p.id: p for p in scenario.commanderies}
        self.regions = {
            key: row
            for key, row in self.data["regions"].items()
            if row["commandery"] in self.provinces
        }
        self.exclusions = Counter()
        self.limitations = [
            "Historical vanilla 1.2 public Assembly Kit reference; "
            "not current installed-game data.",
            "Static full commandery ownership, normal tax, normal fertility, non-harvest season, "
            "supplied population and base corruption.",
            "Original starting ruler remains in power; "
            "only sourced static leader modifiers are included.",
            "Population uses the source's thousand-person bands; growth is not optimized.",
            "Construction costs and time, characters, assignments and dynamic faction resources "
            "are outside this snapshot.",
            "Corruption uses exact proportional modifiers; "
            "game-interface rounding is not simulated.",
        ]
        if not scenario.include_leader_effects:
            self.limitations[2] = "Starting-leader modifiers are disabled by the scenario."
        self.reforms = self._reforms()
        self.effects = {}
        self.candidates = {county: self._candidates(county) for county in self.regions}
        self._validate_choices()
        self._validate_borders()
        self.decisions = {}
        self.products: tuple[Product, ...] = ()

    def _validate_scenario(self):
        if self.scenario.faction not in self.data["factions"]:
            raise ValueError("Unknown Three Kingdoms faction")
        for province in self.scenario.commanderies:
            if province.id not in self.data["commanderies"]:
                raise ValueError(f"Unknown commandery: {province.id}")
        capital = self.scenario.capital_commandery
        if capital is not None and capital not in self.data["commanderies"]:
            raise ValueError("Unknown faction-capital commandery")
        if set(self.scenario.external_resources) - self.data["resources"].keys():
            raise ValueError("Unknown external resource")

    def _reforms(self):
        return {
            key: reform
            for key, reform in self.data["reforms"].items()
            if reform["subculture"] in {"", self.faction["subculture"]}
            and reform["faction"] in {"", self.scenario.faction}
        }

    def _candidates(self, county):
        region = self.regions[county]
        province = self.provinces[region["commandery"]]
        choices = {}
        for key, building in self.data["buildings"].items():
            reason = self._unavailable(building, region, province)
            if reason:
                self.exclusions[reason] += 1
                continue
            effects = building_effects(building, self.faction)
            self.effects[(county, key)] = effects
            choices[key] = building
        return choices

    def _unavailable(self, building, region, province):
        if building["chain"] not in self.faction["chains"]:
            return "faction_building_roster"
        if building["superchain"] not in (
            *region["primary_superchains"],
            *region["secondary_superchains"],
            *region["port_superchains"],
        ):
            return "county_slot_template"
        if building["kind"] == "city" and province.city_level is not None:
            return None if building["level"] == province.city_level else "fixed_city_level"
        if reason := self._city_requirement(building, province):
            return reason
        if building["only_in_capital"] and region["commandery"] != self.scenario.capital_commandery:
            return "faction_capital_required"
        if (
            not self.scenario.all_reforms
            and set(building["required_technologies"]) & self.reforms.keys()
        ):
            return "reform_required"
        return None

    @staticmethod
    def _city_requirement(building, province):
        if building["kind"] == "city" and building["level"] == 0:
            return "abandoned_city_outside_snapshot"
        if province.city_level is not None and building["minimum_city_level"] > province.city_level:
            return "city_level_requirement"
        return None

    def role(self, county, building):
        region = self.regions[county]
        if building["superchain"] in region["primary_superchains"]:
            return "primary"
        if building["superchain"] in region["port_superchains"]:
            return "port"
        return "district"

    def _validate_choices(self):
        for county, buildings in self.candidates.items():
            if not any(self.role(county, b) == "primary" for b in buildings.values()):
                raise ValueError(f"No supported primary building for {county}")
        requested = set(self.scenario.required_buildings) | set(self.scenario.forbidden_buildings)
        if requested - self.data["buildings"].keys():
            raise ValueError("Unknown required or forbidden building")
        available = {key for buildings in self.candidates.values() for key in buildings}
        if set(self.scenario.required_buildings) - available:
            raise ValueError(
                "Required building is unavailable for this faction, holding or research"
            )

    def _validate_borders(self):
        if self.scenario.adjacency is not None or len(self.provinces) == 1:
            return
        for effects in self.effects.values():
            for effect in effects:
                if effect["scope"] != "adjacent_provinces" or effect["metric"] not in ECONOMIC:
                    continue
                if effect["metric"] != "corruption_percent" or any(
                    p.corruption_percent for p in self.scenario.commanderies
                ):
                    raise ValueError(
                        "Supply explicit commandery adjacency for nonzero-corruption holdings"
                    )
        self.limitations.append(
            "Full campaign adjacency is unavailable; "
            "adjacent effects are immaterial at zero base corruption."
        )

    def population_effects(self, province):
        amount = province.population // self.data["rules"]["population_unit"]
        return next(
            band
            for band in self.data["rules"]["population_bands"]
            if band["minimum"] <= amount <= band["maximum"]
        )

    def fixed_effects(self):
        effects = (
            list(self.faction.get("leader_effects", ()))
            if self.scenario.include_leader_effects
            else []
        )
        if self.scenario.all_reforms:
            effects.extend(
                effect for reform in self.reforms.values() for effect in reform["effects"]
            )
        effects.extend(self.faction.get("faction_effects", ()))
        return tuple(effect for effect in effects if effect["metric"] in ECONOMIC)

    def compile(self):
        from games.tw.three_kingdoms.compiler import Compiler

        return Compiler(self).compile()

    def evaluate(self, layout):
        from games.tw.three_kingdoms.evaluation import evaluate

        return evaluate(self, layout)

    def optimize(
        self,
        algorithm="cp-sat",
        seconds=None,
        workers=None,
        *,
        on_search=None,
        on_model=None,
        on_phase=None,
        cancellation=None,
        incumbent=None,
        local_incumbents=None,
        native_products=None,
    ):
        from games.tw.three_kingdoms.optimization import optimize

        return optimize(
            self,
            algorithm,
            seconds,
            workers,
            on_search=on_search,
            on_model=on_model,
            on_phase=on_phase,
            cancellation=cancellation,
            incumbent=incumbent,
            local_incumbents=local_incumbents,
            native_products=native_products,
        )
