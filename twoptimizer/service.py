"""Validated UI requests, adapters to existing engines, and portable exports."""

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

from twoptimizer.catalog import EXACT, NOTES, ROOT, choices, faction_name, read


@dataclass(frozen=True)
class RunConfig:
    game: str = "rome2"
    faction: str = "rom_rome"
    province: str = "coastal"
    algorithm: str = "portfolio"
    seconds: float | None = None
    workers: int | None = None
    research: str = "none"
    fertility: float = 5
    religion: str = "CHRIST_ORTHODOX"
    soil: str = "native"
    town_wealth: float = 0
    tax: float = 30
    world_bonuses: bool = True


def make_jobs(config):
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
    if config.province not in {key: label for label, key in options["provinces"]}:
        raise ValueError("Choose an available province or reference layout.")
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
    return [replace(config, faction=f, algorithm=a) for f in factions for a in algorithms], skipped


def _validate_game_settings(config):
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


def _research_factions(config, factions):
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
                "effects.py",
                "world.py",
                "data/economy_catalog.json",
                "data/world.json",
                "data/world_modifiers.json",
            )
        ]
    elif game == "shogun2":
        paths = [
            ROOT / "shogun2" / name for name in ("model.py", "effects.py", "data/rules.json")
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
            ROOT / "attila/economy.py",
            ROOT / "competition.py",
            ROOT / "sparse.py",
            ROOT / "resources.py",
        ]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def _solve_rome(config, phase):
    buildings, metrics = [], {}
    from games.tw.rome2.benchmark import presets
    from games.tw.rome2.model import Economy, Scenario, load_data
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
                {
                    "region": world.get(site, {}).get("name", site.title()),
                    "building": data["buildings"][key]["name"],
                    "id": key,
                }
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
    return raw, income, buildings, metrics


def _solve_shogun(config, phase):
    buildings, metrics = [], {}
    from games.tw.shogun2.model import Economy, Province, Scenario, load_data

    data, rules = load_data()
    phase("build_model_seconds", "Preparing province model")
    province = Province(
        config.province,
        town_wealth=config.town_wealth,
        base_tax_percent=config.tax,
        farm_multiplier={"native": None, "barren": 1, "very_fertile": 3}[config.soil],
    )
    economy = Economy(
        Scenario(config.faction, (province,), all_arts=config.research == "all"),
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
                {
                    "region": rules["provinces"][key]["name"],
                    "building": data["buildings"][building]["name"],
                    "id": building,
                }
            )
        metrics["public_order"] = row["public_order"]
    metrics["food_surplus"] = raw.get("food_surplus")
    return raw, income, buildings, metrics


def _solve_attila(config, phase):
    buildings, metrics = [], {}
    from games.tw.benchmark import compare, load_attila, snapshot
    from games.tw.models.game_attila import AttilaGame

    parser = load_attila(AttilaGame.Factions(config.faction), AttilaGame.Religion[config.religion])
    province = parser.provinces[config.province]
    phase("build_model_seconds", "Building income model")
    model, build_seconds, economy = snapshot(
        province,
        config.fertility,
        retain_economy=True,
        technologies=set() if config.research == "none" else None,
    )
    assert economy is not None
    phase("solve_and_check_seconds", "Solving and validating")
    result: dict[str, Any] = compare(
        model,
        [config.algorithm],
        config.seconds,
        0,
        128,
        16,
        economy=economy,
        workers=config.workers,
    )["results"][0]
    phase("prepare_result_seconds", "Preparing result")
    raw = {
        **result,
        "build_seconds": build_seconds,
        "omitted_effects": sorted(set(economy.omitted)),
    }
    raw["solver"] = {
        k: result[k]
        for k in ("algorithm", "status", "seconds", "objective", "bound", "timings", "workers")
    }
    raw["model_size"] = {
        "variables": len(model.names),
        "constraints": model.matrix.shape[0],
        "constraint_storage_bytes": model.matrix.nbytes,
    }
    income = result["objective"]
    for key in result.get("selected") or []:
        building = economy.by_id[key]
        buildings.append(
            {
                "region": building.region.print_name,
                "building": building.print_name,
                "id": building.name,
            }
        )
    layout = result.get("layout") or {}
    metrics = {
        "food_surplus": sum(layout.get("province_food", {}).values()) if layout else None,
        "public_order": min(layout.get("public_order", {}).values(), default=None),
    }
    return raw, income, buildings, metrics


