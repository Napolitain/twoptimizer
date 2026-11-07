"""Combine solver incumbents/bounds into honest faction rank intervals."""

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def summarize(paths):
    grouped = defaultdict(list)
    fingerprints, sources = set(), {}
    for path in paths:
        report = json.loads(path.read_text())
        fingerprints.add((report["catalog_sha256"], report["model_sha256"]))
        sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for case in report["cases"]:
            grouped[json.dumps(case["scenario"], sort_keys=True)].append(case)
    if len(fingerprints) != 1:
        raise ValueError("Cannot combine different model/data snapshots")
    rows = []
    for cases in grouped.values():
        usable = [c for c in cases if c.get("domestic_net_income") is not None]
        if not usable:
            raise ValueError("Every ranked faction needs a feasible incumbent")
        best = max(usable, key=lambda c: c["domestic_net_income"])
        upper = min(
            c["solver"]["bound"] for c in usable if c["solver"]["bound"] is not None
        )
        if upper < best["domestic_net_income"] - 1e-5:
            raise ValueError("An incumbent exceeds another solver's upper bound")
        proofs = sorted(
            {
                c["solver"]["algorithm"]
                for c in cases
                if c["solver"]["status"] == "OPTIMAL"
            }
        )
        rows.append(
            {
                "layout": best["layout"],
                "research": best["scenario"].get("technology_profile", "archived")
                if best["scenario"]["all_technologies"]
                else "disabled",
                "world_profile": best["scenario"].get("world_profile"),
                "faction_id": best["scenario"]["faction"],
                "faction": best["faction_name"],
                "best_income": best["domestic_net_income"],
                "upper_bound": upper,
                "status": "OPTIMAL" if proofs else "FEASIBLE",
                "rank_min": 0,
                "rank_max": 0,
                "incumbent_solver": best["solver"]["algorithm"],
                "proof_solvers": ";".join(proofs),
                "scenario_key": json.dumps(
                    {k: v for k, v in best["scenario"].items() if k != "faction"},
                    sort_keys=True,
                ),
            }
        )
    for row in rows:
        others = [
            r for r in rows if r is not row and r["scenario_key"] == row["scenario_key"]
        ]
        row["rank_min"] = 1 + sum(
            r["best_income"] > row["upper_bound"] + 1e-5 for r in others
        )
        row["rank_max"] = 1 + sum(
            r["upper_bound"] > row["best_income"] + 1e-5 for r in others
        )
    rows.sort(
        key=lambda r: (r["layout"], r["research"], -r["best_income"], r["faction"])
    )
    for row in rows:
        del row["scenario_key"]
    return {
        "source_reports": sources,
        "catalog_sha256": next(iter(fingerprints))[0],
        "model_sha256": next(iter(fingerprints))[1],
        "note": "Ranks compare only the covered factions in each declared scenario. Bounds overlapping a rival's income leave the ranking uncertain; ties use competition ranks. Model optimality does not certify current in-game fidelity.",
        "rows": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append")
    parser.add_argument("--output", type=Path, default=Path("reports/rome2-ranking"))
    args = parser.parse_args(argv)
    paths = args.input or [
        Path("reports") / (name + ".json")
        for name in (
            "rome2-income-comparison",
            "rome2-solver-comparison",
            "rome2-resource-comparison",
            "rome2-province-comparison",
            "rome2-research-comparison",
        )
    ]
    payload = summarize(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    with args.output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(payload["rows"][0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(payload["rows"])
    print(
        f"Summarized {len(payload['rows'])} faction/scenario rows from {len(paths)} reports"
    )
    return payload


if __name__ == "__main__":
    main()
