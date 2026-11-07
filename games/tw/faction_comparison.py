"""Compare settled Attila factions on identical province income scenarios.

Example: python -m games.tw.faction_comparison --seconds 15 --workers 8
"""

import argparse
import csv
import hashlib
import json
from math import isfinite
from pathlib import Path

from games.tw.attila.modifiers import catalog
from games.tw.attila.traits import profile
from games.tw.benchmark import load_attila, snapshot
from games.tw.competition import Result, solve
from games.tw.models.game_attila import AttilaGame


def signature(model):
    """Reuse a proof only when every variable, coefficient and bound matches."""
    digest = hashlib.sha256(json.dumps(model.names).encode())
    for array in (model.profit, model.matrix, model.lower, model.upper):
        digest.update(str(array.shape).encode())
        if hasattr(array, "update_hash"):
            array.update_hash(digest)
        else:
            digest.update(array.tobytes())
    digest.update(str(model.offset).encode())
    return digest.hexdigest()


def native_factions():
    return [
        AttilaGame.Factions(f)
        for f in catalog()["faction_slugs"]
        if not any(s in f for s in ("separatist", "rebel"))
        and profile(f)["ruling_party_identified"]
    ]


def main(argv=None):
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
    args = cli.parse_args(argv)
    if (
        (args.seconds is not None and (not isfinite(args.seconds) or args.seconds <= 0))
        or (args.workers is not None and args.workers < 1)
        or args.fertility < 0
    ):
        cli.error("Invalid budget, workers or fertility")
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
    cache = {}
    prior = {}
    prior = _read_prior_cases(args, prior)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for faction in factions:
        parser = load_attila(faction, AttilaGame.Religion[args.religion])
        info = parser.faction_to_culture[faction.value]
        if "nomadic" in info.subculture:
            report["excluded"].append(
                {
                    "id": faction.value,
                    "name": info.name,
                    "reason": "Nomadic/horde income requires a different model",
                }
            )
            continue
        row = {"id": faction.value, "name": info.name, "cases": []}
        for name in provinces:
            matches = [p for p in parser.provinces.values() if name in (p.name, p.print_name)]
            if len(matches) != 1:
                cli.error(f"Unknown or ambiguous province: {name}")
            model, build_seconds, economy = snapshot(
                matches[0], args.fertility, retain_economy=True
            )
            key = signature(model)
            reused = key in cache
            result = cache.get(key)
            if result is None and key in prior:
                previous = prior[key]
                selected = set(previous["selected"])
                auxiliary = {
                    variable.name(): monomial for monomial, variable in economy.products.items()
                }
                values = [
                    economy.evaluate({auxiliary.get(name, (name,)): 1}, selected)
                    for name in model.names
                ]
                value = float(model.profit @ values + model.offset)
                if (
                    model.feasible(values)
                    and abs(value - previous["income"]) < 1e-5
                    and abs(value - previous["bound"]) < 1e-5
                ):
                    result = Result(
                        "cp-sat",
                        "OPTIMAL",
                        seconds=previous["solve_seconds"],
                        objective=value,
                        bound=previous["bound"],
                        values=values,
                        detail="Reused validated optimal case with identical compiled model",
                    )
                    cache[key] = result
                    reused = True
            if result is None:
                result = solve(model, "cp-sat", seconds=args.seconds, workers=args.workers)
                cache[key] = result
            selected = (
                None
                if result.values is None
                else {
                    n
                    for n, value in zip(model.names, result.values, strict=False)
                    if value > 0.5 and not n.startswith("__")
                }
            )
            layout = None if selected is None else economy.evaluate_layout(selected)
            _validate_comparison(layout, model, result)
            case = {
                "province": matches[0].print_name,
                "signature": key,
                "status": result.status,
                "income": result.objective,
                "bound": result.bound,
                "proof_reused": reused,
                "solve_seconds": result.seconds,
                "build_seconds": build_seconds,
                "selected": None if selected is None else sorted(selected),
                "layout": layout,
                "omitted_effects": sorted(set(economy.omitted)),
            }
            row["cases"].append(case)
            print(
                (
                    f"{info.name:24}"
                    " "
                    f"{name:12}"
                    " "
                    f"{result.status:12}"
                    " "
                    f"{result.objective!s:12}"
                    " "
                    f"{('reused' if reused else 'solved')}"
                ),
                flush=True,
            )
        report["factions"].append(row)
        report["unique_models"] = len(cache)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    # Include exclusions even when the last factions were nomadic.
    data_dir = parser.game_dir
    report["source_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted([*data_dir.glob("*.tsv"), *data_dir.glob("online_*.json")])
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


def _validate_comparison(layout, model, result):
    if layout is not None and (
        not model.feasible(result.values) or abs(layout["objective"] - result.objective) > 1e-5
    ):
        raise RuntimeError("Comparison result did not validate")


def _read_prior_cases(args, prior):
    if args.resume and args.output.exists():
        old = json.loads(args.output.read_text())
        prior = {
            c["signature"]: c
            for f in old["factions"]
            for c in f["cases"]
            if c["status"] == "OPTIMAL" and c["selected"] is not None
        }
    return prior


if __name__ == "__main__":
    main()
