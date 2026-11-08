"""Prepare Rome II requests and adapt independently evaluated engine reports."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from games.tw.rome2.catalog import load_data
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from games.tw.rome2.world import province_scenario
from twoptimizer.catalog import read
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


def request_key(config: RunConfig) -> str:
    """Stable historical resume key, using the scenario's public JSON contract."""
    return json.dumps([prepare_scenario(config).to_dict(), config.algorithm], sort_keys=True)


def solve_rome(
    config: RunConfig, phase: PhaseTimer, session: RunSession | None = None
) -> EngineResult:
    data = load_data()
    phase("build_model_seconds", "Preparing province model")
    economy = Economy(prepare_scenario(config), data)
    phase("solve_and_check_seconds", "Solving and validating")
    state = RomeSession() if session is None else session.rome
    raw = state.solve(economy, config)
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
