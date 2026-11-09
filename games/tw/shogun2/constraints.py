"""Optional exact-building requirements across a Shogun 2 holding."""


def normalize_ids(value, label):
    if not isinstance(value, (tuple, list)) or any(
        not isinstance(key, str) or not key for key in value
    ):
        raise ValueError(f"{label} must contain building IDs")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must contain distinct building IDs")
    return tuple(value)


def validate_candidates(scenario, catalog, candidates):
    chosen = set(scenario.required_buildings) | set(scenario.forbidden_buildings)
    unknown = chosen - catalog.buildings.keys()
    if unknown:
        raise ValueError(f"Unknown building IDs: {', '.join(sorted(unknown))}")
    available = {key for choices in candidates.values() for key in choices}
    missing = set(scenario.required_buildings) - available
    if missing:
        raise ValueError(
            "Required buildings are unavailable for this holding, religion or research: "
            + ", ".join(sorted(missing))
        )


def install_constraints(scenario, variables, solver):
    for key in scenario.required_buildings:
        solver.Add(sum(v for (_, building), v in variables.items() if building == key) >= 1)
    for key in scenario.forbidden_buildings:
        solver.Add(sum(v for (_, building), v in variables.items() if building == key) == 0)


def validate_layout(scenario, layout):
    selected = {key for choices in layout.values() for key in choices}
    missing = set(scenario.required_buildings) - selected
    forbidden = set(scenario.forbidden_buildings) & selected
    if missing:
        raise ValueError(f"Required buildings are missing: {', '.join(sorted(missing))}")
    if forbidden:
        raise ValueError(f"Forbidden buildings selected: {', '.join(sorted(forbidden))}")
