"""Compare playable Rome II profiles on explicit, controlled province layouts."""

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path

from games.tw.models.model_rome2 import Rome2Factions
from games.tw.rome2.effects import fact_effect, raw_effect
from games.tw.rome2.model import CATALOG, Economy, Scenario, Site, load_data
from games.tw.rome2.world import province_scenario


def presets(name):
    coastal = name != "inland"
    return (
        Site("capital", major=True, port=coastal),
        Site("town", port=coastal, resource="grain" if name == "grain" else None),
    )


def assumptions():
    return {
        "objective": "Current domestic provincial tax receipts less modeled building maintenance, excluding external trade, armies, agents and construction spending.",
        "reference_holdings": "Controlled two-settlement provinces: inland, coastal, and coastal with a grain-producing minor core. These are explicit layouts, not historical starting provinces.",
        "slots": "Mature settlements: four ordinary plots in the capital, two in each town, plus one compulsory primary and a compulsory port when coastal.",
        "legality": "Grand Campaign faction reference lists, ordinary levels 1-4, mandatory mature primary up to level 4 (highest available for shorter resource chains). City/town, major-only sanitation and industrial, minor-only civil agriculture/mining restrictions reconstructed from public rules. Different upgraded branches may coexist; duplicate stages of the same branch may not.",
        "modifiers": "Research bonuses are disabled by default; explicit public/archived research profiles are optional. Construction resources/unlocks are assumed available independently. Choose exactly one playable political profile, maximizing income.",
        "culture": "100% own culture; applicable culture-dependent public-order bonuses use the stated maximum. No foreign-culture, garrison, war-count, difficulty, imperium or character offsets unless explicitly supplied.",
        "tax": "Normal taxes turn 100% of modified wealth into income. Tax bonuses and corruption deductions are additive percentage points; corruption reductions cannot make corruption negative. No slaves, active edicts or faction-capital-only subsistence. Named provinces include the explicitly labeled community patch-18 wonder profile unless disabled.",
        "food": "Faction-wide food must be nonnegative. Each benchmark holding is an independent single-province realm, not simultaneous ownership of all three layouts. Per-region effects multiply by the number of owned recipient regions. Effects in adjacent provinces have no recipient in this realm.",
        "growth": "Reported but not valued; no construction sequence, growth trajectory, treasury or future cash-flow forecast.",
        "source_limit": "Raw repository DB snapshot, official Emperor Edition eligibility/research references and Honga faction traits have unspecified installed versions. Their combined model is not certified as a single/current patch. New Pantheon/Jupiter campaign rules are outside scope.",
        "world_inputs": "Named provinces use all 173 sourced resource assignments and repository slot/port templates. Three port conflicts and older wonder-value conflicts are disclosed in world.json/world_modifiers.json. Roma/Pharos effect interpretations still need installed definitions. Each province is an independent counterfactual holding, not a historical faction start.",
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
        for text in faction["traits"]["culture_facts"] + [
            text
            for p in faction["traits"]["parties"]
            if p["playable"]
            for text in p["facts"]
        ]:
            effect = fact_effect(text)
            facts.append(
                {
                    "faction": key,
                    "fact": text,
                    "disposition": effect.kind
                    if effect
                    else "outside_declared_scenario",
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
                    "disposition": effect.kind
                    if effect
                    else "outside_declared_scenario",
                }
    return {
        "raw_effect_scopes": list(raw.values()),
        "faction_traits": facts,
        "technology_facts": list(technologies.values()),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--faction", action="append")
    parser.add_argument(
        "--province", action="append", help="Real province name or ID; may repeat"
    )
    parser.add_argument("--no-world-bonuses", action="store_true")
    parser.add_argument(
        "--layout", action="append", choices=["inland", "coastal", "grain"]
    )
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
    parser.add_argument(
        "--technology-profile", choices=["public", "archived"], default="public"
    )
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark-results/rome2/income")
    )
    args = parser.parse_args(argv)
    if args.seconds is not None and (not isfinite(args.seconds) or args.seconds <= 0):
        parser.error("--seconds must be positive; omit it to run to completion")
    if args.fill_missing and not args.resume:
        parser.error("--fill-missing requires --resume")
    data = load_data()
    source_hash = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    model_hash = hashlib.sha256(
        b"".join(
            (Path(__file__).parent / file).read_bytes()
            for file in (
                "model.py",
                "effects.py",
                "world.py",
                "data/world.json",
                "data/world_modifiers.json",
            )
        )
    ).hexdigest()
    output = args.output.with_suffix(".json")
    cases = {}
    previous = {}
    if args.resume and output.exists():
        previous = json.loads(output.read_text())
        if previous["catalog_sha256"] != source_hash:
            raise ValueError("Cannot reuse a different data snapshot")
        if previous.get("model_sha256") != model_hash:
            raise ValueError("Cannot reuse results from different model code")
        cases = {r["case_key"]: r for r in previous["cases"]}
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "catalog_sha256": source_hash,
        "model_sha256": model_hash,
        "assumptions": assumptions(),
        "coverage": audit(data),
        "excluded_playable_factions": sorted(
            {f.value for f in Rome2Factions if f.value.startswith("rom_")}
            - data["factions"].keys()
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
                        )
                    )
                )

    proofs = {
        c["proof_fingerprint"]: c
        for c in cases.values()
        if c["solver"]["status"] == "OPTIMAL" and "proof_fingerprint" in c
    }
    factions = args.faction or sorted(data["factions"])
    if args.all_technologies and not args.faction:
        factions = [
            f
            for f in factions
            if (
                data["technology_coverage"][f]["complete_public_tree"]
                if args.technology_profile == "public"
                else f in data["technologies_archived"]
            )
        ]
    payload["research_mode"] = (
        args.technology_profile
        if args.all_technologies
        else "bonuses_disabled_unlocked_buildings"
    )
    payload["research_excluded_factions"] = (
        sorted(set(data["factions"]) - set(factions))
        if args.all_technologies and not args.faction
        else []
    )
    for layout in args.province or args.layout or ["inland", "coastal", "grain"]:
        for faction in factions:
            scenario = (
                province_scenario(
                    layout,
                    faction,
                    all_technologies=args.all_technologies,
                    technology_profile=args.technology_profile,
                    world_bonuses=not args.no_world_bonuses,
                )
                if args.province
                else Scenario(
                    faction,
                    presets(layout),
                    name=layout,
                    all_technologies=args.all_technologies,
                    technology_profile=args.technology_profile,
                )
            )
            for algorithm in args.algorithm or ["portfolio"]:
                key = json.dumps([asdict(scenario), algorithm], sort_keys=True)
                if key in cases and (
                    args.fill_missing or cases[key]["solver"]["status"] == "OPTIMAL"
                ):
                    continue
                economy = Economy(scenario, data)
                seeds = [
                    c
                    for c in cases.values()
                    if "sites" in c
                    and json.dumps(c["scenario"], sort_keys=True)
                    == json.dumps(asdict(scenario), sort_keys=True)
                ]
                seed = max(seeds, key=lambda c: c["domestic_net_income"], default=None)
                fingerprint = (
                    economy.fingerprint()
                    if algorithm in {"cp-sat", "portfolio"}
                    else None
                )
                result = (
                    economy.reuse_optimum(proofs[fingerprint])
                    if fingerprint in proofs
                    else economy.optimize(
                        algorithm,
                        args.seconds,
                        args.workers,
                        incumbent=seed
                        if algorithm in {"cp-sat", "scip-nonlinear", "portfolio"}
                        else None,
                    )
                )
                result.update(
                    case_key=key,
                    layout=layout,
                    faction_name=data["factions"][faction]["name"],
                )
                if (
                    fingerprint
                    and result.get("proof_fingerprint") == fingerprint
                    and result["solver"]["status"] == "OPTIMAL"
                ):
                    proofs[fingerprint] = result
                old = cases.get(key)
                if old and old.get("domestic_net_income", -1) > result.get(
                    "domestic_net_income", -1
                ):
                    best = old
                else:
                    best = result
                bounds = [
                    c["solver"]["bound"]
                    for c in (old, result)
                    if c and c["solver"]["bound"] is not None
                ]
                if bounds:
                    best["solver"]["bound"] = min(bounds)
                result = best
                cases[key] = result
                same = [
                    c
                    for c in cases.values()
                    if c["layout"] == layout
                    and c["scenario"]["faction"] == faction
                    and c["scenario"] == asdict(scenario)
                    and c["solver"]["status"] == "OPTIMAL"
                ]
                if (
                    same
                    and max(c["domestic_net_income"] for c in same)
                    - min(c["domestic_net_income"] for c in same)
                    > 1e-5
                ):
                    raise AssertionError("Exact solvers disagree on a proved optimum")
                save()  # Retain incumbents/proofs if a later source case fails.
                print(
                    f"{layout:7} {faction:15} {algorithm:6} {result['solver']['status']:9} income={result.get('domestic_net_income')} bound={result['solver']['bound']} ({result['solver']['seconds']:.2f}s)",
                    flush=True,
                )
    return payload


if __name__ == "__main__":
    main()
