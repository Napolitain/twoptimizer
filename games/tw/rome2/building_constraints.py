"""Optional exact-building requirements, shared by construction and replay."""


def identifiers(values):
    if not isinstance(values, (tuple, list)) or any(
        not isinstance(key, str) or not key for key in values
    ):
        raise ValueError("Building requirements must be lists of building IDs")
    if len(set(values)) != len(values):
        raise ValueError("Building requirements must not contain duplicate IDs")
    return tuple(values)


def validate(scenario, known, candidates):
    requested = set(scenario.required_buildings) | set(scenario.forbidden_buildings)
    unknown = requested - set(known)
    if unknown:
        raise ValueError(f"Unknown building IDs in requirements: {sorted(unknown)}")
    unavailable = set(scenario.required_buildings) - {
        key for rows in candidates.values() for key in rows
    }
    if unavailable:
        raise ValueError(f"Required buildings unavailable in this holding: {sorted(unavailable)}")


def fields(scenario):
    return {
        key: list(getattr(scenario, key))
        for key in ("required_buildings", "forbidden_buildings")
        if getattr(scenario, key)
    }


def install(scenario, choices, solver):
    for key in scenario.required_buildings:
        solver.Add(
            sum(variable for (_, building), variable in choices.items() if building == key) >= 1
        )
    for key in scenario.forbidden_buildings:
        solver.Add(
            sum(variable for (_, building), variable in choices.items() if building == key) == 0
        )


def validate_layout(scenario, layout):
    selected = {key for keys in layout.values() for key in keys}
    missing = set(scenario.required_buildings) - selected
    forbidden = set(scenario.forbidden_buildings) & selected
    if missing or forbidden:
        raise ValueError(
            f"Building requirements violated; missing: {sorted(missing)}, "
            f"forbidden: {sorted(forbidden)}"
        )
