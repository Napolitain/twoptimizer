"""Normalize interface inputs and expand typed requests into independent cases."""

import csv
from dataclasses import replace
from math import isfinite

from twoptimizer.catalog import ROOT, faction_name, read
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.errors import ApplicationError
from twoptimizer.holdings import named_province_choices, validate_selection
from twoptimizer.models import AttilaOptions, RunConfig, RunRequest
from twoptimizer.registry import choices, game_plugin, supports_optimization
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions


def default_config(game: str) -> RunConfig:
    if not supports_optimization(game):
        raise ApplicationError("This game does not yet have a complete optimizer.")
    options = choices(game)
    return RunConfig(
        game=game,
        faction=options.default_faction,
        province=options.default_province,
        research=options.default_research,
        algorithm="cp-sat",
        three_kingdoms=ThreeKingdomsOptions(city_level=None)
        if game == "three_kingdoms"
        else ThreeKingdomsOptions(),
    )


def make_jobs(request: RunConfig | RunRequest) -> tuple[list[RunConfig], list[str]]:
    """Resolve IDs/defaults once, with identical validation for CLI and workers."""
    try:
        return _expand(RunRequest(request) if isinstance(request, RunConfig) else request)
    except (ValueError, TypeError) as error:
        if isinstance(error, ApplicationError):
            raise
        raise ApplicationError(str(error)) from error


def _expand(request: RunRequest) -> tuple[list[RunConfig], list[str]]:
    config = _normalize_three_kingdoms(request.config)
    request = replace(request, config=config)
    if not supports_optimization(config.game):
        raise ApplicationError("This game does not yet have a complete optimizer.")
    validate_case(config)
    factions, skipped = _factions(config, request.factions or (config.faction,))
    groups = _holdings(request)
    algorithms = _algorithms(config, request.algorithms or (config.algorithm,))
    joint = config.joint or request.joint
    jobs = []
    for soil in request.soils or (config.soil,):
        for fertility in request.fertilities or (config.fertility,):
            for group in groups:
                for faction in factions:
                    for algorithm in algorithms:
                        job = replace(
                            config,
                            faction=faction,
                            province=group[0],
                            provinces=group if joint else None,
                            joint=joint,
                            algorithm=algorithm,
                            fertility=fertility,
                            soil=soil,
                        )
                        validate_case(job)
                        validate_selection(job)
                        jobs.append(job)
    return jobs, skipped


def _normalize_three_kingdoms(config: RunConfig) -> RunConfig:
    options = config.three_kingdoms
    if config.game != "three_kingdoms" or not isinstance(options, ThreeKingdomsOptions):
        return config
    if options.capital_commandery is None:
        return config
    return replace(
        config,
        three_kingdoms=replace(
            options, capital_commandery=province_id(config.game, options.capital_commandery)
        ),
    )


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _positive_integer(value: int | None, label: str) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 1):
        raise ApplicationError(f"{label} must be a positive whole number.")


def validate_case(config: RunConfig) -> None:
    _validate_flags(config)
    if not isinstance(config.constraints, ConstraintOptions):
        raise ApplicationError("Optional constraints must use ConstraintOptions.")
    config.constraints.validate_game(config.game)
    if config.comparison_candidates and config.game != "rome2":
        raise ApplicationError("Retained comparison candidates require the Rome II model.")
    if config.seconds is not None and (not _finite_number(config.seconds) or config.seconds <= 0):
        raise ApplicationError("Time limit must be positive, or disabled to run to completion.")
    _positive_integer(config.workers, "Workers")
    if config.research not in {key for _, key in choices(config.game).research}:
        raise ApplicationError("Choose an available research profile.")
    if config.game == "attila":
        _validate_attila(config)
    elif config.attila != AttilaOptions():
        raise ApplicationError("Attila options require the Attila game.")
    if config.game == "shogun2":
        _validate_shogun(config)
    if config.game == "rome2" and config.technology_profile not in {"public", "archived"}:
        raise ApplicationError("Choose an available research profile.")
    _validate_three_kingdoms(config)


def _validate_three_kingdoms(config: RunConfig) -> None:
    if not isinstance(config.three_kingdoms, ThreeKingdomsOptions):
        raise ApplicationError("Three Kingdoms options must use ThreeKingdomsOptions.")
    if config.game == "three_kingdoms":
        config.three_kingdoms.validate()
    elif config.three_kingdoms != ThreeKingdomsOptions():
        raise ApplicationError("Three Kingdoms options require the Three Kingdoms game.")


def _validate_flags(config: RunConfig) -> None:
    for value, label in (
        (config.joint, "Joint mode"),
        (config.world_bonuses, "World bonuses"),
        (config.compare_constraints, "Constraint comparison"),
        (config.attila.military, "Military buildings"),
    ):
        if not isinstance(value, bool):
            raise ApplicationError(f"{label} must be a boolean.")


