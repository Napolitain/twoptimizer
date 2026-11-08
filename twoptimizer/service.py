"""Validated UI requests, adapters to existing engines, and portable exports."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from math import isfinite

from twoptimizer.catalog import EXACT, NOTES, ROOT, choices, faction_name, read
from twoptimizer.engines import solve_attila, solve_rome, solve_shogun
from twoptimizer.holdings import holding_jobs, province_label, validate_selection
from twoptimizer.models import CaseResult, RunConfig, SolverSummary
from twoptimizer.progress import PhaseTimer


def make_jobs(config: RunConfig) -> tuple[list[RunConfig], list[str]]:
    if config.game not in EXACT:
        raise ValueError("This game does not yet have a complete optimizer.")
    if config.seconds is not None and (not isfinite(config.seconds) or config.seconds <= 0):
        raise ValueError("Time limit must be positive, or disabled to run to completion.")
    if config.workers is not None and (
        isinstance(config.workers, bool)
        or not isinstance(config.workers, int)
        or config.workers < 1
    ):
        raise ValueError("Workers must be a positive whole number.")
    options = choices(config.game)
    validate_selection(config)
    if config.research not in {key for _, key in options["research"]}:
        raise ValueError("Choose an available research profile.")
    factions = (
        [key for _, key in options["factions"]] if config.faction == "all" else [config.faction]
    )
    if any(key not in {key for _, key in options["factions"]} for key in factions):
        raise ValueError("Unknown faction or clan.")
    algorithms = EXACT[config.game] if config.algorithm == "compare" else (config.algorithm,)
    if any(
        a not in EXACT[config.game] and not (config.game == "rome2" and a == "portfolio")
        for a in algorithms
    ):
        raise ValueError("Choose an available solver.")
    skipped = _research_factions(config, factions)
    _validate_game_settings(config)
    return [
        replace(holding, faction=f, algorithm=a)
        for holding in holding_jobs(config)
        for f in factions
        for a in algorithms
    ], skipped


def _validate_game_settings(config: RunConfig) -> None:
    if config.game == "shogun2":
        if config.soil not in {"native", "barren", "very_fertile"}:
            raise ValueError("Choose a listed soil profile.")
        if not 0 <= config.tax <= 100 or not isfinite(config.town_wealth) or config.town_wealth < 0:
            raise ValueError("Tax must be 0-100%; town wealth must be nonnegative.")
    if config.game == "attila":
        from games.tw.models.model_attila import AttilaReligion

        if not isfinite(config.fertility) or config.fertility < 0:
            raise ValueError("Fertility must be finite and nonnegative.")
        if config.religion not in AttilaReligion.__members__:
            raise ValueError("Choose an available religion.")


def _research_factions(config: RunConfig, factions: list[str]) -> list[str]:
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
                    f"{faction_name(config.game, faction)}"
                    ": "
                    f"{config.research}"
                    " research data is incomplete. Choose research bonuses "
                    "disabled or another available profile."
                )
                if config.faction != "all":
                    raise ValueError(message)
                factions.remove(faction)
                skipped.append(message)
    return skipped


def source_files(game):
    if game == "rome2":
        paths = [
            ROOT / "rome2" / name
            for name in (
                "model.py",
                "compiler.py",
                "linear.py",
                "optimization.py",
                "backends.py",
                "scenario.py",
                "placement.py",
                "catalog.py",
                "records.py",
                "provenance.py",
                "effects.py",
                "world.py",
                "data/economy_catalog.json",
                "data/world.json",
                "data/world_modifiers.json",
            )
        ]
    elif game == "shogun2":
        paths = [
            ROOT / "shogun2" / name
            for name in (
                "model.py",
                "scenario.py",
                "catalog.py",
                "records.py",
                "effects.py",
                "data/rules.json",
            )
        ] + [
            ROOT / "multigame/data/shogun2.json",
            ROOT / "competition.py",
            ROOT / "sparse.py",
            ROOT / "resources.py",
        ]
    else:
        paths = [
            *sorted((ROOT / "attila/data").glob("*.tsv")),
            *[
                ROOT / "attila/data" / name
                for name in (
                    "online_buildings.json",
                    "online_factions.json",
                    "online_modifiers.json",
                )
            ],
            *[
                ROOT / name
                for name in (
                    "attila/economy.py",
                    "attila/algebra.py",
                    "attila/compiler.py",
                    "attila/compact.py",
                    "attila/reporting.py",
                    "attila/scenario.py",
                    "attila/scenario_validation.py",
                    "attila/records.py",
                    "catalog.py",
                    "immutable.py",
                    "attila/model.py",
                    "context.py",
                    "comparison.py",
                    "building.py",
                    "entity.py",
                    "region.py",
                    "province.py",
                    "problem.py",
                    "solver_ortools.py",
                    "solver_cpsat.py",
                    "parser/parser.py",
                    "parser/parser_attila.py",
                )
            ],
            ROOT / "competition.py",
            ROOT / "sparse.py",
            ROOT / "resources.py",
        ]
    paths.append(ROOT / "immutable.py")
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def solve_case(config: RunConfig, progress: Callable[[str], None] | None = None) -> CaseResult:
    phase = PhaseTimer(progress)
    phase("request_seconds", "Validating request")
    jobs, _ = make_jobs(config)
    if len(jobs) != 1:
        raise ValueError("A worker must receive exactly one holding, faction and solver.")
    config = jobs[0]
    phase("load_engine_seconds", "Loading engine and game data")
    adapter = {"rome2": solve_rome, "shogun2": solve_shogun, "attila": solve_attila}[config.game]
    result = adapter(config, phase)
    income = result.income
    solver = SolverSummary.from_dict(result.raw["solver"])
    bound = solver.bound
    gap = (
        100 * max(0, bound - income) / max(1, abs(bound))
        if income is not None and bound is not None and isfinite(bound)
        else None
    )
    output = CaseResult(
        request=config,
        faction=faction_name(config.game, config.faction),
        province=province_label(config),
        solver=solver,
        income=income,
        gap_percent=gap,
        metrics=result.metrics,
        buildings=sorted(result.buildings, key=lambda b: (b.region, b.building)),
        assumptions=NOTES[config.game],
        source_files=source_files(config.game),
        raw=result.raw,
        timings=phase.timings,
    )
    phase()
    return output
