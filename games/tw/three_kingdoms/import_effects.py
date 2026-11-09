"""Resolve historical effect mappings without interpreting names as numeric rules."""

from collections import defaultdict

from games.tw.three_kingdoms.source import SourceArchive

FOOD_CATEGORIES = {
    "3k_main_pooled_factor_junction_food_local_farming": "farming",
    "3k_main_pooled_factor_junction_food_fishing": "fishing",
    "3k_main_pooled_factor_junction_food_from_foraging": "foraging",
    "3k_main_pooled_factor_junction_food_sold": "sold",
    "3k_main_pooled_factor_junction_food_distribution": "distribution",
    "3k_main_pooled_factor_junction_food_from_population": "population",
}


def _scope(raw: str) -> str:
    if raw == "building_to_province_enemy_adjacent":
        return "enemy_adjacent_provinces"
    if raw == "building_to_province_own_adjacent":
        return "adjacent_provinces"
    if (
        "factionwide" in raw
        or raw.startswith(("faction_to_region_own", "faction_to_province_own"))
        or raw
        in {
            "faction_to_faction_own",
            "faction_to_faction_own_unseen",
            "building_to_faction_unseen",
        }
    ):
        return "faction"
    if (
        "provincewide" in raw
        or "to_province_own" in raw
        or raw.startswith("province_to_region_own")
    ):
        return "province"
    if raw.startswith(("region_to_region_own", "building_to_building_own")):
        return "region"
    return "unmodeled"


class EffectMappings:
    """Map each effect to all affected economic categories, keeping raw scopes."""

    def __init__(self, archive: SourceArchive):
        self.mappings: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for row in archive.table("effect_bonus_value_region_gdp_type_junctions"):
            metric = {"region_gdp": "wealth", "region_gdp_mod": "wealth_percent"}.get(
                row["bonus_value_id"]
            )
            if metric:
                self.mappings[row["effect"]].append((metric, row["region_gdp_type"]))
        self._basic(archive)
        self._food(archive)
        self.mappings["3k_main_effect_province_building_slot_unlocks_dummy"].append(("slots", ""))
        for suffix in ("", "_unseen"):
            self.mappings[f"3k_main_effect_province_population_capacity{suffix}"].append(
                ("population_capacity", "")
            )

    def _basic(self, archive: SourceArchive) -> None:
        for row in archive.table("effect_bonus_value_basic_junction"):
            bonus = row["bonus_value_id"]
            metric = ""
            if bonus == "admin_cost_mod":
                metric = "corruption_percent"
            elif bonus.startswith("province_public_order_happiness_"):
                metric = "order"
            if metric:
                self.mappings[row["effect"]].append((metric, ""))

    def _food(self, archive: SourceArchive) -> None:
        metrics = {"base_amount": "food", "percentage_multiplier_mod": "food_percent"}
        for row in archive.table("effect_bonus_value_pooled_resource_factor_junctions"):
            category = FOOD_CATEGORIES.get(row["resource_factor"])
            metric = metrics.get(row["bonus_value_id"])
            if category and metric:
                self.mappings[row["effect"]].append((metric, category))

    def normalize(self, effect: str, scope: str, value: str) -> list[dict]:
        number = float(value)
        number = int(number) if number.is_integer() else number
        return [
            {
                "effect": effect,
                "raw_scope": scope,
                "scope": _scope(scope),
                "value": number,
                "metric": metric,
                "category": category,
            }
            for metric, category in self.mappings.get(effect, [("unmodeled", "")])
        ]


def building_variants(archive: SourceArchive, mappings: EffectMappings) -> dict[str, list[dict]]:
    effects: dict[str, list[dict]] = defaultdict(list)
    for row in archive.table("building_effects_junction"):
        effects[row["campaign_group"]].extend(
            mappings.normalize(row["effect"], row["effect_scope"], row["value"])
        )
    members = {row["id"]: row for row in archive.table("campaign_group_members")}
    conditions: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for field, table, column in (
        ("factions", "factions", "faction"),
        ("subcultures", "subcultures", "subculture"),
        ("campaigns", "campaigns", "campaign"),
    ):
        for row in archive.table(f"campaign_group_member_criteria_{table}"):
            conditions[row["member"]][field].append(row[column])
    result: dict[str, list[dict]] = defaultdict(list)
    for row in archive.table("campaign_group_member_criteria_building_levels"):
        member = members[row["member"]]
        group = member["group"]
        if group in effects:
            result[row["building_level"]].append(
                {
                    "group": group,
                    "priority": int(member["priority"]),
                    "factions": conditions[row["member"]].get("factions", []),
                    "subcultures": conditions[row["member"]].get("subcultures", []),
                    "campaigns": conditions[row["member"]].get("campaigns", []),
                    "effects": effects[group],
                }
            )
    return dict(result)
