"""Compare settled Attila factions on identical province income scenarios.

Example: python -m games.tw.faction_comparison --seconds 15 --workers 8
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from games.tw.models.game_attila import AttilaGame
from twoptimizer import service
from twoptimizer.adapters.attila import faction_report
from twoptimizer.attila_session import (
    AttilaSession,
    faction_metadata,
)
from twoptimizer.attila_session import (
    native_factions as native_factions,
)
from twoptimizer.attila_session import (
    signature as signature,
)
from twoptimizer.catalog import ROOT
from twoptimizer.models import RunConfig
from twoptimizer.session import RunSession


def _parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--province", action="append")
    cli.add_argument("--fertility", type=float, default=5)
    cli.add_argument(
        "--religion",
        choices=[r.name for r in AttilaGame.Religion],
        default="CHRIST_ORTHODOX",
    )
    cli.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Optional time limit per case; default runs to completion",
    )
    cli.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional CPU worker override; default automatic",
    )
    cli.add_argument(
        "--resume",
        action="store_true",
        help="Reuse validated optimal cases from the output file; rerun incomplete proofs",
    )
    cli.add_argument(
        "--all-factions",
        action="store_true",
        help="Include NPC/rebel/separatist entries",
    )
    cli.add_argument("--output", type=Path, default=Path("benchmark-results/factions/income.json"))
    return cli


def main(argv=None):
    cli = _parser()
    args = cli.parse_args(argv)
    provinces = args.province or ["Aegyptus", "Thracia", "Germania"]
    factions = (
        [f for f in AttilaGame.Factions if f.value.startswith("att_fact_")]
        if args.all_factions
        else native_factions()
    )
    settings = vars(args).copy()
    settings["output"] = str(args.output)
    report = {
        "settings": settings,
        "objective": "income",
        "scope": (
            "Independent hypothetical ownership of each province; common "
            "religion, no treasury interest, zero unsupplied "
            "trade/tribute/corruption/army costs. Technology effects and legacy "
            "disables included. Not starting-position or full-campaign "
            "comparisons."
        ),
        "factions": [],
        "excluded": [],
    }
    session = RunSession(attila=AttilaSession(reuse_proofs=True, prior=_read_prior_cases(args)))
    metadata = faction_metadata()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for faction in factions:
        info = metadata[faction.value]
        if info["nomadic"]:
            report["excluded"].append(
                {
                    "id": faction.value,
                    "name": info["name"],
                    "reason": "Nomadic/horde income requires a different model",
                }
            )
            continue
        try:
            jobs = _faction_jobs(args, faction.value, provinces)
            cases = _run_faction(jobs, session, info["name"])
        except (ValueError, TypeError) as error:
            cli.error(str(error))
        report["factions"].append({"id": faction.value, "name": info["name"], "cases": cases})
        report["unique_models"] = len(session.attila.proofs)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    directory = ROOT / "attila/data"
    report["source_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted([*directory.glob("*.tsv"), *directory.glob("online_*.json")])
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    with args.output.with_suffix(".csv").open("w") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["faction_id", "faction", *provinces, "proof_status"])
        for faction in report["factions"]:
            writer.writerow(
                [
                    faction["id"],
                    faction["name"],
                    *[c["income"] for c in faction["cases"]],
                    ",".join(c["status"] for c in faction["cases"]),
                ]
            )
    return report


def _faction_jobs(args, faction, provinces):
    # CSV columns follow the caller's province order, including the historical defaults.
    jobs = []
    for province in provinces:
        expanded, _ = service.make_jobs(
            RunConfig(
                game="attila",
                faction=faction,
                province=province,
                algorithm="cp-sat",
                fertility=args.fertility,
                religion=args.religion,
                research="all",
                seconds=args.seconds,
                workers=args.workers,
            )
        )
        jobs.extend(expanded)
    return jobs


def _run_faction(jobs, session, name):
    cases = []
    for job in jobs:
        case = faction_report(service.solve_case(job, session=session))
        cases.append(case)
        print(
            f"{name:24} {case['province']:12} {case['status']:12} "
            f"{case['income']!s:12} {'reused' if case['proof_reused'] else 'solved'}",
            flush=True,
        )
    return cases


def _read_prior_cases(args):
    if not args.resume or not args.output.exists():
        return {}
    old = json.loads(args.output.read_text())
    return {
        case["signature"]: case
        for faction in old["factions"]
        for case in faction["cases"]
        if case["status"] == "OPTIMAL" and case["selected"] is not None
    }


if __name__ == "__main__":
    main()
