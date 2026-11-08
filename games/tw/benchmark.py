"""Run competing optimizers against the checked-in Total War: Attila data.

Example: python -m games.tw.benchmark --fertility 0 5 --limit 3 --output results.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Any

import ortools

from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.comparison import ComparisonOptions, compare_model
from games.tw.competition import ALGORITHMS
from games.tw.models.game_attila import AttilaGame


def _apply_region_fertility(args, parser, cli):
    for assignment in args.region_fertility:
        try:
            name, value = assignment.rsplit("=", 1)
            value = float(value)
            if not isfinite(value) or value < 0:
                raise ValueError()
            matches = [r for r in parser.regions.values() if name in (r.name, r.print_name)]
            if len(matches) != 1:
                raise ValueError()
            matches[0].fertility = value
        except ValueError:
            cli.error(f"Invalid or unknown region fertility assignment: {assignment}")


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=["cp-sat"])
    cli.add_argument("--fertility", type=float, nargs="+", default=[0, 5])
    cli.add_argument("--province", action="append", help="Province ID or display name; repeatable")
    cli.add_argument("--limit", type=int, help="First N selected provinces (default: all)")
    cli.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Optional time limit per algorithm/case; default runs to completion",
    )
    cli.add_argument("--seed", type=int, default=0)
    cli.add_argument("--scenario", type=Path, help="Campaign inputs, targets and weights as JSON")
    cli.add_argument("--joint", action="store_true", help="Optimize selected provinces together")
    cli.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional CPU worker override; default automatic",
    )
    cli.add_argument(
        "--objective",
        choices=("wealth", "income", "legacy"),
        default="income",
        help="Maximize recurring income (default), gross building wealth, or legacy GDP",
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
    cli.add_argument("--region-fertility", action="append", default=[], metavar="REGION=VALUE")
    cli.add_argument("--beam-width", type=int, default=128)
    cli.add_argument("--restarts", type=int, default=16)
    cli.add_argument("--city-level", type=int, choices=range(1, 5), default=4)
    cli.add_argument("--building-level", type=int, choices=range(1, 5), default=1)
    cli.add_argument("--military", action="store_true", help="Include military buildings")
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
        (args.seconds is not None and (not isfinite(args.seconds) or args.seconds <= 0))
        or args.beam_width < 1
        or args.restarts < 1
        or (args.workers is not None and args.workers < 1)
        or (args.limit is not None and args.limit < 1)
        or any(not isfinite(f) or f < 0 for f in args.fertility)
    ):
        cli.error("Budgets/counts must be positive and fertility must be finite and nonnegative")
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
    _apply_region_fertility(args, parser, cli)
    provinces = list(parser.provinces.values())
    provinces = _select_provinces(args, provinces, cli)
    digest = hashlib.sha256()
    for path in sorted(
        [
            *parser.game_dir.glob("*.tsv"),
            parser.game_dir / "online_buildings.json",
            parser.game_dir / "online_factions.json",
            parser.game_dir / "online_modifiers.json",
        ]
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    settings = vars(args).copy()
    settings.pop("output")
    settings["scenario"] = scenario
    report: dict[str, Any] = {
        "settings": settings,
        "ortools_version": ortools.__version__,
        "data_sha256": digest.hexdigest(),
        "cases": [],
    }
    print(
        f"{'Province':24}"
        " "
        f"{'Fert':>5}"
        " "
        f"{'Algorithm':12}"
        " "
        f"{'Status':18}"
        " "
        f"{'Objective':>10}"
        " "
        f"{'Seconds':>8}"
        " "
        f"{'Gap/bound':>10}"
    )
    for fertility in args.fertility:
        for group in [provinces] if args.joint else [[p] for p in provinces]:
            province = group[0]
            try:
                compiled = compile_scenario(
                    group,
                    SnapshotOptions(
                        fertility=fertility,
                        city_level=args.city_level,
                        building_level=args.building_level,
                        military=args.military,
                        objective=args.objective,
                        scenario=scenario,
                        technologies=frozenset()
                        if args.no_technologies
                        else None
                        if args.technology is None
                        else frozenset(args.technology),
                    ),
                )
                model, build_seconds, economy = (
                    compiled.model,
                    compiled.build_seconds,
                    compiled.economy,
                )
            except (ValueError, TypeError) as error:
                cli.error(str(error))
            case: dict[str, Any] = {
                "province": "joint" if args.joint else province.name,
                "province_name": ", ".join(p.print_name for p in group),
                "fertility": fertility,
                "variables": len(model.names),
                "constraints": len(model.lower),
                "build_seconds": build_seconds,
                "omitted_effects": sorted(set(economy.omitted)) if economy is not None else [],
            }
            case.update(
                compare_model(
                    model,
                    ComparisonOptions(
                        algorithms=tuple(args.algorithms),
                        seconds=args.seconds,
                        seed=args.seed,
                        width=args.beam_width,
                        restarts=args.restarts,
                        objective=args.objective,
                        workers=args.workers,
                    ),
                    economy,
                )
            )
            report["cases"].append(case)
            _print_case(case, fertility)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def _select_provinces(args, provinces, cli):
    if args.province:
        missing = set(args.province) - {n for p in provinces for n in (p.name, p.print_name)}
        if missing:
            cli.error(f"Unknown provinces: {', '.join(sorted(missing))}")
        provinces = [
            p for p in provinces if p.name in args.province or p.print_name in args.province
        ]
    if args.limit:
        provinces = provinces[: args.limit]
    return provinces


def _print_case(case, fertility):
    for result in case["results"]:
        gdp = "-" if result["objective"] is None else f"{result['objective']:.2f}"
        gap = (
            "-"
            if result["gap_to_bound_percent"] is None
            else f"{result['gap_to_bound_percent']:.2f}%"
        )
        print(
            f"{case['province_name'][:24]:24} {fertility:5g} {result['algorithm']:12} "
            f"{result['status']:18} {gdp:>10} {result['seconds']:8.3f} {gap:>10}"
        )


if __name__ == "__main__":
    main()
