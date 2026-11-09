"""Province selection and joint ownership shared by the TUI and worker adapters."""

from games.tw.immutable import thaw
from games.tw.maps.catalog import load_campaign_map, province_borders
from twoptimizer.models import RunConfig
from twoptimizer.registry import choices, game_plugin

ROME_REFERENCE_LAYOUTS = {"coastal", "inland", "grain"}


def named_province_choices(game: str) -> tuple[tuple[str, str], ...]:
    """Geographic holdings exclude hypothetical Rome II reference layouts."""
    return tuple(
        (label, key)
        for label, key in choices(game).provinces
        if game != "rome2" or key not in ROME_REFERENCE_LAYOUTS
    )


def selected_provinces(config: RunConfig) -> tuple[str, ...]:
    return config.holdings


def province_label(config: RunConfig) -> str:
    names = dict((key, label) for label, key in choices(config.game).provinces)
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
    available = {key for _, key in choices(config.game).provinces}
    if any(key not in available for key in selected):
        raise ValueError("Choose an available province or reference layout.")
    if len(set(selected)) != len(selected):
        raise ValueError("Select each province only once.")
    if config.joint and not game_plugin(config.game).capabilities.joint_holdings:
        raise ValueError("Joint ownership is unavailable for this game.")
    if config.joint and config.game == "rome2" and set(selected) & ROME_REFERENCE_LAYOUTS:
        raise ValueError("Joint Rome II holdings require named provinces, not reference layouts.")
    validate_borders(config, selected)
    return selected


def validate_borders(config: RunConfig, selected: tuple[str, ...]) -> None:
    if (
        config.joint
        and game_plugin(config.game).capabilities.borders
        and len(selected) > 1
        and config.adjacency is None
        and not has_campaign_borders(config)
        and not unverified_inactive_borders(config)
        and province_borders(config.game, selected) is None
    ):
        game = game_plugin(config.game).label
        raise ValueError(
            f"No complete map covers this holding. Set neighboring provinces, "
            f"or confirm no borders, before running {game} together."
        )
    if config.adjacency is None:
        return
    if not config.joint or not game_plugin(config.game).capabilities.borders:
        raise ValueError(
            "Neighboring provinces apply to joint Attila, Rome II or Three Kingdoms runs."
        )
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
    directed = config.adjacency is None and has_campaign_borders(config)
    for first, second in resolved_borders(config):
        mapping[first].append(second)
        if not directed:
            mapping[second].append(first)
    return mapping


def has_campaign_borders(config: RunConfig) -> bool:
    return (
        config.game == "attila"
        and config.attila.campaign is not None
        and "adjacency" in config.attila.campaign.data
    )


def resolved_borders(config: RunConfig) -> tuple[tuple[str, str], ...]:
    """Explicit overrides take precedence over campaign inputs and bundled maps."""
    if config.adjacency is not None:
        return config.adjacency
    if has_campaign_borders(config):
        assert config.attila.campaign is not None
        mapping = config.attila.campaign.adjacency
        return tuple(sorted((a, b) for a, neighbors in mapping.items() for b in neighbors))
    if (
        not config.joint
        or not game_plugin(config.game).capabilities.borders
        or len(config.holdings) < 2
    ):
        return ()
    borders = province_borders(config.game, config.holdings)
    if borders is None:
        if unverified_inactive_borders(config):
            return ()
        raise ValueError("Set neighboring provinces or supply a complete campaign map")
    return borders


def map_context(config: RunConfig) -> dict:
    """Record effective borders separately from the user's automatic/custom intent."""
    if not config.joint or not game_plugin(config.game).capabilities.borders:
        return {"mode": "not_applied", "borders": [], "directed": False}
    if config.game == "three_kingdoms" and len(config.holdings) < 2:
        return {"mode": "not_applied", "borders": [], "directed": False}
    if config.adjacency is None and unverified_inactive_borders(config):
        return {
            "mode": "unverified_no_effect",
            "borders": [],
            "directed": False,
            "limitations": [
                "Borders are unverified. The historical reference's adjacent economic effects "
                "only reduce corruption, so they do not change income at zero base corruption."
            ],
        }
    if config.adjacency is not None:
        mode = "custom" if config.adjacency else "none"
    elif has_campaign_borders(config):
        mode = "campaign"
    else:
        mode = "map"
    context = {
        "mode": mode,
        "borders": thaw(resolved_borders(config)),
        "directed": mode == "campaign",
    }
    if mode == "map" and (data := load_campaign_map(config.game)) is not None:
        context.update(
            campaign=data["campaign"],
            adjacency_kind=data["coverage"]["adjacency_kind"],
            sources=thaw(data["sources"]),
            limitations=thaw(data.get("limitations", ())),
        )
    return context


def unverified_inactive_borders(config: RunConfig) -> bool:
    """Only this fixed snapshot makes missing neighboring corruption effects inactive."""
    return (
        config.game == "three_kingdoms"
        and config.three_kingdoms.corruption_percent == 0
        and province_borders(config.game, config.holdings) is None
    )
