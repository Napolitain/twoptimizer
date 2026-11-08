"""Building chain identity and legal site placement policy."""

import re


def branch(building):
    return re.sub(r"_\d+(?:_[a-z]+)?$", "", building["id"])


def _primary_placement(site, category, title):
    if site.major:
        return "primary" if category == "Provincial Capital" else None
    resource = re.sub(r"[^a-z]", "", (site.resource or "Minor Settlement").lower())
    resource = {"oliveoil": "olive"}.get(resource, resource)
    actual = re.sub(r"[^a-z]", "", title.lower())
    actual = {"oliveoil": "olive"}.get(actual, actual)
    return "primary" if category == "Minor Settlement" and resource == actual else None


def placement(building, occurrence, site):
    if "allowed_regions" in occurrence and site.id not in occurrence["allowed_regions"]:
        return None
    category, title = occurrence["category"], occurrence["chain_title"]
    if category in {"Provincial Capital", "Minor Settlement"}:
        return _primary_placement(site, category, title)
    if category == "Port":
        return "port" if site.port else None
    if title == "City Centre" and not site.major:
        return None
    if title == "Town Centre" and site.major:
        return None
    barbarian = occurrence["culture"] == "rom_Barbarian"
    if (category in {"Sanitation", "Water", "Tax"} or title == "Tax") and not site.major:
        return None
    if not barbarian and category == "Agricultural" and site.major:
        return None
    if not barbarian and category == "Industrial" and (title == "Minor Settlement") == site.major:
        return None
    if category == "Military" and title == "Siege" and not site.major:
        return None
    return "ordinary"
