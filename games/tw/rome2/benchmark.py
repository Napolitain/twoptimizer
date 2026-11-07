"""Compare playable Rome II profiles on explicit, controlled province layouts."""

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from games.tw.models.model_rome2 import Rome2Factions
from games.tw.rome2.effects import fact_effect, raw_effect
from games.tw.rome2.model import CATALOG, Economy, Scenario, Site, load_data


def presets(name):
    coastal = name != "inland"
    return (
        Site("capital", major=True, port=coastal),
        Site("town", port=coastal, resource="grain" if name == "grain" else None),
    )


def assumptions():
    return {
        "objective": "Current domestic provincial tax receipts, excluding external trade, armies, agents and construction spending.",
        "reference_holdings": "Controlled two-settlement provinces: inland, coastal, and coastal with a grain-producing minor core. These are explicit layouts, not historical starting provinces.",
        "slots": "Mature settlements: four ordinary plots in the capital, two in each town, plus one compulsory primary and a compulsory port when coastal.",
        "legality": "Official Grand Campaign faction lists, ordinary levels 1-4, mandatory level-4 primary. City/town, major-only sanitation and industrial, minor-only civil agriculture/mining restrictions reconstructed from public rules. Different upgraded branches may coexist; duplicate stages of the same branch may not.",
        "modifiers": "Imported faction-specific technologies are researched; construction resources/unlocks are available. Choose exactly one playable political profile, maximizing income. Dominated profiles can be safely pruned under this objective.",
        "culture": "100% own culture; applicable culture-dependent public-order bonuses use the stated maximum. No foreign-culture, garrison, war-count, difficulty, imperium or character offsets unless explicitly supplied.",
        "tax": "Normal taxes turn 100% of modified wealth into income. Tax bonuses and supplied corruption deductions are additive percentage points. Corruption defaults to zero. No slaves or slave unrest/wealth effects, no edicts, no faction-capital-only subsistence or wonder bonuses.",
        "food": "Faction-wide food must be nonnegative. Each benchmark holding is an independent single-province realm, not simultaneous ownership of all three layouts. Per-region effects multiply by the number of owned recipient regions. Effects in adjacent provinces have no recipient in this realm.",
        "growth": "Reported but not valued; no construction sequence, growth trajectory, treasury or future cash-flow forecast.",
        "source_limit": "Raw repository DB snapshot, official Emperor Edition eligibility/research references and Honga faction traits have unspecified installed versions. Their combined model is not certified as a single/current patch. New Pantheon/Jupiter campaign rules are outside scope.",
        "missing_world_inputs": "Complete region resource assignments, natural-wonder numeric bonuses and campaign states still require verification. A supplied scenario can run without them; absent resources are not inferred historical facts.",
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
        "--layout", action="append", choices=["inland", "coastal", "grain"]
    )
    parser.add_argument(
        "--algorithm",
        action="append",
        choices=["cp-sat", "cbc", "scip", "scip-nonlinear"],
    )
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-technologies", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("benchmark-results/rome2/income")
    )
    args = parser.parse_args(argv)
    data = load_data()
    source_hash = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    model_hash = hashlib.sha256(
        b"".join(
            (Path(__file__).parent / file).read_bytes()
            for file in ("model.py", "effects.py")
        )
    ).hexdigest()
    output = args.output.with_suffix(".json")
    cases = {}
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
                                case.get("domestic_tax_income"),
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
    for layout in args.layout or ["inland", "coastal", "grain"]:
        for faction in args.faction or sorted(data["factions"]):
            scenario = Scenario(
                faction,
                presets(layout),
                name=layout,
                all_technologies=not args.no_technologies,
            )
            for algorithm in args.algorithm or ["cp-sat"]:
                key = json.dumps([asdict(scenario), algorithm], sort_keys=True)
                if key in cases and cases[key]["solver"]["status"] == "OPTIMAL":
                    continue
                economy = Economy(scenario, data)
                fingerprint = economy.fingerprint() if algorithm == "cp-sat" else None
                result = (
                    economy.reuse_optimum(proofs[fingerprint])
                    if fingerprint in proofs
                    else economy.optimize(algorithm, args.seconds, args.workers)
                )
                result.update(
                    case_key=key,
                    layout=layout,
                    faction_name=data["factions"][faction]["name"],
                )
                if fingerprint and result["solver"]["status"] == "OPTIMAL":
                    proofs[fingerprint] = result
                old = cases.get(key)
                if old and old.get("domestic_tax_income", -1) > result.get(
                    "domestic_tax_income", -1
                ):
                    result = old
                cases[key] = result
                same = [
                    c
                    for c in cases.values()
                    if c["layout"] == layout
                    and c["scenario"]["faction"] == faction
                    and c["scenario"]["all_technologies"] == scenario.all_technologies
                    and c["solver"]["status"] == "OPTIMAL"
                ]
                if (
                    same
                    and max(c["domestic_tax_income"] for c in same)
                    - min(c["domestic_tax_income"] for c in same)
                    > 1e-5
                ):
                    raise AssertionError("Exact solvers disagree on a proved optimum")
                save()  # Retain incumbents/proofs if a later source case fails.
                print(
                    f"{layout:7} {faction:15} {algorithm:6} {result['solver']['status']:9} income={result.get('domestic_tax_income')} bound={result['solver']['bound']} ({result['solver']['seconds']:.2f}s)",
                    flush=True,
                )
    return payload


if __name__ == "__main__":
    main()