def solve_case(config, progress=None):
    timings = {}
    stage, stage_start = None, perf_counter()

    def phase(key=None, label=None):
        nonlocal stage, stage_start
        now = perf_counter()
        if stage is not None:
            timings[stage] = now - stage_start
        stage, stage_start = key, now
        if progress is not None and label is not None:
            progress(label)

    phase("request_seconds", "Validating request")
    jobs, _ = make_jobs(config)
    if len(jobs) != 1:
        raise ValueError("A worker must receive exactly one faction and solver.")
    phase("load_engine_seconds", "Loading engine and game data")
    adapter = {"rome2": _solve_rome, "shogun2": _solve_shogun, "attila": _solve_attila}[config.game]
    raw, income, buildings, metrics = adapter(config, phase)
    solver = raw["solver"]
    bound = solver.get("bound")
    gap = (
        100 * max(0, bound - income) / max(1, abs(bound))
        if income is not None and bound is not None and isfinite(bound)
        else None
    )
    output = {
        "request": asdict(config),
        "faction": faction_name(config.game, config.faction),
        "province": {key: label for label, key in choices(config.game)["provinces"]}[
            config.province
        ],
        "solver": solver,
        "income": income,
        "gap_percent": gap,
        "metrics": metrics,
        "buildings": sorted(buildings, key=lambda b: (b["region"], b["building"])),
        "assumptions": NOTES[config.game],
        "source_files": source_files(config.game),
        "raw": raw,
        "timings": timings,
    }
    phase()
    return output


def export_session(path, results, *, skipped=(), overwrite=False):
    path = Path(path).expanduser()
    if path.suffix.lower() not in {"", ".json"}:
        raise ValueError("Choose a JSON filename; a matching CSV is saved alongside it.")
    path = path.with_suffix(".json")
    csv_path = path.with_suffix(".csv")
    if not results:
        raise ValueError("Run an optimization before exporting.")
    if not overwrite and (path.exists() or csv_path.exists()):
        raise FileExistsError(
            "A report already exists. Choose another filename or enable replacement."
        )
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(),
        "scope": (
            "Independent province cases; no cross-game ranking. OPTIMAL is a "
            "solver proof for the stated model. FEASIBLE keeps an unresolved "
            "bound. Cancelled batches may contain fewer cases than requested."
        ),
        "skipped": list(skipped),
        "cases": results,
    }
    encoded = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded)
    fields = (
        "game",
        "faction",
        "province",
        "research",
        "algorithm",
        "status",
        "income",
        "bound",
        "gap_percent",
        "seconds",
        "fertility",
        "soil",
        "tax",
        "town_wealth",
        "time_limit_seconds",
        "workers",
        "elapsed_seconds",
        "build_seconds",
        "search_seconds",
    )
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in results:
            writer.writerow(
                {
                    **{
                        k: row["request"][k]
                        for k in (
                            "game",
                            "research",
                            "fertility",
                            "soil",
                            "tax",
                            "town_wealth",
                        )
                    },
                    "faction": row["faction"],
                    "province": row["province"],
                    "algorithm": row["solver"]["algorithm"],
                    "status": row["solver"]["status"],
                    "income": row["income"],
                    "bound": row["solver"].get("bound"),
                    "gap_percent": row["gap_percent"],
                    "seconds": row["solver"]["seconds"],
                    "time_limit_seconds": row["request"]["seconds"],
                    "workers": row["solver"].get("workers"),
                    "elapsed_seconds": row.get("timings", {}).get("worker_wall_seconds"),
                    "build_seconds": row.get("timings", {}).get("build_model_seconds"),
                    "search_seconds": row["solver"].get("timings", {}).get("search_seconds"),
                }
            )
    return path, csv_path
