"""Province selection and joint ownership shared by the TUI and worker adapters."""

from dataclasses import replace

from twoptimizer.catalog import choices
from twoptimizer.models import RunConfig

JOINT_GAMES = {"attila", "shogun2"}


def selected_provinces(config: RunConfig) -> tuple[str, ...]:
    return (config.province,) if config.provinces is None else config.provinces


def province_label(config: RunConfig) -> str:
    names = dict((key, label) for label, key in choices(config.game)["provinces"])
    selected = selected_provinces(config)
    if not selected:
        return "No provinces selected"
    label = " + ".join(names[key] for key in selected)
    if config.joint and len(selected) > 1:
        return "Together · " + (label if len(selected) <= 3 else f"{len(selected)} provinces")
    return label


def validate_selection(config: RunConfig) -> tuple[str, ...]:
    if not isinstance(config.joint, bool):
        raise ValueError("Joint mode must be a boolean.")
    selected = selected_provinces(config)
    available = {key for _, key in choices(config.game)["provinces"]}
    if any(key not in available for key in selected):
        raise ValueError("Choose an available province or reference layout.")
    if len(set(selected)) != len(selected):
        raise ValueError("Select each province only once.")
    if config.joint and config.game not in JOINT_GAMES:
        raise ValueError(
            "Joint ownership is available for Attila and Shogun 2; Rome II batches are independent."
        )
    validate_borders(config, selected)
    return selected


def validate_borders(config: RunConfig, selected: tuple[str, ...]) -> None:
    if config.joint and config.game == "attila" and len(selected) > 1 and config.adjacency is None:
        raise ValueError(
            "Set neighboring provinces, or confirm no borders, before running Attila together."
        )
    if config.adjacency is None:
        return
    if not config.joint or config.game != "attila":
        raise ValueError("Neighboring provinces apply to joint Attila runs.")
    seen = set()
    for pair in config.adjacency:
        if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= set(selected):
            raise ValueError("Each border must join two different selected provinces.")
        border = frozenset(pair)
        if border in seen:
            raise ValueError("List each border only once.")
        seen.add(border)


def holding_jobs(config: RunConfig) -> list[RunConfig]:
    selected = selected_provinces(config)
    if not selected:
        return []
    if config.joint:
        return [replace(config, province=selected[0], provinces=selected)]
    return [replace(config, province=key, provinces=None) for key in selected]


def adjacency_mapping(config: RunConfig) -> dict[str, list[str]]:
    mapping = {key: [] for key in selected_provinces(config)}
    for first, second in config.adjacency or ():
        mapping[first].append(second)
        mapping[second].append(first)
    return mapping
