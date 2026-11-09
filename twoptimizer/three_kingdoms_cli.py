"""Optimize Three Kingdoms holdings using the historical vanilla 1.2.0 reference."""

import argparse
from dataclasses import replace
from pathlib import Path

from twoptimizer.cli_constraints import add_constraint_options, print_comparison, read_constraints
from twoptimizer.cli_holdings import add_holding_options, read_borders
from twoptimizer.export import export_session
from twoptimizer.models import RunRequest
from twoptimizer.registry import choices
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.service import solve_case
from twoptimizer.session import RunSession
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Campaign borders are not fully sourced. At zero base corruption the imported "
            "adjacent corruption effects are inactive; joint holdings with nonzero corruption "
            "require explicit --borders or --no-borders."
        ),
    )
    result.add_argument(
        "--faction", action="append", help="Faction name or ID; all compares profiles"
    )
    result.add_argument(
        "--commandery",
        "--province",
        dest="commandery",
        action="append",
        help="Commandery name or ID; repeat to batch, or all for the sourced map",
    )
    add_holding_options(
        result, joint_help="Optimize commanderies together with shared food and bonuses"
    )
    add_constraint_options(result, "three_kingdoms")
    result.add_argument("--algorithm", action="append", choices=("cp-sat", "highs"))
    result.add_argument("--seconds", type=float, help="Optional per-case limit; default no limit")
    result.add_argument("--workers", type=int, help="Optional override; default machine CPU budget")
    _snapshot_arguments(result)
    result.add_argument(
        "--output", type=Path, default=Path("benchmark-results/three-kingdoms/income")
    )
    result.add_argument(
        "--overwrite", action="store_true", help="Replace existing JSON/CSV reports"
    )
    return result


def _snapshot_arguments(result: argparse.ArgumentParser) -> None:
    defaults = ThreeKingdomsOptions()
    group = result.add_argument_group("explicit static scenario inputs, common to every commandery")
    group.add_argument(
        "--city-level",
        type=city_level,
        default=None,
        metavar="auto|1..10",
        help="Optimize each commandery's city level (default auto), or fix one inhabited level",
    )
    group.add_argument("--population", type=int, default=defaults.population, help="People")
    group.add_argument(
        "--corruption", type=int, default=defaults.corruption_percent, help="Percent"
    )
    group.add_argument("--public-order-offset", type=int, default=defaults.order_offset)
    group.add_argument("--minimum-public-order", type=int, default=defaults.minimum_order)
    group.add_argument(
        "--capital-commandery", help="Faction capital name or ID; default unspecified"
    )
    group.add_argument("--reforms", "--research", choices=("none", "all"), default="none")
    group.add_argument(
        "--no-leader-effects",
        action="store_true",
        help="Disable the original faction leader's imported economic traits",
    )
    group.add_argument(
        "--resource",
        action="append",
        default=[],
        help="Resource ID supplied from outside the holding; repeatable; default none",
    )
    group.add_argument(
        "--external-food",
        type=int,
        default=defaults.external_food,
        help="Fixed food from outside this solved holding; default zero",
    )


def city_level(value: str) -> int | None:
    if value == "auto":
        return None
    try:
        level = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "City level must be auto or a whole number from 1 to 10"
        ) from error
    if level not in range(1, 11):
        raise argparse.ArgumentTypeError("City level must be auto or a whole number from 1 to 10")
    return level


def request_from_args(args: argparse.Namespace) -> RunRequest:
    config = replace(
        default_config("three_kingdoms"),
        seconds=args.seconds,
        workers=args.workers,
        research=args.reforms,
        adjacency=read_borders(args, "three_kingdoms"),
        three_kingdoms=ThreeKingdomsOptions(
            city_level=args.city_level,
            population=args.population,
            corruption_percent=args.corruption,
            order_offset=args.public_order_offset,
            minimum_order=args.minimum_public_order,
            external_food=args.external_food,
            capital_commandery=args.capital_commandery,
            external_resources=tuple(args.resource),
            include_leader_effects=not args.no_leader_effects,
        ),
        constraints=read_constraints(args, "three_kingdoms"),
        compare_constraints=args.compare_constraints,
    )
    return RunRequest(
        config,
        factions=tuple(args.faction or ()),
        provinces=tuple(args.commandery or ()),
        algorithms=tuple(args.algorithm or ()),
        joint=args.joint,
    )


def main(argv=None):
    args = parser().parse_args(argv)
    jobs, skipped = make_jobs(request_from_args(args))
    print(
        "Three Kingdoms · historical vanilla 1.2.0 reference; explicit static inputs.", flush=True
    )
    results, session = [], RunSession()
    for job in jobs:
        case = solve_case(job, session=session)
        results.append(case.to_dict())
        print(
            f"{case.faction} · {case.province} · {job.algorithm}: "
            f"{case.solver.status} · income {case.income} · bound {case.solver.bound}",
            flush=True,
        )
        print_city_levels(case.raw)
        print_comparison(case.raw)
    paths = export_session(args.output, results, skipped=skipped, overwrite=args.overwrite)
    print(f"Saved {paths[0]} and {paths[1]}", flush=True)
    return results


def print_city_levels(raw: dict) -> None:
    names = {key: name for name, key in choices("three_kingdoms").provinces}
    for key, row in raw.get("commanderies", {}).items():
        print(f"  {names[key]}: city level {row['city_level']}", flush=True)


if __name__ == "__main__":
    from twoptimizer.cli import run_cli

    raise SystemExit(run_cli(main))
