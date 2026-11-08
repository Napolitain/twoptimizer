"""Prepare jointly owned Shogun 2 holdings and adapt their evaluated income."""

from twoptimizer.models import BuildingSelection, EngineResult, RunConfig
from twoptimizer.progress import PhaseTimer


def prepare_scenario(config: RunConfig):
    from games.tw.shogun2.scenario import Province, Scenario

    multiplier = {"native": None, "barren": 1, "very_fertile": 3}[config.soil]
    return Scenario(
        config.faction,
        tuple(
            Province(
                key,
                town_wealth=config.town_wealth,
                base_tax_percent=config.tax,
                farm_multiplier=multiplier,
            )
            for key in config.holdings
        ),
        all_arts=config.research == "all",
    )


def solve_shogun(config: RunConfig, phase: PhaseTimer, session=None) -> EngineResult:
    from games.tw.shogun2.catalog import load_data
    from games.tw.shogun2.model import Economy

    data, rules = load_data()
    phase("build_model_seconds", "Preparing province model")
    economy = Economy(prepare_scenario(config), data, rules)
    phase("solve_and_check_seconds", "Solving and validating")
    raw = economy.optimize(config.algorithm, config.seconds, config.workers)
    phase("prepare_result_seconds", "Preparing result")
    buildings = [
        BuildingSelection(rules["provinces"][key]["name"], data["buildings"][b]["name"], b)
        for key, row in raw.get("provinces", {}).items()
        for b in row["buildings"]
    ]
    metrics = {
        "food_surplus": raw.get("food_surplus"),
        "public_order": min(
            (row["public_order"] for row in raw.get("provinces", {}).values()), default=None
        ),
    }
    return EngineResult(raw, raw.get("domestic_tax_income"), buildings, metrics)
