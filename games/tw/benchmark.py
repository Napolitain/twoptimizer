"""Run competing optimizers against the checked-in Total War: Attila data.

Example: python -m games.tw.benchmark --fertility 0 5 --limit 3 --output results.json
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from math import isfinite
from pathlib import Path
from time import perf_counter

import ortools

from games.tw.competition import ALGORITHMS, BinaryModel, solve
from games.tw.enums import NameType, ProblemState, SolverType
from games.tw.games import Games
from games.tw.models.game_attila import AttilaGame
from games.tw.problem import Problem


def load_attila(faction, religion, legacy=False):
    Games.legacy_effects = legacy
    Games.instance = AttilaGame(faction=faction, religion=religion)
    Games.USE_NAME = NameType.NAME
    parser = Games.instance.get_parser()
    parser.parse_building_effects_junction_tables()
    parser.parse_start_pos_tsv(parser.game_dir)
    Games.buildings = parser.buildings
    return parser


def snapshot(
    province,
    fertility,
    city_level=4,
    building_level=1,
    military=False,
    objective="wealth",
    retain_economy=False,
    technologies=None,
    scenario=None,
):
    """Use the existing engine, including its cross-region sanitation effects."""
    start = perf_counter()
    problem = Problem(
        solver=SolverType.GOOGLE,
        objective=objective,
        technologies=technologies,
        scenario=scenario,
    )
    provinces = province if isinstance(province, list) else [province]
    for selected_province in provinces:
        problem.add_province(selected_province)
    Games.fertility = fertility
    try:
        regions = [r for p in provinces for r in p.regions]
        for region in regions:
            region.buildings = []
            region.add_buildings()
            region.filter_city_level(city_level)
            region.filter_building_level(building_level)
            if not military:
                region.filter_military()
            region.filter_technologies()
            problem.problem.filter_added({b.name: b for b in region.buildings})
        for region in regions:
            region.add_constraints()
        for selected_province in provinces:
            selected_province.add_sanitation_constraint()
            selected_province.add_food_constraint()
            selected_province.add_public_order_constraint()
        problem.state = ProblemState.CONSTRAINTS_ADDED
        problem.add_objective()
        result = (
            BinaryModel.from_solver(problem.problem.solver),
            perf_counter() - start,
        )
        return (*result, problem.economy) if retain_economy else result
    finally:
        for selected_province in provinces:
            selected_province.clean()


def compare(
    model,
    algorithms,
    seconds,
    seed,
    width,
    restarts,
    economy=None,
    objective="wealth",
    workers=1,
):
    results = [
        solve(model, name, seconds, seed, width, restarts, workers=workers)
        for name in algorithms
    ]
    feasible = [
        r.objective for r in results if not r.relaxation and r.objective is not None
    ]
    best = max(feasible, default=None)
    bounds = [r.bound for r in results if r.bound is not None and isfinite(r.bound)]
    upper = min(bounds, default=None)
    if upper is not None and best is not None and upper < best - 1e-5:
        raise RuntimeError(
            "Reported upper bound is below a validated feasible solution"
        )
    rows = []
    for result in results:
        row = asdict(result)
        values = row.pop("values")
        row["selected"] = (
            [
                model.names[i]
                for i, value in enumerate(values)
                if value > 0.5 and not model.names[i].startswith("__")
            ]
            if values is not None and not result.relaxation
            else None
        )
        row["fractional_values"] = (
            dict(zip(model.names, values))
            if values is not None and result.relaxation
            else None
        )
        row["gap_to_best_percent"] = (
            100 * max(0, best - result.objective) / max(1, abs(best))
            if best is not None
            and result.objective is not None
            and not result.relaxation
            else None
        )
        row["gap_to_bound_percent"] = (
            100 * max(0, upper - result.objective) / max(1, abs(upper))
            if upper is not None
            and result.objective is not None
            and not result.relaxation
            else None
        )
        if economy is not None and row["selected"] is not None:
            row["layout"] = economy.evaluate_layout(set(row["selected"]), objective)
            if abs(row["layout"]["objective"] - result.objective) > 1e-5:
                raise RuntimeError(
                    "Layout evaluator disagrees with the compiled objective"
                )
        rows.append(row)
    return {"best_feasible": best, "upper_bound": upper, "results": rows}


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=["cp-sat"])
    cli.add_argument("--fertility", type=float, nargs="+", default=[0, 5])
    cli.add_argument(
        "--province", action="append", help="Province ID or display name; repeatable"
    )
    cli.add_argument(
        "--limit", type=int, help="First N selected provinces (default: all)"
    )
    cli.add_argument(
        "--seconds", type=float, default=5, help="Per-algorithm solve budget per case"
    )
    cli.add_argument("--seed", type=int, default=0)
    cli.add_argument(
        "--scenario", type=Path, help="Campaign inputs, targets and weights as JSON"
    )
    cli.add_argument(
        "--joint", action="store_true", help="Optimize selected provinces together"
    )
    cli.add_argument(
        "--workers", type=int, default=1, help="CP-SAT workers; other solvers unchanged"
    )
    cli.add_argument(
        "--objective", choices=("wealth", "income", "legacy"), default="wealth"
    )
    techs = cli.add_mutually_exclusive_group()
    techs.add_argument(
        "--technology",
        action="append",
        help="Researched technology display name; repeat for multiple",
    )
    techs.add_argument(
        "--no-technologies",
        action="store_true",
        help="No researched technologies (default: all available)",
    )
    cli.add_argument(
        "--region-fertility", action="append", default=[], metavar="REGION=VALUE"
    )
    cli.add_argument("--beam-width", type=int, default=128)
    cli.add_argument("--restarts", type=int, default=16)
    cli.add_argument("--city-level", type=int, choices=range(1, 5), default=4)
    cli.add_argument("--building-level", type=int, choices=range(1, 5), default=1)
    cli.add_argument(
        "--military", action="store_true", help="Include military buildings"
    )
    cli.add_argument(
        "--faction",
        choices=[f.name for f in AttilaGame.Factions],
        default="ATT_FACT_EASTERN_ROMAN_EMPIRE",
    )
    cli.add_argument(
        "--religion",
        choices=[r.name for r in AttilaGame.Religion],
        default="CHRIST_ORTHODOX",
    )
    cli.add_argument(
        "--output", type=Path, help="Write machine-readable results and layouts as JSON"
    )
    args = cli.parse_args(argv)
    if (
        not isfinite(args.seconds)
        or args.seconds <= 0
        or args.beam_width < 1
        or args.restarts < 1
        or args.workers < 1
        or (args.limit is not None and args.limit < 1)
        or any(not isfinite(f) or f < 0 for f in args.fertility)
    ):
        cli.error(
            "Budgets/counts must be positive and fertility must be finite and nonnegative"
        )
    try:
        scenario = json.loads(args.scenario.read_text()) if args.scenario else None
        from games.tw.attila.scenario import Scenario

        Scenario(scenario)
    except (OSError, ValueError, TypeError) as error:
        cli.error(f"Invalid scenario: {error}")
    if args.objective == "legacy" and scenario:
        cli.error("Campaign scenarios require wealth or income mode")
    parser = load_attila(
        AttilaGame.Factions[args.faction],
        AttilaGame.Religion[args.religion],
        legacy=args.objective == "legacy",
    )
    for assignment in args.region_fertility:
        try:
            name, value = assignment.rsplit("=", 1)
            value = float(value)
            if not isfinite(value) or value < 0:
                raise ValueError()
            matches = [
                r for r in parser.regions.values() if name in (r.name, r.print_name)
            ]
            if len(matches) != 1:
                raise ValueError()
            matches[0].fertility = value
        except ValueError:
            cli.error(f"Invalid or unknown region fertility assignment: {assignment}")
    provinces = list(parser.provinces.values())
    if args.province:
        missing = set(args.province) - {
            n for p in provinces for n in (p.name, p.print_name)
        }
        if missing:
            cli.error(f"Unknown provinces: {', '.join(sorted(missing))}")
        provinces = [
            p
            for p in provinces
            if p.name in args.province or p.print_name in args.province
        ]
    if args.limit:
        provinces = provinces[: args.limit]
    digest = hashlib.sha256()
    for path in sorted(
        [*parser.game_dir.glob("*.tsv"), parser.game_dir / "online_buildings.json"]
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    settings = vars(args).copy()
    settings.pop("output")
    settings["scenario"] = scenario
    report = {
        "settings": settings,
        "ortools_version": ortools.__version__,
        "data_sha256": digest.hexdigest(),
        "cases": [],
    }
    print(
        f"{'Province':24} {'Fert':>5} {'Algorithm':12} {'Status':18} {'Objective':>10} {'Seconds':>8} {'Gap/bound':>10}"
    )
    for fertility in args.fertility:
        for group in [provinces] if args.joint else [[p] for p in provinces]:
            province = group[0]
            try:
                model, build_seconds, economy = snapshot(
                    group,
                    fertility,
                    args.city_level,
                    args.building_level,
                    args.military,
                    args.objective,
                    retain_economy=True,
                    scenario=scenario,
                    technologies=set()
                    if args.no_technologies
                    else None
                    if args.technology is None
                    else set(args.technology),
                )
            except (ValueError, TypeError) as error:
                cli.error(str(error))
            case = {
                "province": "joint" if args.joint else province.name,
                "province_name": ", ".join(p.print_name for p in group),
                "fertility": fertility,
                "variables": len(model.names),
                "constraints": len(model.lower),
                "build_seconds": build_seconds,
                "omitted_effects": sorted(set(economy.omitted))
                if economy is not None
                else [],
            }
            case.update(
                compare(
                    model,
                    args.algorithms,
                    args.seconds,
                    args.seed,
                    args.beam_width,
                    args.restarts,
                    economy=economy,
                    objective=args.objective,
                    workers=args.workers,
                )
            )
            report["cases"].append(case)
            for result in case["results"]:
                gdp = (
                    "-" if result["objective"] is None else f"{result['objective']:.2f}"
                )
                gap = (
                    "-"
                    if result["gap_to_bound_percent"] is None
                    else f"{result['gap_to_bound_percent']:.2f}%"
                )
                print(
                    f"{case['province_name'][:24]:24} {fertility:5g} {result['algorithm']:12} "
                    f"{result['status']:18} {gdp:>10} {result['seconds']:8.3f} {gap:>10}"
                )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    main()
