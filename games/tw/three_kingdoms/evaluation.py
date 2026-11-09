"""Validate selected layouts and recompute their economics without solver auxiliaries."""

from collections import Counter
from fractions import Fraction

from games.tw.three_kingdoms.scopes import ECONOMIC, targets


def validate_layout(economy, layout):
    if set(layout) != set(economy.regions):
        raise ValueError("Layout must cover exactly the selected counties")
    selected, unique, resources = set(), Counter(), set(economy.scenario.external_resources)
    for county, keys in layout.items():
        if len(keys) != len(set(keys)) or set(keys) - economy.candidates[county].keys():
            raise ValueError("Duplicate or unavailable building")
        buildings = [economy.candidates[county][key] for key in keys]
        _validate_slots(economy, county, buildings)
        for building in buildings:
            selected.add(building["id"])
            resources.update(building["provided_resources"])
            if building["faction_unique"]:
                unique[building["id"]] += 1
    if any(count > 1 for count in unique.values()):
        raise ValueError("Faction-unique building duplicated")
    if set(economy.scenario.required_buildings) - selected:
        raise ValueError("Required building missing")
    if set(economy.scenario.forbidden_buildings) & selected:
        raise ValueError("Forbidden building selected")
    for key in selected:
        _validate_resources(economy.data["buildings"][key], resources)


def _validate_slots(economy, county, buildings):
    roles = Counter(economy.role(county, b) for b in buildings)
    groups = Counter(b["superchain"] for b in buildings)
    if roles["primary"] != 1 or any(count > 1 for count in groups.values()):
        raise ValueError("Invalid primary building or building-chain occupancy")
    has_port = any(economy.role(county, b) == "port" for b in economy.candidates[county].values())
    if roles["port"] != int(has_port):
        raise ValueError("Missing or duplicate dedicated harbour")
    province = economy.provinces[economy.regions[county]["commandery"]]
    slots = economy.data["rules"]["city_levels"][str(province.city_level)]["slots"]
    if roles["district"] + roles["port"] > slots:
        raise ValueError("City has too few building slots")


def _validate_resources(building, available):
    requirement = building["required_resources"]
    needed = set(requirement["resources"])
    if not needed:
        return
    valid = bool(needed & available) if requirement["operator"] == "OR" else needed <= available
    if not valid:
        raise ValueError(f"Required resource unavailable for {building['id']}")


def _effects(economy, layout):
    totals = Counter()
    for county, keys in layout.items():
        for key in keys:
            for effect in economy.effects[(county, key)]:
                _add_effect(economy, totals, effect, county)
    source = next(iter(economy.regions))
    for effect in economy.fixed_effects():
        _add_effect(economy, totals, effect, source)
    for province in economy.scenario.commanderies:
        population = economy.population_effects(province)
        totals[("order", province.id, "")] += population["public_order"] + province.order_offset
        for county, region in economy.regions.items():
            if region["commandery"] == province.id:
                totals[("wealth_percent", county, "peasantry")] += population["peasantry_percent"]
    return totals


def _add_effect(economy, totals, effect, county):
    if effect["metric"] not in ECONOMIC:
        return
    for place in targets(
        effect, county, economy.regions, economy.provinces, economy.scenario.adjacency or ()
    ):
        totals[(effect["metric"], place, effect["category"])] += effect["value"]


def _county_totals(economy, county, keys, totals, retention):
    categories, food = {}, Fraction(0)
    for metric, place, category in list(totals):
        if place != county or metric not in {"wealth", "food"}:
            continue
        base = totals[(metric, county, category)]
        rate = totals[(metric + "_percent", county, category)]
        if rate < -100:
            raise ValueError("Negative economic multiplier")
        value = Fraction(base * (100 + rate), 100)
        if metric == "food":
            food += value
        else:
            categories[category] = {"base": base, "modifier_percent": rate, "income": float(value)}
    wealth = sum(
        (
            Fraction(row["base"] * (100 + row["modifier_percent"]), 100)
            for row in categories.values()
        ),
        Fraction(0),
    )
    upkeep = sum(economy.candidates[county][key]["upkeep"] for key in keys)
    return (
        {
            "name": economy.regions[county]["battle_name"],
            "buildings": sorted(keys),
            "categories": categories,
            "gross_income": float(wealth * retention),
            "building_upkeep": upkeep,
            "income": float(wealth * retention - upkeep),
            "food_surplus": float(food),
        },
        wealth * retention - upkeep,
        food,
    )


def _province(economy, province, layout, totals):
    order = totals[("order", province.id, "")]
    if order < province.minimum_order:
        raise ValueError("Insufficient public order")
    corruption = min(
        Fraction(100),
        max(
            Fraction(0),
            Fraction(
                province.corruption_percent
                * (100 + totals[("corruption_percent", province.id, "")]),
                100,
            ),
        ),
    )
    retention = 1 - corruption / 100
    counties, income, food = {}, Fraction(0), Fraction(0)
    placements, capacity = [], 0
    for county, region in economy.regions.items():
        if region["commandery"] != province.id:
            continue
        row, value, balance = _county_totals(economy, county, layout[county], totals, retention)
        counties[county] = row
        income += value
        food += balance
        placements.extend({"county": county, "building": key} for key in sorted(layout[county]))
        capacity += sum(
            e["value"]
            for key in layout[county]
            for e in economy.effects[(county, key)]
            if e["metric"] == "population_capacity"
        )
    capacity *= economy.data["rules"]["population_unit"]
    if province.population > capacity:
        raise ValueError("Population exceeds settlement capacity")
    return (
        {
            "name": economy.data["commanderies"][province.id]["name"],
            "income": float(income),
            "food_surplus": float(food),
            "public_order": order,
            "population": province.population,
            "population_capacity": capacity,
            "base_corruption_percent": province.corruption_percent,
            "effective_corruption_percent": float(corruption),
            "buildings": [p["building"] for p in placements],
            "placements": placements,
            "counties": counties,
        },
        income,
        food,
    )


def evaluate(economy, layout):
    validate_layout(economy, layout)
    totals = _effects(economy, layout)
    rows, income, food = {}, Fraction(0), Fraction(economy.scenario.external_food)
    for province in economy.scenario.commanderies:
        row, value, balance = _province(economy, province, layout, totals)
        rows[province.id] = row
        income += value
        food += balance
    if food < 0:
        raise ValueError("Faction-wide food deficit")
    return {"domestic_income": float(income), "food_surplus": float(food), "commanderies": rows}
