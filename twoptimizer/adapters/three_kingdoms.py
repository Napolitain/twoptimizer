"""Prepare historical Three Kingdoms snapshots and adapt validated engine reports."""

from twoptimizer.adapters.model_stats import record_cp_result
from twoptimizer.adapters.search import search_observers
from twoptimizer.models import BuildingSelection, EngineResult, RunConfig
from twoptimizer.progress import ModelStats, PhaseTimer


def prepare_scenario(config: RunConfig):
    from games.tw.three_kingdoms.scenario import Commandery, Scenario

    options = config.three_kingdoms.to_dict()
    food = options.pop("external_food")
    capital = options.pop("capital_commandery")
    resources = tuple(options.pop("external_resources"))
    leader = options.pop("include_leader_effects")
    return Scenario(
        config.faction,
        tuple(Commandery(key, **options) for key in config.holdings),
        all_reforms=config.research == "all",
        external_food=food,
        capital_commandery=capital,
        external_resources=resources,
        include_leader_effects=leader,
        adjacency=config.adjacency if config.joint and len(config.holdings) > 1 else (),
        required_buildings=config.constraints.required_buildings,
        forbidden_buildings=config.constraints.forbidden_buildings,
    )


def solve_three_kingdoms(config: RunConfig, phase: PhaseTimer, session=None) -> EngineResult:
    from games.tw.three_kingdoms.catalog import load_data
    from games.tw.three_kingdoms.model import Economy

    class ObservedEconomy(Economy):
        def compile(self):
            model = super().compile()
            phase.record_model(
                ModelStats(
                    "HiGHS solver input"
                    if config.algorithm == "highs"
                    else "Three Kingdoms linearized income model",
                    len(model.variable),
                    len(model.constraint),
                    formulation="linearized_income",
                    stage="solver" if config.algorithm == "highs" else "reference",
                    decision_variables=len(self.decisions),
                    nonzeros=sum(len(row.var_index) for row in model.constraint),
                )
            )
            return model

    data = load_data()
    phase("build_model_seconds", "Preparing historical Three Kingdoms snapshot")
    economy = ObservedEconomy(prepare_scenario(config))
    phase("solve_and_check_seconds", "Solving and validating")
    raw = economy.optimize(
        config.algorithm,
        config.seconds,
        config.workers,
        **_observers(config, phase, economy),
    )
    record_cp_result(phase, raw["solver"], len(economy.decisions))
    phase("prepare_result_seconds", "Preparing result")
    buildings = _buildings(raw, data)
    metrics = {
        "food_surplus": raw.get("food_surplus"),
        "public_order": min(
            (row["public_order"] for row in raw.get("commanderies", {}).values()), default=None
        ),
    }
    return EngineResult(raw, raw.get("domestic_income"), buildings, metrics)


def _observers(config: RunConfig, phase: PhaseTimer, economy) -> dict:
    if config.algorithm == "cp-sat":
        return search_observers(phase, "Three Kingdoms CP-SAT", lambda: len(economy.decisions))
    return {} if phase.cancellation is None else {"cancellation": phase.cancellation}


def _buildings(raw, data):
    return [
        BuildingSelection(
            data["regions"][placement["county"]]["battle_name"],
            _building_name(data["buildings"][placement["building"]]),
            placement["building"],
        )
        for row in raw.get("commanderies", {}).values()
        for placement in row["placements"]
    ]


def _building_name(building):
    name = building["name"]
    return f"{name} · city level {building['level']}" if building["kind"] == "city" else name
