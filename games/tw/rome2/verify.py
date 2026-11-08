"""Replay stored layouts against current data, independently of solver state."""

import argparse
import hashlib
import json
from pathlib import Path

from games.tw.rome2.catalog import CATALOG, load_data
from games.tw.rome2.model import Economy
from games.tw.rome2.provenance import model_fingerprint
from games.tw.rome2.scenario import Scenario, Site


def verify(paths):
    data = load_data()
    catalog_hash = hashlib.sha256(CATALOG.read_bytes()).hexdigest()
    model_hash = model_fingerprint()
    cases, proofs, reports = 0, 0, {}
    for path in paths:
        report = json.loads(path.read_text())
        if (report["catalog_sha256"], report["model_sha256"]) != (
            catalog_hash,
            model_hash,
        ):
            raise ValueError(f"Stale data/model snapshot: {path}")
        reports[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for case in report["cases"]:
            if "sites" not in case:
                continue
            raw = dict(case["scenario"])
            raw["sites"] = tuple(Site(**row) for row in raw["sites"])
            economy = Economy(Scenario(**raw), data)
            layout = {key: row["buildings"] for key, row in case["sites"].items()}
            checked = economy.evaluate(layout, case["party_index"])
            _verify_economics(checked, case, path)
            income, bound = checked["domestic_net_income"], case["solver"]["bound"]
            if (
                abs(case["solver"]["objective"] - income) > 1e-5
                or bound is None
                or bound < income - 1e-5
            ):
                raise AssertionError("Invalid objective/bound")
            if case["solver"]["status"] == "OPTIMAL":
                if abs(bound - income) > 1e-4:
                    raise AssertionError("Optimal status has a nonzero bound gap")
                proofs += 1
                if "proof_fingerprint" in case:
                    economy.reuse_optimum(case)
            cases += 1
    return {
        "verified_feasible_layouts": cases,
        "optimal_solver_results": proofs,
        "catalog_sha256": catalog_hash,
        "model_sha256": model_hash,
        "source_reports": reports,
        "scope": (
            "Replays eligibility, slots, branches, parties, economics, "
            "food/order, objective, upper-bound consistency and portable proof "
            "metadata. Does not independently reproduce solver proofs or validate"
            " against the installed game."
        ),
    }


def _verify_economics(checked, case, path):
    for key in (
        "domestic_net_income",
        "domestic_tax_income",
        "building_maintenance",
        "food_surplus",
        "public_order",
        "modified_wealth",
        "tax_modifier_percent_net",
    ):
        if abs(checked[key] - case[key]) > 1e-5:
            raise AssertionError(f"Stored economics differs: {path}, {case['case_key']}, {key}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/rome2-verification.json"))
    args = parser.parse_args(argv)
    paths = args.input or [
        Path("reports") / f"rome2-{name}-comparison.json"
        for name in ("income", "research", "province", "solver", "resource", "marib")
    ]
    result = verify(paths)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        "Verified "
        f"{result['verified_feasible_layouts']}"
        " layouts ("
        f"{result['optimal_solver_results']}"
        " optimal solver results)"
    )
    return result


if __name__ == "__main__":
    main()
