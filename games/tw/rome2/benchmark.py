"""Compare playable Rome II profiles on explicit, controlled province layouts."""

import argparse
import csv
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from games.tw.models.model_rome2 import Rome2Factions
from games.tw.rome2.catalog import CATALOG, load_data
from games.tw.rome2.effects import fact_effect, raw_effect
from games.tw.rome2.provenance import model_fingerprint
from twoptimizer import service
from twoptimizer.adapters.rome2 import prepare_scenario, request_key
from twoptimizer.models import RunConfig, RunRequest
from twoptimizer.rome_session import RomeSession
from twoptimizer.session import RunSession


def assumptions():
    return {
        "objective": (
            "Current domestic provincial tax receipts less modeled building "
            "maintenance, excluding external trade, armies, agents and "
            "construction spending."
        ),
        "reference_holdings": (
            "Controlled two-settlement provinces: inland, coastal, and coastal "
            "with a grain-producing minor core. These are explicit layouts, not "
            "historical starting provinces."
        ),
        "slots": (
            "Mature settlements: four ordinary plots in the capital, two in each "
            "town, plus one compulsory primary and a compulsory port when "
            "coastal."
        ),
        "legality": (
            "Grand Campaign faction reference lists, ordinary levels 1-4, "
            "mandatory mature primary up to level 4 (highest available for "
            "shorter resource chains). City/town, major-only sanitation and "
            "industrial, minor-only civil agriculture/mining restrictions "
            "reconstructed from public rules. Different upgraded branches may "
            "coexist; duplicate stages of the same branch may not."
        ),
        "modifiers": (
            "Research bonuses are disabled by default; explicit public/archived "
            "research profiles are optional. Construction resources/unlocks are "
            "assumed available independently. Choose exactly one playable "
            "political profile, maximizing income."
        ),
        "culture": (
            "100% own culture; applicable culture-dependent public-order bonuses "
            "use the stated maximum. No foreign-culture, garrison, war-count, "
            "difficulty, imperium or character offsets unless explicitly "
            "supplied."
        ),
        "tax": (
            "Normal taxes turn 100% of modified wealth into income. Tax bonuses "
            "and corruption deductions are additive percentage points; corruption"
            " reductions cannot make corruption negative. No slaves, active "
            "edicts or faction-capital-only subsistence. Named provinces include "
            "the explicitly labeled community patch-18 wonder profile unless "
            "disabled."
        ),
        "food": (
            "Faction-wide food must be nonnegative. Each benchmark holding is an "
            "independent single-province realm, not simultaneous ownership of all"
            " three layouts. Per-region effects multiply by the number of owned "
            "recipient regions. Effects in adjacent provinces have no recipient "
            "in this realm."
        ),
        "growth": (
            "Reported but not valued; no construction sequence, growth "
            "trajectory, treasury or future cash-flow forecast."
        ),
        "source_limit": (
            "Raw repository DB snapshot, official Emperor Edition "
            "eligibility/research references and Honga faction traits have "
            "unspecified installed versions. Their combined model is not "
            "certified as a single/current patch. New Pantheon/Jupiter campaign "
            "rules are outside scope."
        ),
        "world_inputs": (
            "Named provinces use all 173 sourced resource assignments and "
            "repository slot/port templates. Three port conflicts and older "
            "wonder-value conflicts are disclosed in "
            "world.json/world_modifiers.json. Roma/Pharos effect interpretations "
            "still need installed definitions. Each province is an independent "
            "counterfactual holding, not a historical faction start."
        ),
    }


def audit(data):
    raw = {}
    for b in data["buildings"].values():
        for item in b["effects"]:
            effect = raw_effect(item["id"], item["value"])
            raw[(item["id"], item["scope"])] = {
                "id": item["id"],
                "scope": item["scope"],
                "disposition": effect.kind if effect else "outside_static_scope",
            }
    facts = []
    for key, faction in data["factions"].items():
        for text in list(faction["traits"]["culture_facts"]) + [
            text for p in faction["traits"]["parties"] if p["playable"] for text in p["facts"]
        ]:
            effect = fact_effect(text)
            facts.append(
                {
                    "faction": key,
                    "fact": text,
                    "disposition": effect.kind if effect else "outside_declared_scenario",
                }
            )
    technologies = {}
    for tree in data["technologies"].values():
        for record in tree.values():
            for text in record["facts"]:
                effect = fact_effect(text)
                technologies[(record["id"], text)] = {
                    "technology": record["id"],
                    "fact": text,
                    "disposition": effect.kind if effect else "outside_declared_scenario",
                }
    return {
        "raw_effect_scopes": list(raw.values()),
        "faction_traits": facts,
        "technology_facts": list(technologies.values()),
    }


