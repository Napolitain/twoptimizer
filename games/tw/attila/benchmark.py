"""Run competing optimizers against the checked-in Total War: Attila data.

Example: python -m games.tw.attila.benchmark --fertility 0 5 --limit 3 --output results.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import batched
from pathlib import Path

import ortools

from games.optimization.competition import ALGORITHMS
from games.tw.attila.game import AttilaGame
from games.tw.attila.scenario import Scenario
from twoptimizer import service
from twoptimizer.adapters.attila import comparison_report
from twoptimizer.catalog import ROOT
from twoptimizer.cli_constraints import add_constraint_options, print_comparison, read_constraints
from twoptimizer.cli_holdings import add_holding_options, read_borders
from twoptimizer.models import AttilaOptions, RegionFertility, RunConfig, RunRequest
from twoptimizer.registry import game_plugin
from twoptimizer.session import RunSession


def _parser():
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
    cli.add_argument("--scenario", type=Path, help="Campaign inputs and targets as JSON")
    add_holding_options(cli)
    add_constraint_options(cli, "attila")
    cli.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional CPU worker override; default automatic",
    )
    cli.add_argument(
        "--objective",
        choices=("income",),
        default="income",
        help="Maximize recurring income (the supported application objective)",
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
    return cli


def request_from_args(args) -> RunRequest:
    """Decode CLI syntax into the same typed requests used by workers and the TUI."""
    campaign = Scenario(json.loads(args.scenario.read_text())) if args.scenario else None
    region_fertility = tuple(
        RegionFertility(name, float(value))
        for name, value in (assignment.rsplit("=", 1) for assignment in args.region_fertility)
    )
    config = RunConfig(
        game="attila",
        faction=args.faction,
        province="all",
        algorithm="cp-sat",
        seconds=args.seconds,
        workers=args.workers,
        research="none" if args.no_technologies else "all",
        religion=args.religion,
        joint=args.joint,
        adjacency=read_borders(args, "attila"),
        constraints=read_constraints(args, "attila"),
        compare_constraints=args.compare_constraints,
        attila=AttilaOptions(
            campaign=campaign,
            technologies=None if args.technology is None else tuple(args.technology),
            region_fertility=region_fertility,
            city_level=args.city_level,
            building_level=args.building_level,
            military=args.military,
            seed=args.seed,
        ),
    )
    return RunRequest(
        config,
        provinces=tuple(args.province or ("all",)),
        algorithms=tuple(args.algorithms),
        fertilities=tuple(args.fertility),
        joint=args.joint,
        limit=args.limit,
    )


def _source_digest():
    directory = ROOT / "attila/data"
    digest = hashlib.sha256()
    for path in sorted(
        [
            *directory.glob("*.tsv"),
            directory / "online_buildings.json",
            directory / "online_factions.json",
            directory / "online_modifiers.json",
        ]
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _run_cases(jobs, joint, algorithm_count):
    session = RunSession()
    for group in batched(jobs, algorithm_count, strict=False):
        case = comparison_report(
            [service.solve_case(job, session=session) for job in group], joint=joint
        )
        _print_case(case, group[0].fertility)
        yield case


def main(argv=None):
    cli = _parser()
    args = cli.parse_args(argv)
    try:
        request = request_from_args(args)
        jobs, _ = service.make_jobs(request)
    except (OSError, ValueError, TypeError) as error:
        cli.error(str(error))
    settings = vars(args).copy()
    settings.pop("output")
    settings["scenario"] = (
        request.config.attila.campaign.to_dict() if request.config.attila.campaign else None
    )
    report = {
        "settings": settings,
        "ortools_version": ortools.__version__,
        "data_sha256": _source_digest(),
        "model_assumptions": game_plugin("attila").notes,
        "cases": [],
    }
    print(
        f"{'Province':24} {'Fert':>5} {'Algorithm':12} {'Status':18} "
        f"{'Objective':>10} {'Seconds':>8} {'Gap/bound':>10}"
    )
    try:
        report["cases"] = list(_run_cases(jobs, args.joint, len(args.algorithms)))
    except (ValueError, TypeError) as error:
        cli.error(str(error))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


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
        print_comparison(result)


if __name__ == "__main__":
    main()
