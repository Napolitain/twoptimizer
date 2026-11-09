"""Route declared effect scopes without assuming missing campaign borders."""

ECONOMIC = frozenset(
    {"wealth", "wealth_percent", "food", "food_percent", "order", "corruption_percent"}
)


def province_targets(scope, source, provinces, adjacency):
    if scope in {"region", "province"}:
        return (source,)
    if scope == "faction":
        return tuple(provinces)
    if scope == "adjacent_provinces":
        return tuple(sorted({b if a == source else a for a, b in adjacency if source in (a, b)}))
    if scope == "enemy_adjacent_provinces":
        return ()
    raise ValueError(f"Unsupported economic effect scope: {scope}")


def targets(effect, county, regions, provinces, adjacency):
    """Income and food modifiers target counties; order and corruption target commanderies."""
    scope, metric = effect["scope"], effect["metric"]
    source = regions[county]["commandery"]
    commanderies = province_targets(scope, source, provinces, adjacency)
    if metric in {"order", "corruption_percent"}:
        return commanderies
    if scope == "region":
        return (county,)
    return tuple(key for key, region in regions.items() if region["commandery"] in commanderies)
