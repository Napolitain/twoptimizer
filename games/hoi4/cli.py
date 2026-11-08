"""Inspect HoI4 evidence and hourly planning inputs without running a gameplay model."""

import argparse
import json
from pathlib import Path

from twoptimizer.errors import ApplicationError
from twoptimizer.hoi4_data import COUNTRIES, format_reference, inspect_reference
from twoptimizer.hoi4_planning import format_planning_review, inspect_planning_file


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    data = commands.add_parser("data", help="Inspect provisional public reference data")
    data.add_argument("--country", type=str.upper, choices=(*COUNTRIES, "ALL"), default="FRA")
    plan = commands.add_parser(
        "plan-check", help="Check planning input structure without evaluating feasibility"
    )
    plan.add_argument("path", type=Path, help="JSON PlanningContract input")
    for command in (data, plan):
        command.add_argument("--json", action="store_true", help="Print the full report as JSON")
        command.add_argument("--output", type=Path, help="Save the full report as JSON")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "data":
        report = inspect_reference(args.country)
        text, label = format_reference(report), "reference"
    else:
        if args.output and args.path.resolve() == args.output.resolve():
            raise ApplicationError("Planning report output must differ from the input path")
        report = inspect_planning_file(args.path)
        text, label = format_planning_review(report), "planning"
    payload = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        try:
            args.output.write_text(payload, encoding="utf-8")
        except OSError as error:
            raise ApplicationError(f"Cannot save HoI4 {label} report: {error}") from error
    print(payload if args.json else text, end="" if args.json else "\n")
    return report