def _validate_run_options(args, parser):
    if args.fill_missing and not args.resume:
        parser.error("--fill-missing requires --resume")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--faction", action="append")
    parser.add_argument("--province", action="append", help="Real province name or ID; may repeat")
    parser.add_argument("--no-world-bonuses", action="store_true")
    parser.add_argument("--layout", action="append", choices=["inland", "coastal", "grain"])
    parser.add_argument(
        "--algorithm",
        action="append",
        choices=["cp-sat", "cbc", "scip", "scip-nonlinear", "portfolio"],
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Optional time limit per case; default runs to completion",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional CPU worker override; default automatic",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--fill-missing",
        action="store_true",
        help="With --resume, keep existing feasible cases and run only absent cases",
    )
    research = parser.add_mutually_exclusive_group()
    research.add_argument("--no-technologies", action="store_true")
    research.add_argument("--all-technologies", action="store_true")
    parser.add_argument("--technology-profile", choices=["public", "archived"], default="public")
    parser.add_argument("--output", type=Path, default=Path("benchmark-results/rome2/income"))
    args = parser.parse_args(argv)
    _validate_run_options(args, parser)
    data = load_data()
    source_hash = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    model_hash = model_fingerprint()
    output = args.output.with_suffix(".json")
    cases = {}
    previous = {}
    previous, cases = _load_previous(args, output, source_hash, model_hash, previous)
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "catalog_sha256": source_hash,
        "model_sha256": model_hash,
        "assumptions": assumptions(),
        "coverage": audit(data),
        "excluded_playable_factions": sorted(
            {f.value for f in Rome2Factions if f.value.startswith("rom_")} - data["factions"].keys()
        ),
    }
    if "snapshot_migration" in previous:
        payload["snapshot_migration"] = previous["snapshot_migration"]

    def save():
        payload["cases"] = list(cases.values())
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n")
        fields = [
            "layout",
            "faction",
            "algorithm",
            "status",
            "income",
            "upper_bound",
            "food",
            "public_order",
            "seconds",
        ]
        with args.output.with_suffix(".csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            for case in cases.values():
                solver = case["solver"]
                writer.writerow(
                    dict(
                        zip(
                            fields,
                            [
                                case["layout"],
                                case["faction_name"],
                                solver["algorithm"],
                                solver["status"],
                                case.get("domestic_net_income"),
                                solver["bound"],
                                case.get("food_surplus"),
                                case.get("public_order"),
                                solver["seconds"],
                            ],
                            strict=False,
                        )
                    )
                )

    request = request_from_args(args)
    jobs, _ = service.make_jobs(request)
    labels = {
        prepare_scenario(replace(request.config, province=name)).name: name
        for name in request.provinces
    }
    selected = {job.faction for job in jobs}
    payload["research_mode"] = (
        args.technology_profile if args.all_technologies else "bonuses_disabled_unlocked_buildings"
    )
    payload["research_excluded_factions"] = (
        sorted(set(data["factions"]) - selected)
        if args.all_technologies and not args.faction
        else []
    )
    session = RunSession(rome=RomeSession(cases))
    for job in jobs:
        if session.rome.should_skip(job, fill_missing=args.fill_missing):
            continue
        case = service.solve_case(job, session=session)
        result = case.raw
        key = request_key(job)
        result.update(
            case_key=key,
            layout=labels[result["scenario"]["name"]],
            faction_name=case.faction,
        )
        cases[key] = result
        save()  # Retain incumbents/proofs if a later source case fails.
        solver = case.solver
        print(
            f"{job.province:7} {job.faction:15} {job.algorithm:6} {solver.status:9} "
            f"income={case.income} bound={solver.bound} ({solver.seconds:.2f}s)",
            flush=True,
        )
    payload["cases"] = list(cases.values())
    return payload


def request_from_args(args) -> RunRequest:
    """Translate CLI defaults into the same request expanded by the terminal UI."""
    return RunRequest(
        config=RunConfig(
            game="rome2",
            faction="all",
            province="coastal",
            algorithm="portfolio",
            seconds=args.seconds,
            workers=args.workers,
            research=args.technology_profile if args.all_technologies else "none",
            technology_profile=args.technology_profile,
            world_bonuses=not args.no_world_bonuses,
        ),
        factions=tuple(args.faction or ()),
        provinces=tuple(args.province or args.layout or ("inland", "coastal", "grain")),
        algorithms=tuple(args.algorithm or ()),
    )


def _load_previous(args, output, source_hash, model_hash, previous):
    cases = {}
    if args.resume and output.exists():
        previous = json.loads(output.read_text())
        if previous["catalog_sha256"] != source_hash:
            raise ValueError("Cannot reuse a different data snapshot")
        if previous.get("model_sha256") != model_hash:
            raise ValueError("Cannot reuse results from different model code")
        cases = {r["case_key"]: r for r in previous["cases"]}
    return previous, cases


if __name__ == "__main__":
    from twoptimizer.cli import run_cli

    raise SystemExit(run_cli(main))
