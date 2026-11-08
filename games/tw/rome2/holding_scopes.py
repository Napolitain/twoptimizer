"""Recipients of Rome II building effects inside explicitly owned holdings."""

from games.tw.rome2.model import GLOBAL_SCOPES, LOCAL_SCOPES

ADJACENT_SCOPES = {
    "in_all_your_regions_in_adjacent_provinces",
    "in_all_your_provinces_adjacent",
    "in_adjacent_provinces",
}
REGION_SCOPES = {
    "regions_in_this_province",
    "in_all_your_regions",
    "in_all_your_regions_in_adjacent_provinces",
}


def recipients(scope, source, target, regions, borders):
    """Count owned recipients; borders are undirected and never guessed."""
    if scope in GLOBAL_SCOPES:
        applies = True
    elif scope in LOCAL_SCOPES:
        applies = source == target
    elif scope in ADJACENT_SCOPES:
        applies = frozenset((source, target)) in borders
    else:
        applies = False
    return (regions if scope in REGION_SCOPES else 1) if applies else 0


def validate_economic_scope(raw):
    """Reject raw combinations that province aggregates cannot represent exactly."""
    from games.tw.rome2.effects import raw_effect

    effect = raw_effect(raw["id"], raw["value"])
    if effect is None:
        return
    province_scopes = {"this_province", "regions_in_this_province"}
    accepted = {
        "wealth": {"this_building", "this_region"},
        "wealth_percent": province_scopes | GLOBAL_SCOPES | ADJACENT_SCOPES,
        "food": LOCAL_SCOPES | GLOBAL_SCOPES | ADJACENT_SCOPES,
        "order": {"this_province", "in_all_your_provinces", "this_faction"},
        "tax_percent": {"this_province", "in_all_your_provinces", "this_faction"},
        "income_flat": {"this_building", "this_region", "this_province", "this_faction"},
    }
    if effect.kind in accepted and raw["scope"] not in accepted[effect.kind]:
        raise ValueError(
            f"Joint Rome II cannot represent {effect.kind} with scope {raw['scope']!r}: "
            f"{raw['id']} requires additional recipient rules"
        )
