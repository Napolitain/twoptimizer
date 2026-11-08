"""Independent selected-building replay for jointly owned Rome II provinces."""

from collections import Counter
from fractions import Fraction

from games.tw.rome2.building_constraints import validate_layout
from games.tw.rome2.effects import CATEGORIES, raw_effect
from games.tw.rome2.holding_scopes import recipients


def evaluate(economy, layout, party):
    if set(layout) != set(economy.candidates) or party not in economy.parties:
        raise ValueError("Layout/party coverage differs")
    validate_layout(economy.scenario, layout)
    provinces = {
        key: evaluate_province(economy, key, local, layout, party)
        for key, local in economy.locals.items()
    }
    food = sum(row["food_surplus"] for row in provinces.values())
    if food < 0:
        raise ValueError("Food deficit across joint holdings")
    totals = {
        field: sum(row[field] for row in provinces.values())
        for field in (
            "domestic_tax_income",
            "domestic_net_income",
            "building_maintenance",
            "modified_wealth",
        )
    }
    return {
        **totals,
        "food_surplus": food,
        "public_order": min(row["public_order"] for row in provinces.values()),
        "party_index": party,
        "party_facts": list(economy.parties[party]["facts"]),
        "sites": {site: row for p in provinces.values() for site, row in p["sites"].items()},
        "provinces": provinces,
    }


def evaluate_province(economy, key, local, layout, party):
    validate_layout(local.scenario, {site.id: layout[site.id] for site in local.scenario.sites})
    fixed = local.fixed + local.party_effects[party]
    base, minor, modifiers = Counter(), Counter(), Counter()
    for effect in fixed:
        if effect.kind == "wealth_percent":
            for category in effect.targets:
                modifiers[category] += effect.value
    values = Counter(
        food=local.scenario.external_food
        + sum(
            e.value * (len(local.scenario.sites) if e.kind == "food_per_regions" else 1)
            for e in fixed
            if e.kind in {"food_per_regions", "food_per_provinces"}
        ),
        order=local.scenario.order_offset
        + sum(e.value for e in fixed if e.kind in {"order", "own_culture_order"}),
        tax=local.scenario.tax_points
        - local.effective_corruption
        + sum(e.value for e in fixed if e.kind == "tax_percent"),
    )
    sites = _sites(local, layout)
    for source_site, buildings in layout.items():
        source = economy.owners[source_site]
        for building in buildings:
            for raw in economy.candidates[source_site][building]["effects"]:
                count = recipients(
                    raw["scope"], source, key, len(local.scenario.sites), economy.borders
                )
                effect = raw_effect(raw["id"], raw["value"])
                if count and effect:
                    _effect(
                        effect,
                        source_site,
                        source == key,
                        count,
                        base,
                        minor,
                        modifiers,
                        values,
                        local,
                        sites,
                    )
    if values["order"] < local.scenario.minimum_order or 100 + values["tax"] < 0:
        raise ValueError("Insufficient local public order or negative tax factor")
    minor_percent = sum(e.value for e in fixed if e.kind == "minor_wealth_percent")
    categories = {
        c: {
            "base": base[c],
            "modifier_percent": modifiers[c],
            "minor_base": minor[c],
            "minor_bonus_percent": minor_percent,
            "modified": float(
                Fraction(base[c] * (100 + modifiers[c]) + minor[c] * minor_percent, 100)
            ),
        }
        for c in CATEGORIES
    }
    wealth = sum(
        Fraction(base[c] * (100 + modifiers[c]) + minor[c] * minor_percent, 100) for c in CATEGORIES
    )
    income = wealth * Fraction(100 + values["tax"], 100)
    return {
        "domestic_tax_income": float(income),
        "domestic_net_income": float(income) + values["flat"],
        "building_maintenance": -values["flat"],
        "modified_wealth": float(wealth),
        "tax_modifier_percent_net": values["tax"],
        "effective_corruption_points": local.effective_corruption,
        "food_surplus": values["food"],
        "public_order": values["order"],
        "categories": categories,
        "growth_contribution_unvalued": values["growth"],
        "sites": sites,
    }


def _sites(local, layout):
    sites = {}
    for site in local.scenario.sites:
        keys, roles = local._validate_site_layout(layout, site)
        sites[site.id] = {
            "buildings": sorted(keys),
            "ordinary_slots_used": roles["ordinary"],
            "ordinary_slots_available": site.capacity,
            "food_contribution": 0,
            "order_contribution": 0,
            "growth_contribution_unvalued": 0,
        }
    return sites


def _effect(effect, site, is_source, count, base, minor, modifiers, values, local, sites):
    if effect.kind == "wealth":
        base[effect.targets[0]] += effect.value
        if any(s.id == site and not s.major for s in local.scenario.sites):
            minor[effect.targets[0]] += effect.value
    elif effect.kind == "wealth_percent":
        for category in effect.targets:
            modifiers[category] += effect.value
    else:
        _other_effect(effect, site, is_source, count, values, sites)


def _other_effect(effect, site, is_source, count, values, sites):
    if effect.kind in {"food", "order"}:
        amount = effect.value * (count if effect.kind == "food" else 1)
        values[effect.kind] += amount
        if is_source:
            sites[site][effect.kind + "_contribution"] += amount
    elif effect.kind == "tax_percent":
        values["tax"] += effect.value
    elif effect.kind == "income_flat" and is_source:
        values["flat"] += effect.value
    elif effect.kind == "growth":
        values["growth"] += effect.value
        if is_source:
            sites[site]["growth_contribution_unvalued"] += effect.value


def warm_values(economy, reference):
    layout = {key: row["buildings"] for key, row in reference["sites"].items()}
    economics = economy.evaluate(layout, reference["party_index"])
    if abs(economics["domestic_net_income"] - reference["domestic_net_income"]) > 1e-5:
        raise ValueError("Warm start does not match joint economics")
    values = {name: int(key in layout[site]) for name, (site, key) in economy.decisions.items()}
    values.update(
        {
            name: int(party == reference["party_index"])
            for name, party in economy.party_variables.items()
        }
    )
    for key, row in economics["provinces"].items():
        values.update({key + ":" + name: value for name, value in _auxiliaries(row).items()})
    return values


def _auxiliaries(economics):
    values, total = {}, 0
    for category, row in economics["categories"].items():
        wealth = row["base"] * (100 + row["modifier_percent"])
        extra = row["minor_base"] * row["minor_bonus_percent"]
        values.update(
            {
                "base:" + category: row["base"],
                "rate:" + category: 100 + row["modifier_percent"],
                "wealth_hundredths:" + category: wealth,
                "minor_base:" + category: row["minor_base"],
                "minor_rate:" + category: row["minor_bonus_percent"],
                "minor_wealth_hundredths:" + category: extra,
            }
        )
        total += wealth + extra
    values.update(
        {
            "total_wealth_hundredths": total,
            "tax_factor": 100 + economics["tax_modifier_percent_net"],
            "income_ten_thousandths": total * (100 + economics["tax_modifier_percent_net"]),
        }
    )
    return values
