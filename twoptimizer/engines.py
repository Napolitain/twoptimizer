"""Adapt game-specific outputs to the typed application result contract."""

from typing import Any

from twoptimizer.catalog import read
from twoptimizer.holdings import adjacency_mapping, selected_provinces
from twoptimizer.models import BuildingSelection, EngineResult, RunConfig
from twoptimizer.progress import PhaseTimer


def solve_rome(config: RunConfig, phase: PhaseTimer) -> EngineResult:
    buildings, metrics = [], {}
    from games.tw.rome2.benchmark import presets
    from games.tw.rome2.catalog import load_data
    from games.tw.rome2.model import Economy
    from games.tw.rome2.scenario import Scenario
    from games.tw.rome2.world import province_scenario

    data = load_data()
    phase("build_model_seconds", "Preparing province model")
    scenario = (
        Scenario(
            config.faction,
            presets(config.province),
            name=config.province,
            all_technologies=config.research != "none",
            technology_profile="archived" if config.research == "archived" else "public",
        )
        if config.province in {"coastal", "inland", "grain"}
        else province_scenario(
            config.province,
            config.faction,
            world_bonuses=config.world_bonuses,
            all_technologies=config.research != "none",
            technology_profile="archived" if config.research == "archived" else "public",
        )
    )
    economy = Economy(scenario, data)
    phase("solve_and_check_seconds", "Solving and validating")
    raw = economy.optimize(config.algorithm, config.seconds, config.workers)
    phase("prepare_result_seconds", "Preparing result")
    income = raw.get("domestic_net_income")
    world = read("rome2/data/world.json")["regions"]
    for site, row in raw.get("sites", {}).items():
        for key in row["buildings"]:
            buildings.append(
                BuildingSelection(
                    world.get(site, {}).get("name", site.title()),
                    data["buildings"][key]["name"],
                    key,
                )
            )
    metrics = {
        k: raw.get(k)
        for k in (
            "food_surplus",
            "public_order",
            "modified_wealth",
            "domestic_tax_income",
            "building_maintenance",
        )
    }
    return EngineResult(raw, income, buildings, metrics)


def solve_shogun(config: RunConfig, phase: PhaseTimer) -> EngineResult:
    buildings, metrics = [], {}
    from games.tw.shogun2.catalog import load_data
    from games.tw.shogun2.model import Economy
    from games.tw.shogun2.scenario import Province, Scenario

    data, rules = load_data()
    phase("build_model_seconds", "Preparing province model")
    provinces = tuple(
        Province(
            key,
            town_wealth=config.town_wealth,
            base_tax_percent=config.tax,
            farm_multiplier={"native": None, "barren": 1, "very_fertile": 3}[config.soil],
        )
        for key in selected_provinces(config)
    )
    economy = Economy(
        Scenario(config.faction, provinces, all_arts=config.research == "all"),
        data,
        rules,
    )
    phase("solve_and_check_seconds", "Solving and validating")
    raw = economy.optimize(config.algorithm, config.seconds, config.workers)
    phase("prepare_result_seconds", "Preparing result")
    income = raw.get("domestic_tax_income")
    for key, row in raw.get("provinces", {}).items():
        for building in row["buildings"]:
            buildings.append(
                BuildingSelection(
                    rules["provinces"][key]["name"], data["buildings"][building]["name"], building
                )
            )
    metrics["public_order"] = min(
        (row["public_order"] for row in raw.get("provinces", {}).values()), default=None
    )
    metrics["food_surplus"] = raw.get("food_surplus")
    return EngineResult(raw, income, buildings, metrics)


def solve_attila(config: RunConfig, phase: PhaseTimer) -> EngineResult:
    buildings, metrics = [], {}
    from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
    from games.tw.comparison import ComparisonOptions, compare_model
    from games.tw.immutable import thaw
    from games.tw.models.game_attila import AttilaGame

    parser = load_attila(AttilaGame.Factions(config.faction), AttilaGame.Religion[config.religion])
    provinces = [parser.provinces[key] for key in selected_provinces(config)]
    phase("build_model_seconds", "Building income model")
    snapshot = compile_scenario(
        provinces,
        SnapshotOptions(
            fertility=config.fertility,
            technologies=frozenset() if config.research == "none" else None,
            scenario={"adjacency": adjacency_mapping(config)} if config.joint else None,
        ),
    )
    model, build_seconds, economy = snapshot.model, snapshot.build_seconds, snapshot.economy
    assert economy is not None
    phase("solve_and_check_seconds", "Solving and validating")
    result: dict[str, Any] = compare_model(
        model,
        ComparisonOptions(
            algorithms=(config.algorithm,),
            seconds=config.seconds,
            workers=config.workers,
        ),
        economy,
    )["results"][0]
    phase("prepare_result_seconds", "Preparing result")
    raw = {
        **result,
        "build_seconds": build_seconds,
        "omitted_effects": sorted(set(economy.omitted)),
        "adjacency": thaw(economy.adjacency),
    }
    raw["solver"] = {
        k: result[k]
        for k in (
            "algorithm",
            "status",
            "seconds",
            "objective",
            "bound",
            "timings",
            "workers",
            "model_stats",
        )
    }
    raw["model_size"] = {
        "variables": len(model.names),
        "constraints": model.matrix.shape[0],
        "constraint_storage_bytes": model.matrix.nbytes,
        "cp_sat": result.get("model_stats", {}),
    }
    income = result["objective"]
    for key in result.get("selected") or []:
        building = economy.by_id[key]
        buildings.append(
            BuildingSelection(building.region.print_name, building.print_name, building.name)
        )
    layout = result.get("layout") or {}
    metrics = {
        "food_surplus": sum(layout.get("province_food", {}).values()) if layout else None,
        "public_order": min(layout.get("public_order", {}).values(), default=None),
    }
    return EngineResult(raw, income, buildings, metrics)