def _validate_attila(config: RunConfig) -> None:
    from games.tw.attila.enums import AttilaReligion

    if not _finite_number(config.fertility) or config.fertility < 0:
        raise ApplicationError("Fertility must be finite and nonnegative.")
    if config.religion not in AttilaReligion.__members__:
        raise ApplicationError("Choose an available religion.")
    options = config.attila
    for value in (options.city_level, options.building_level):
        if isinstance(value, bool) or not isinstance(value, int) or value not in range(1, 5):
            raise ApplicationError("City and building levels must be whole numbers from 1 to 4.")
    if isinstance(options.seed, bool) or not isinstance(options.seed, int):
        raise ApplicationError("Seed must be a whole number.")
    if options.campaign is not None and options.campaign.weights:
        raise ApplicationError(
            "Only income optimization is supported; campaign objective weights are not allowed."
        )
    for assignment in options.region_fertility:
        if not _finite_number(assignment.value) or assignment.value < 0:
            raise ApplicationError("Region fertility must be finite and nonnegative.")


def _validate_shogun(config: RunConfig) -> None:
    if config.soil not in {"native", "barren", "very_fertile"}:
        raise ApplicationError("Choose a listed soil profile.")
    if (
        not _finite_number(config.tax)
        or not 0 <= config.tax <= 100
        or not _finite_number(config.town_wealth)
        or config.town_wealth < 0
    ):
        raise ApplicationError("Tax must be 0-100%; town wealth must be nonnegative.")


def _faction_id(game: str, value: str) -> str:
    if game == "attila":
        from games.tw.attila.enums import AttilaFactions

        if value in AttilaFactions.__members__:
            return AttilaFactions[value].value
        try:
            return AttilaFactions(value).value
        except ValueError:
            pass
    known = {key: key for _, key in choices(game).factions}
    known.update({label: key for label, key in choices(game).factions})
    if value not in known:
        raise ApplicationError("Unknown faction or clan.")
    return known[value]


def _factions(config: RunConfig, selected: tuple[str, ...]) -> tuple[list[str], list[str]]:
    implicit = selected == ("all",)
    factions = (
        sorted(key for _, key in choices(config.game).factions)
        if implicit
        else [_faction_id(config.game, name) for name in selected]
    )
    skipped = []
    if config.game == "rome2" and config.research != "none":
        data = read("rome2/data/economy_catalog.json")
        for faction in list(factions):
            available = (
                data["technology_coverage"][faction]["complete_public_tree"]
                if config.research == "public"
                else faction in data["technologies_archived"]
            )
            if not available:
                message = (
                    f"{faction_name(config.game, faction)}: {config.research} research data is "
                    "incomplete. Choose research bonuses disabled or another available profile."
                )
                if not implicit:
                    raise ApplicationError(message)
                factions.remove(faction)
                skipped.append(message)
    factions, religious_skips = _religious_factions(config, factions, implicit)
    return factions, skipped + religious_skips


def _religious_factions(config, factions, implicit):
    faith = config.constraints.shogun_religion
    if config.game != "shogun2" or faith is None:
        return factions, []
    accepted, skipped = [], []
    for faction in factions:
        if (faction == "ikko_ikki") == (faith == "ikko"):
            accepted.append(faction)
            continue
        message = (
            f"{faction_name(config.game, faction)}: incompatible with {faith} religion; "
            "Ikko religion and the Ikko Ikki clan must be used together."
        )
        if not implicit:
            raise ApplicationError(message)
        skipped.append(message)
    return accepted, skipped


def _algorithms(config: RunConfig, selected: tuple[str, ...]) -> tuple[str, ...]:
    allowed = game_plugin(config.game).algorithms
    algorithms = allowed if selected == ("compare",) else selected
    if any(algorithm not in allowed for algorithm in algorithms):
        raise ApplicationError("Supported solvers are CP-SAT and HiGHS; choose cp-sat or highs.")
    return tuple(algorithms)


def province_id(game: str, value: str) -> str:
    if not isinstance(value, str):
        raise ApplicationError("Choose an available province or reference layout.")
    options = choices(game).provinces
    if game == "rome2":
        from games.tw.rome2.world import normalized

        matches = {
            key
            for label, key in options
            if normalized(value) in (normalized(key), normalized(label))
        }
    else:
        matches = {key for label, key in options if value in (key, label)}
    if len(matches) != 1:
        raise ApplicationError("Choose an available province or reference layout.")
    return matches.pop()


def _all_provinces(game: str) -> tuple[str, ...]:
    if game == "attila":
        with (ROOT / "attila/data/provinces.tsv").open() as stream:
            return tuple(
                row[0]
                for row in csv.reader(stream, delimiter="\t")
                if row[0].startswith("att_prov_")
            )
    return tuple(key for _, key in named_province_choices(game))


def _holdings(request: RunRequest) -> tuple[tuple[str, ...], ...]:
    config = request.config
    selected = request.provinces or config.holdings
    provinces = (
        _all_provinces(config.game)
        if selected == ("all",)
        else tuple(province_id(config.game, value) for value in selected)
    )
    if len(provinces) != len(set(provinces)):
        raise ApplicationError("Select each province only once.")
    _positive_integer(request.limit, "Province limit")
    if config.game == "attila" and request.provinces:
        selected_ids = set(provinces)
        provinces = tuple(key for key in _all_provinces(config.game) if key in selected_ids)
    provinces = provinces[: request.limit]
    validate_selection(replace(config, provinces=provinces, joint=request.joint or config.joint))
    if not provinces:
        return ()
    if request.joint or config.joint:
        return (provinces,)
    return tuple((key,) for key in provinces)
