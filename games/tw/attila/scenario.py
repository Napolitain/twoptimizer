"""Strict, explicit campaign inputs for the static Attila model."""

from copy import deepcopy
from math import isfinite

from games.tw.attila.effects import METRICS, RULES, Reach, reach


class Scenario:
    def __init__(self, data=None):
        self.data = deepcopy({} if data is None else data)
        allowed = {
            "provinces",
            "regions",
            "adjacency",
            "conditional_targets",
            "external_effects",
            "base_tariffs",
            "resource_prices",
            "resource_demand",
            "targets",
            "weights",
            "projects",
            "project_budget",
            "campaign",
            "faction_traits",
            "technology_effects",
            "religion_traits",
        }
        self.keys(self.data, allowed, "scenario")
        for key in ("faction_traits", "technology_effects", "religion_traits"):
            if key in self.data and not isinstance(self.data[key], bool):
                raise ValueError(f"{key} must be Boolean")
        self._validate_campaign()
        for key in (
            "provinces",
            "regions",
            "adjacency",
            "conditional_targets",
            "resource_prices",
            "resource_demand",
        ):
            if key in self.data and not isinstance(self.data[key], dict):
                raise TypeError(f"{key} must be an object")
        for key in ("targets", "weights", "external_effects", "projects"):
            if key in self.data and not isinstance(self.data[key], list):
                raise TypeError(f"{key} must be a list")
        self._validate_area_values()
        self.number(self.data.get("base_tariffs", 0), nonnegative=True)
        self._validate_resources()
        self._validate_metrics()
        self._validate_external_effects()
        self._validate_projects()
        if "project_budget" in self.data:
            self.number(self.data["project_budget"], nonnegative=True)

    def _validate_resources(self):
        for key in ("resource_prices", "resource_demand"):
            for name, value in self.data.get(key, {}).items():
                if f"resource:{name}" not in METRICS:
                    raise ValueError(f"Unknown resource: {name}")
                self.number(value, nonnegative=True)

    def _validate_projects(self):
        for project in self.data.get("projects", []):
            if not isinstance(project, dict) or not {"region", "base_cost"} <= project.keys():
                raise ValueError("Missing required project fields")
            self.keys(
                project,
                {
                    "name",
                    "region",
                    "base_cost",
                    "sanitation",
                    "conversion",
                    "main_settlement",
                    "category",
                },
                "project",
            )
            self.number(project["base_cost"], nonnegative=True)
            if "category" in project and project["category"] not in {
                "main",
                "civic",
                "agriculture",
                "industry",
                "religious",
                "military",
            }:
                raise ValueError("Invalid construction project category")
            for key in ("sanitation", "conversion", "main_settlement"):
                if key in project and not isinstance(project[key], bool):
                    raise ValueError(f"{key} must be Boolean")

    def _validate_external_effects(self):
        for record in self.data.get("external_effects", []):
            if (
                not isinstance(record, dict)
                or not {"effect", "scope", "amount", "region"} <= record.keys()
            ):
                raise ValueError("Missing required external effect fields")
            self.keys(record, {"effect", "scope", "amount", "region"}, "external_effects")
            if record.get("effect") not in RULES or reach(record.get("scope", "")) == Reach.OTHER:
                raise ValueError(
                    "External effect must have a recognized settlement effect and scope"
                )
            self.number(record["amount"])

    def _validate_metrics(self):
        for kind in ("targets", "weights"):
            for record in self.data.get(kind, []):
                if (
                    not isinstance(record, dict)
                    or not {"metric", "scope", "value"} <= record.keys()
                ):
                    raise ValueError(f"Missing required {kind} fields")
                self.keys(
                    record,
                    {"metric", "scope", "target", "value"},
                    kind,
                    {"metric", "scope", "value"},
                )
                if record.get("metric") not in METRICS:
                    raise ValueError(f"Unknown metric in {kind}")
                if record.get("scope") not in ("region", "province", "faction"):
                    raise ValueError("Invalid metric scope")
                self.number(record["value"])

    def _validate_area_values(self):
        for area, fields in (
            (
                "provinces",
                {
                    "corruption_percent",
                    "tax_percent",
                    "immigration_order",
                    "religious_order",
                    "public_order",
                    "food",
                    "minimum_food",
                    "minimum_public_order",
                },
            ),
            (
                "regions",
                {
                    "wealth_percent",
                    "immigration_wealth",
                    "food",
                    "sanitation",
                    "minimum_sanitation",
                },
            ),
        ):
            for name, values in self.data.get(area, {}).items():
                self.keys(values, fields, f"{area}.{name}")
                for key, value in values.items():
                    if key == "wealth_percent":
                        self.keys(
                            value,
                            {
                                "all",
                                "agriculture",
                                "livestock",
                                "industry",
                                "culture",
                                "commerce",
                                "maritime",
                                "subsistence",
                            },
                            "wealth_percent",
                        )
                        for number in value.values():
                            self.number(number)
                    else:
                        self.number(value)
                        if key == "corruption_percent" and not 0 <= value <= 100:
                            raise ValueError("Corruption must be in [0,100]")
                        if key in ("tax_percent", "immigration_wealth") and value < 0:
                            raise ValueError(f"{key} must be nonnegative")
                        if key in ("immigration_order", "religious_order") and value > 0:
                            raise ValueError("immigration_order is a nonpositive base penalty")

    def _validate_campaign(self):
        campaign = self.data.get("campaign", {})
        self.keys(
            campaign,
            {
                "province_capitals_held",
                "active_trade_routes",
                "base_tribute",
                "at_peace_with_sassanids",
                "poor_fertility_regions",
            },
            "campaign",
        )
        for key in ("province_capitals_held", "active_trade_routes"):
            if key in campaign and (
                isinstance(campaign[key], bool)
                or not isinstance(campaign[key], int)
                or campaign[key] < 0
            ):
                raise ValueError(f"{key} must be a nonnegative integer")
        self.number(campaign.get("base_tribute", 0), nonnegative=True)
        if "at_peace_with_sassanids" in campaign and not isinstance(
            campaign["at_peace_with_sassanids"], bool
        ):
            raise ValueError("at_peace_with_sassanids must be Boolean")
        if "poor_fertility_regions" in campaign and (
            not isinstance(campaign["poor_fertility_regions"], list)
            or not all(isinstance(r, str) for r in campaign["poor_fertility_regions"])
        ):
            raise ValueError("poor_fertility_regions must be a list of region IDs")

    @staticmethod
    def keys(record, allowed, label, required=()):
        if not isinstance(record, dict):
            raise TypeError(f"{label} must be an object")
        if set(required) - record.keys():
            raise ValueError(f"Missing required {label} fields")
        unknown = set(record) - allowed
        if unknown:
            raise ValueError(f"Unknown {label} fields: {sorted(unknown)}")

    @staticmethod
    def number(value, nonnegative=False):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError("Scenario numbers must be finite")
        if nonnegative and value < 0:
            raise ValueError("Value must be nonnegative")

    def bind(self, provinces):
        province_ids = {p.name for p in provinces}
        region_ids = {r.name for p in provinces for r in p.regions}
        if set(self.data.get("campaign", {}).get("poor_fertility_regions", [])) - region_ids:
            raise ValueError("Unknown poor fertility regions")
        for key, known in (("provinces", province_ids), ("regions", region_ids)):
            if set(self.data.get(key, {})) - known:
                raise ValueError(f"Unknown or unselected {key} in scenario")
        for origin, neighbors in self.data.get("adjacency", {}).items():
            if (
                not isinstance(neighbors, list)
                or origin not in province_ids
                or set(neighbors) - province_ids
                or origin in neighbors
            ):
                raise ValueError(
                    "Adjacency must reference distinct selected provinces; use a joint problem"
                )
        self._bind_conditional_targets(province_ids)
        self._bind_metric_targets(region_ids, province_ids)
        for record in self.data.get("external_effects", []) + self.data.get("projects", []):
            if record.get("region") not in region_ids:
                raise ValueError("Unknown source/project region")
        return self

    def _bind_metric_targets(self, region_ids, province_ids):
        for kind in ("targets", "weights"):
            for record in self.data.get(kind, []):
                known = (
                    region_ids
                    if record["scope"] == "region"
                    else province_ids
                    if record["scope"] == "province"
                    else {"faction"}
                )
                if record.get("target", "faction") not in known:
                    raise ValueError(f"Unknown {kind} target")

    def _bind_conditional_targets(self, province_ids):
        for effect, mapping in self.data.get("conditional_targets", {}).items():
            if effect not in {
                "att_effect_public_order_base_neighbouring",
                "att_effect_food_production_fertility_neighbouring",
            }:
                raise ValueError(f"Not a supported conditional effect: {effect}")
            if not isinstance(mapping, dict):
                raise TypeError("Conditional recipients must be an object")
            for origin, targets in mapping.items():
                if (
                    origin not in province_ids
                    or not isinstance(targets, list)
                    or set(targets) - province_ids
                ):
                    raise ValueError("Conditional targets must reference selected provinces")

    def region(self, region, key, default=0):
        return self.data.get("regions", {}).get(region.name, {}).get(key, default)

    def province(self, province, key, default=0):
        name = province if isinstance(province, str) else province.name
        return self.data.get("provinces", {}).get(name, {}).get(key, default)
