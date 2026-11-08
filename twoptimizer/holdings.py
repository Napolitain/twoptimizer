"""Province selection and joint ownership shared by the TUI and worker adapters."""

from twoptimizer.catalog import choices
from twoptimizer.models import RunConfig

JOINT_GAMES = {"attila", "rome2", "shogun2"}
BORDER_GAMES = {"attila", "rome2"}
ROME_REFERENCE_LAYOUTS = {"coastal", "inland", "grain"}


def named_province_choices(game: str) -> tuple[tuple[str, str], ...]:
    """Geographic holdings exclude hypothetical Rome II reference layouts."""
    return tuple(
        (label, key)
        for label, key in choices(game)["provinces"]
        if game != "rome2" or key not in ROME_REFERENCE_LAYOUTS
    )


def selected_provinces(config: RunConfig) -> tuple[str, ...]:
    return config.holdings


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
        raise ValueError("Joint ownership is unavailable for this game.")
    if config.joint and config.game == "rome2" and set(selected) & ROME_REFERENCE_LAYOUTS:
        raise ValueError("Joint Rome II holdings require named provinces, not reference layouts.")
    validate_borders(config, selected)
    return selected


def validate_borders(config: RunConfig, selected: tuple[str, ...]) -> None:
    has_campaign_borders = (
        config.game == "attila"
        and config.attila.campaign is not None
        and "adjacency" in config.attila.campaign.data
    )
    if (
        config.joint
        and config.game in BORDER_GAMES
        and len(selected) > 1
        and config.adjacency is None
        and not has_campaign_borders
    ):
        game = "Attila" if config.game == "attila" else "Rome II"
        raise ValueError(
            f"Set neighboring provinces, or confirm no borders, before running {game} together."
        )
    if config.adjacency is None:
        return
    if not config.joint or config.game not in BORDER_GAMES:
        raise ValueError("Neighboring provinces apply to joint Attila or Rome II runs.")
    seen = set()
    for pair in config.adjacency:
        if len(pair) != 2 or pair[0] == pair[1] or not set(pair) <= set(selected):
            raise ValueError("Each border must join two different selected provinces.")
        border = frozenset(pair)
        if border in seen:
            raise ValueError("List each border only once.")
        seen.add(border)


def adjacency_mapping(config: RunConfig) -> dict[str, list[str]]:
    mapping = {key: [] for key in selected_provinces(config)}
    for first, second in config.adjacency or ():
        mapping[first].append(second)
        mapping[second].append(first)
    return mapping
