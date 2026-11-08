"""Explicit campaign limits and regional placement for Attila buildings.

These are caller-supplied constraints, not inferred vanilla uniqueness rules.
Several upgrade IDs can share one maximum, including a whole unique chain.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BuildingRule:
    buildings: tuple[str, ...]
    maximum: int | None = None
    regions: tuple[str, ...] | None = None

    def __post_init__(self):
        object.__setattr__(self, "buildings", tuple(self.buildings))
        if self.regions is not None:
            object.__setattr__(self, "regions", tuple(self.regions))


def building_key(building):
    return building.name.removeprefix(building.region.name + "_")


def validate_records(records):
    if not isinstance(records, list):
        raise TypeError("building_rules must be a list")
    for record in records:
        if not isinstance(record, dict) or set(record) - {"buildings", "maximum", "regions"}:
            raise ValueError("Unknown building rule fields")
        _identifiers(record.get("buildings"), "Building rule buildings", nonempty=True)
        if "maximum" not in record and "regions" not in record:
            raise ValueError("Building rules need a maximum or allowed regions")
        if "maximum" in record:
            maximum = record["maximum"]
            if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
                raise ValueError("Building rule maximum must be a nonnegative integer")
        if "regions" in record:
            _identifiers(record["regions"], "Building rule regions")


def _identifiers(value, label, *, nonempty=False):
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or any(not isinstance(key, str) or not key for key in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError(f"{label} must contain distinct identifiers")


def bind_records(records, provinces):
    if not records:
        return
    regions = {r.name for p in provinces for r in p.regions}
    buildings = {building_key(b) for p in provinces for r in p.regions for b in r.buildings}
    context = provinces[0].context
    if context.buildings is not None:
        buildings.update(key for entries in context.buildings.values() for key in entries)
    for record in records:
        if set(record["buildings"]) - buildings:
            raise ValueError("Unknown building IDs in building rule")
        if set(record.get("regions", ())) - regions:
            raise ValueError("Unknown or unselected regions in building rule")


def install_rules(economy, solver):
    for i, rule in enumerate(economy.scenario.building_rules):
        candidates = [b for b in economy.buildings if building_key(b) in rule.buildings]
        if rule.maximum is not None:
            solver.create_constraint(
                f"Building_Rule_{i}_Maximum",
                [b.variable for b in candidates],
                constraint_fn=lambda total, maximum=rule.maximum: total <= maximum,
            )
        if rule.regions is not None:
            solver.create_constraint(
                f"Building_Rule_{i}_Regions",
                [b.variable for b in candidates if b.region.name not in rule.regions],
                constraint_fn=lambda total: total == 0,
            )


def rule_report(economy, selected):
    reports = []
    for rule in economy.scenario.building_rules:
        chosen = [
            b
            for b in economy.buildings
            if b.get_name() in selected and building_key(b) in rule.buildings
        ]
        reports.append(
            {
                "source": "user_supplied_campaign_rule",
                "buildings": list(rule.buildings),
                "maximum": rule.maximum,
                "regions": None if rule.regions is None else list(rule.regions),
                "selected_count": len(chosen),
                "satisfied": (rule.maximum is None or len(chosen) <= rule.maximum)
                and (rule.regions is None or all(b.region.name in rule.regions for b in chosen)),
            }
        )
    return reports
