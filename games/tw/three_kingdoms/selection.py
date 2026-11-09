"""Exact-choice implications used to bound expressions without relaxing the model."""

from collections import Counter, defaultdict


class SelectionBounds:
    """Bound a linear sum using mandatory roles, exclusive chains and available slots."""

    def __init__(self, economy, choices):
        self.membership = {}
        self.sizes = Counter()
        ports = set()
        for (county, key), variable in choices.items():
            building = economy.candidates[county][key]
            role = economy.role(county, building)
            chain = building["superchain"] if role == "district" else role
            group = (county, role, chain)
            self.membership[variable.name()] = group
            self.sizes[group] += 1
            if role == "port":
                ports.add(county)
        self.capacities = {
            county: max(0, _city_slots(economy, county) - int(county in ports))
            for county in economy.candidates
        }

    def bounds(self, terms):
        """Return safe extrema; duplicate contributions to one choice add first."""
        coefficients = Counter()
        for amount, name in terms:
            coefficients[name] += amount
        groups = defaultdict(list)
        for name, amount in coefficients.items():
            groups[self.membership[name]].append(amount)
        lower, upper = 0, 0
        districts = defaultdict(list)
        for group, amounts in groups.items():
            county, role, _ = group
            if role == "district" or len(amounts) < self.sizes[group]:
                amounts.append(0)
            extrema = min(amounts), max(amounts)
            if role == "district":
                districts[county].append(extrema)
            else:
                lower += extrema[0]
                upper += extrema[1]
        for county, values in districts.items():
            slots = self.capacities[county]
            lower += sum(sorted(low for low, _ in values)[:slots])
            upper += sum(sorted((high for _, high in values), reverse=True)[:slots])
        return lower, upper


def _city_slots(economy, county):
    province = economy.provinces[economy.regions[county]["commandery"]]
    rules = economy.data["rules"]["city_levels"]
    if province.city_level is not None:
        return rules[str(province.city_level)]["slots"]
    capital = economy.data["commanderies"][province.id]["capital"]
    return max(
        rules[str(building["level"])]["slots"]
        for building in economy.candidates[capital].values()
        if building["kind"] == "city"
    )


def guaranteed_resources(economy):
    """Resources supplied by every alternative of a required settlement or port."""
    guaranteed = set(economy.scenario.external_resources)
    for county, buildings in economy.candidates.items():
        roles = defaultdict(list)
        for building in buildings.values():
            role = economy.role(county, building)
            if role in {"primary", "port"}:
                roles[role].append(set(building["provided_resources"]))
        for alternatives in roles.values():
            guaranteed.update(set.intersection(*alternatives))
    return guaranteed
