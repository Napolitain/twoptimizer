"""Translate explicit CLI ownership and border inputs into application requests."""

import argparse
import json
from pathlib import Path

from twoptimizer.errors import ApplicationError
from twoptimizer.requests import province_id


def add_holding_options(parser: argparse.ArgumentParser) -> None:
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--joint", action="store_true", help="Optimize selected provinces together")
    mode.add_argument(
        "--independent",
        dest="joint",
        action="store_false",
        help="Optimize each province separately (default)",
    )
    parser.set_defaults(joint=False)
    borders = parser.add_mutually_exclusive_group()
    borders.add_argument(
        "--borders",
        type=Path,
        help="JSON list of neighboring province pairs, using names or IDs; each pair is two-way",
    )
    borders.add_argument(
        "--no-borders",
        action="store_true",
        help="Explicitly treat selected provinces as having no adjacency effects",
    )


def read_borders(args, game: str) -> tuple[tuple[str, str], ...] | None:
    if args.no_borders:
        return ()
    if args.borders is None:
        return None
    try:
        raw = json.loads(args.borders.read_text())
    except (OSError, ValueError) as error:
        raise ApplicationError(f"Cannot read border pairs: {error}") from error
    if not isinstance(raw, list) or any(
        not isinstance(pair, list) or len(pair) != 2 for pair in raw
    ):
        raise ApplicationError("Borders must be a JSON list of province pairs.")
    return tuple((province_id(game, a), province_id(game, b)) for a, b in raw)
