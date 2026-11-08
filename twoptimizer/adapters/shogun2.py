"""Prepare jointly owned Shogun 2 holdings and adapt their evaluated income."""

from twoptimizer.adapters.model_stats import record_binary, record_cp_result
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
        religion=config.constraints.shogun_religion,
        nanban_contact=config.constraints.nanban_contact,
        required_buildings=config.constraints.required_buildings,
        forbidden_buildings=config.constraints.forbidden_buildings,
    )


def solve_shogun(config: RunConfig, phase: PhaseTimer, session=None) -> EngineResult:
    from games.tw.shogun2.catalog import load_data
    from games.tw.shogun2.model import Economy

    class ObservedEconomy(Economy):
        def compile(self):
            model = super().compile()
            record_binary(
                phase,
                model,
                "Shogun 2 binary income model",
                len(self.decision_names),
                config.algorithm,
            )
            return model

    data, rules = load_data()
    phase("build_model_seconds", "Preparing province model")
    economy = ObservedEconomy(prepare_scenario(config), data, rules)
    phase("solve_and_check_seconds", "Solving and validating")
    raw = economy.optimize(config.algorithm, config.seconds, config.workers)
    record_cp_result(phase, raw["solver"], len(economy.decision_names))
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
