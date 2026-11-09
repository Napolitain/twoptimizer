"""Single registry for built-in CLI, TUI and solve-service game integrations."""

from functools import lru_cache
from types import MappingProxyType

from twoptimizer.catalog import (
    attila_choices,
    rome_choices,
    shogun_choices,
    three_kingdoms_choices,
)
from twoptimizer.game_plugin import (
    GameCapabilities,
    GameChoices,
    GameCommand,
    GamePlugin,
    SolveAdapter,
)


def _rome_adapter() -> SolveAdapter:
    from twoptimizer.adapters.rome2 import solve_rome

    return solve_rome


def _attila_adapter() -> SolveAdapter:
    from twoptimizer.adapters.attila import solve_attila

    return solve_attila


def _shogun_adapter() -> SolveAdapter:
    from twoptimizer.adapters.shogun2 import solve_shogun

    return solve_shogun


def _three_kingdoms_adapter() -> SolveAdapter:
    from twoptimizer.adapters.three_kingdoms import solve_three_kingdoms

    return solve_three_kingdoms


_TOTAL_WAR_SOURCES = ("games/tw/immutable.py", "games/tw/maps/catalog.py")
_PLUGINS = (
    GamePlugin(
        identifier="rome2",
        label="Rome II",
        notes=(
            "Static domestic income after modeled maintenance. Food and public order are "
            "enforced. Research bonuses default off; mature buildings remain unlocked. Public "
            "full-research mode excludes seven incomplete trees, including Rome. Named "
            "provinces include the declared community patch-18 regional bonus profile unless "
            "disabled. Joint holdings share food and factionwide bonuses; adjacent effects use "
            "bundled map borders or explicit overrides. Public references are not "
            "installed-patch certification. No external trade, treasury interest or campaign "
            "timeline. Unverified level-5 monuments remain excluded."
        ),
        commands=(GameCommand("rome2", "games.tw.rome2.benchmark", "Rome II comparisons"),),
        load_choices=rome_choices,
        source_patterns=(
            *_TOTAL_WAR_SOURCES,
            "games/tw/rome2/**/*.py",
            "games/tw/rome2/data/*.json",
            "twoptimizer/adapters/rome2.py",
            "twoptimizer/adapters/rome_models.py",
            "twoptimizer/rome_session.py",
        ),
        capabilities=GameCapabilities(joint_holdings=True, borders=True),
        algorithms=("cp-sat", "highs"),
        load_adapter=_rome_adapter,
        session_cache=lambda session: session.rome,
    ),
    GamePlugin(
        identifier="attila",
        label="Attila",
        notes=(
            "Recurring settlement income, including modeled tax and maintenance. Food, "
            "sanitation and public order are enforced. Factions are compared after settlement, "
            "with the selected common religion and explicit fertility. Hordes are excluded. "
            "Technologies default researched; missing building metadata can exclude variants. "
            "No treasury interest or unsupplied trade/tribute/campaign inputs. Public "
            "references still need installed-build validation. Legendary civic capital and "
            "uniqueness restrictions remain unverified; layouts using them can overstate legal "
            "campaign income."
        ),
        commands=(
            GameCommand("attila", "games.tw.attila.benchmark", "Attila province optimization"),
            GameCommand(
                "attila-factions",
                "games.tw.attila.faction_comparison",
                "Attila faction comparisons",
            ),
        ),
        load_choices=attila_choices,
        source_patterns=(
            *_TOTAL_WAR_SOURCES,
            "games/tw/attila/**/*.py",
            "games/tw/attila/data/*.json",
            "games/tw/attila/data/*.tsv",
            "twoptimizer/adapters/attila.py",
            "twoptimizer/attila_session.py",
            "twoptimizer/attila_incumbents.py",
        ),
        capabilities=GameCapabilities(joint_holdings=True, borders=True),
        algorithms=("cp-sat", "highs"),
        load_adapter=_attila_adapter,
        session_cache=lambda session: session.attila,
    ),
    GamePlugin(
        identifier="shogun2",
        label="Shogun 2",
        notes=(
            "Domestic tax income in koku per turn. Food and public order are enforced. Soil "
            "uses the selected province's source profile by default; town wealth is supplied "
            "explicitly. All arts default researched, native clan faith, no Nanban contact. No "
            "external trade, construction timeline or future growth valuation. Public "
            "references still need installed-build validation."
        ),
        commands=(GameCommand("shogun2", "games.tw.shogun2.benchmark", "Shogun 2 comparisons"),),
        load_choices=shogun_choices,
        source_patterns=(
            *_TOTAL_WAR_SOURCES,
            "games/tw/shogun2/**/*.py",
            "games/tw/shogun2/data/*.json",
            "games/tw/multigame/data/shogun2.json",
            "twoptimizer/adapters/shogun2.py",
            "twoptimizer/shogun_session.py",
        ),
        capabilities=GameCapabilities(joint_holdings=True, borders=False),
        algorithms=("cp-sat", "highs"),
        load_adapter=_shogun_adapter,
        session_cache=lambda session: session.shogun,
    ),
    GamePlugin(
        identifier="three_kingdoms",
        label="Three Kingdoms · historical 1.2.0",
        notes=(
            "Historical vanilla 1.2.0 public Assembly Kit reference; not a current-patch or "
            "installed-game validation. Maximize recurring domestic income after modeled "
            "corruption and building maintenance. City levels default optimized from 1 to 10 "
            "and may be fixed. Population and base corruption are explicit common snapshot "
            "inputs, not a historical starting state. Joint holdings share food and supported "
            "cross-commandery effects. No construction timeline, armies, trade agreements or "
            "character optimization. Original leader economic traits default enabled and can be "
            "disabled. See exported coverage for unresolved effects and exclusions."
        ),
        commands=(
            GameCommand(
                "three-kingdoms",
                "twoptimizer.three_kingdoms_cli",
                "Three Kingdoms historical 1.2.0 economy",
                aliases=("three_kingdoms",),
            ),
        ),
        load_choices=three_kingdoms_choices,
        source_patterns=(
            *_TOTAL_WAR_SOURCES,
            "games/tw/three_kingdoms/**/*.py",
            "games/tw/three_kingdoms/data/*.json",
            "twoptimizer/adapters/three_kingdoms.py",
            "twoptimizer/three_kingdoms_options.py",
            "twoptimizer/three_kingdoms_session.py",
            "twoptimizer/three_kingdoms_cli.py",
        ),
        capabilities=GameCapabilities(joint_holdings=True, borders=True),
        algorithms=("cp-sat", "highs"),
        load_adapter=_three_kingdoms_adapter,
        session_cache=lambda session: session.three_kingdoms,
    ),
    GamePlugin(
        identifier="hoi4",
        label="Hearts of Iron IV · reference data",
        notes=(
            "Inspect HoI4 data opens public source facts for eight major countries, with "
            "literal state declarations, source hashes and unresolved coverage. The source "
            "patch is unverified. Hourly planning is under development; no validated starting "
            "scenario or gameplay optimizer is available yet."
        ),
        commands=(
            GameCommand(
                "hoi4",
                "games.hoi4.cli",
                "HoI4 data and hourly planning input review",
                examples=(
                    ("hoi4 data", "HoI4 public reference data"),
                    ("hoi4 plan-check", "Review hourly planning input structure"),
                ),
            ),
        ),
        load_choices=GameChoices,
        source_patterns=("games/hoi4/**/*.py", "twoptimizer/hoi4*.py"),
        capabilities=GameCapabilities(reference_inspector=True),
    ),
)
_PLUGINS_BY_ID = MappingProxyType({plugin.identifier: plugin for plugin in _PLUGINS})
_COMMANDS = MappingProxyType(
    {
        name: command
        for plugin in _PLUGINS
        for command in plugin.commands
        for name in (command.name, *command.aliases)
    }
)


def game_plugins() -> tuple[GamePlugin, ...]:
    return _PLUGINS


def game_plugin(identifier: str) -> GamePlugin:
    try:
        return _PLUGINS_BY_ID[identifier]
    except KeyError:
        raise ValueError(f"Unknown game: {identifier}") from None


def supports_optimization(identifier: str) -> bool:
    plugin = _PLUGINS_BY_ID.get(identifier)
    return plugin is not None and plugin.optimizable


@lru_cache
def choices(identifier: str) -> GameChoices:
    return game_plugin(identifier).load_choices()


def solve_adapter(identifier: str) -> SolveAdapter:
    loader = game_plugin(identifier).load_adapter
    if loader is None:
        raise ValueError("This game does not yet have a complete optimizer.")
    return loader()


def command_named(name: str) -> GameCommand | None:
    return _COMMANDS.get(name)


def command_help() -> tuple[tuple[str, str], ...]:
    return tuple(
        example
        for plugin in _PLUGINS
        for command in plugin.commands
        for example in command.examples or ((command.name, command.description),)
    )
