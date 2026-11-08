"""Prepare Rome II requests and adapt independently evaluated engine reports."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

from games.tw.rome2.catalog import load_data
from games.tw.rome2.scenario import Scenario, Site
from games.tw.rome2.world import province_scenario
from twoptimizer.adapters.model_stats import record_cp_result
from twoptimizer.adapters.rome_models import ObservedEconomy, ObservedHoldingEconomy
from twoptimizer.adapters.search import search_observers
from twoptimizer.catalog import read
from twoptimizer.holdings import resolved_borders
from twoptimizer.models import BuildingSelection, EngineResult, RunConfig
from twoptimizer.progress import PhaseTimer
from twoptimizer.rome_session import RomeSession

if TYPE_CHECKING:
    from twoptimizer.session import RunSession


def presets(name: str) -> tuple[Site, ...]:
    coastal = name != "inland"
    return (
        Site("capital", major=True, port=coastal),
        Site("town", port=coastal, resource="grain" if name == "grain" else None),
    )


def prepare_scenario(config: RunConfig) -> Scenario:
    return replace(
        _base_scenario(config),
        required_buildings=config.constraints.required_buildings,
        forbidden_buildings=config.constraints.forbidden_buildings,
        retained_buildings=config.comparison_candidates,
    )


def _base_scenario(config: RunConfig) -> Scenario:
    if config.joint:
        return _joint_scenario(config)
    profile = config.research if config.research != "none" else config.technology_profile
    if config.province in {"coastal", "inland", "grain"}:
        return Scenario(
            config.faction,
            presets(config.province),
            name=config.province,
            all_technologies=config.research != "none",
            technology_profile=profile,
        )
    return province_scenario(
        config.province,
        config.faction,
        world_bonuses=config.world_bonuses,
        all_technologies=config.research != "none",
        technology_profile=profile,
    )


def _joint_scenario(config):
    from games.tw.rome2.holdings import HoldingScenario

    if any(key in {"coastal", "inland", "grain"} for key in config.holdings):
        raise ValueError("Joint Rome II holdings require named campaign provinces")
    world = read("rome2/data/world.json")["regions"]
    owned = {key for key, row in world.items() if row["province"] in config.holdings}
    profile = config.research if config.research != "none" else config.technology_profile
    provinces = tuple(
        replace(
            province_scenario(
                key,
                config.faction,
                owned_regions=owned,
                world_bonuses=config.world_bonuses,
                all_technologies=config.research != "none",
                technology_profile=profile,
            ),
            name=key,
        )
        for key in config.holdings
    )
    return HoldingScenario.from_provinces(provinces, resolved_borders(config))


def request_key(config: RunConfig) -> str:
    """Stable historical resume key, using the scenario's public JSON contract."""
    return json.dumps([prepare_scenario(config).to_dict(), config.algorithm], sort_keys=True)


def solve_rome(
    config: RunConfig, phase: PhaseTimer, session: RunSession | None = None
) -> EngineResult:
    data = load_data()
    phase("build_model_seconds", "Preparing province model")
    scenario = prepare_scenario(config)
    if config.joint:
        from games.tw.rome2.holdings import HoldingScenario

        assert isinstance(scenario, HoldingScenario)
        economy = ObservedHoldingEconomy(scenario, data, phase, config.algorithm)
    else:
        economy = ObservedEconomy(scenario, data, phase, config.algorithm)
    phase("solve_and_check_seconds", "Solving and validating")
    state = RomeSession() if session is None else session.rome
    raw = state.solve(
        economy,
        config,
        **search_observers(
            phase,
            "Rome II CP-SAT",
            lambda: len(economy.decisions) + len(economy.party_variables),
            phases=True,
        ),
    )
    record_cp_result(phase, raw["solver"], len(economy.decisions) + len(economy.party_variables))
    phase("prepare_result_seconds", "Preparing result")
    world = read("rome2/data/world.json")["regions"]
    buildings = [
        BuildingSelection(
            world.get(site, {}).get("name", site.title()), data["buildings"][key]["name"], key
        )
        for site, row in raw.get("sites", {}).items()
        for key in row["buildings"]
    ]
    metrics = {
        key: raw.get(key)
        for key in (
            "food_surplus",
            "public_order",
            "modified_wealth",
            "domestic_tax_income",
            "building_maintenance",
        )
    }
    return EngineResult(raw, raw.get("domestic_net_income"), buildings, metrics)
