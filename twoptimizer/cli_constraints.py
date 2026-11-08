"""Optional scenario constraints shared by the three command-line interfaces."""

import argparse
import json

from twoptimizer.constraint_options import ConstraintOptions


def add_constraint_options(parser: argparse.ArgumentParser, game: str) -> None:
    group = parser.add_argument_group("optional constraints")
    group.add_argument(
        "--require-building",
        action="append",
        default=[],
        metavar="ID",
        help=(
            "Require at least one copy of this building in each solved holding; repeatable. "
            "Existing availability and unique-building limits still apply"
        ),
    )
    group.add_argument(
        "--forbid-building",
        action="append",
        default=[],
        metavar="ID",
        help="Exclude this building from each solved holding; repeatable",
    )
    if game == "attila":
        group.add_argument(
            "--minimum-religious-influence",
            type=float,
            metavar="POINTS",
            help=(
                "Require this minimum state-religion influence in every selected province; "
                "effect points, not a population percentage"
            ),
        )
    elif game == "shogun2":
        group.add_argument(
            "--religion",
            choices=("buddhist", "christian", "ikko"),
            help="Override the clan's native faith; existing clan/religion rules still apply",
        )
        group.add_argument(
            "--nanban-contact",
            action="store_true",
            help="Assume Nanban contact for eligible buildings; does not force construction",
        )


def read_constraints(args: argparse.Namespace, game: str) -> ConstraintOptions:
    return ConstraintOptions(
        required_buildings=tuple(args.require_building),
        forbidden_buildings=tuple(args.forbid_building),
        minimum_religious_influence=args.minimum_religious_influence if game == "attila" else None,
        shogun_religion=args.religion if game == "shogun2" else None,
        nanban_contact=args.nanban_contact if game == "shogun2" else False,
    )


def constraint_metadata(args: argparse.Namespace, game: str) -> dict:
    options = read_constraints(args, game)
    return {} if options == ConstraintOptions() else {"constraints": options.to_dict()}


def constraint_csv(args: argparse.Namespace, game: str) -> dict[str, str]:
    return {
        key: json.dumps(value, sort_keys=True)
        for key, value in constraint_metadata(args, game).items()
    }
