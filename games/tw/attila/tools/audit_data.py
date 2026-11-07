"""Audit effect coverage and compare checked-in numeric effects with online facts."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from games.tw.attila.effects import RULES, Reach, reach
from games.tw.attila.tools.import_online import DATA


def audit(data_dir=DATA):
    with (data_dir / "building_effects_junction_table.tsv").open() as f:
        rows = list(csv.reader(f, delimiter="\t"))
    online = json.loads((data_dir / "online_buildings.json").read_text())
    local = defaultdict(lambda: defaultdict(float))
    effect_status = {}
    for building, effect, scope, amount in rows:
        rule = RULES.get(effect)
        destination = reach(scope)
        effect_status[(effect, scope)] = {
            "effect": effect,
            "raw_scope": scope,
            "reach": destination.value,
            "kind": rule.kind if rule else "unmodeled",
            "metrics": list(rule.categories) if rule and rule.kind == "metric" else [],
            "status": (
                "outside_settlement_model"
                if destination == Reach.OTHER
                else "requires_condition"
                if destination == Reach.CONDITIONAL
                or (rule and rule.kind == "conditional_fertility_food")
                else "requires_adjacency"
                if destination == Reach.ADJACENT
                else "metric_option"
                if rule and rule.kind == "metric"
                else "scenario_option"
                if rule
                and rule.kind
                in {
                    "immigration_order_percent",
                    "immigration_wealth_percent",
                    "corruption_percent",
                    "tariff_percent",
                    "construction_percent",
                    "sanitation_cost_percent",
                    "conversion_cost_percent",
                }
                else "modeled"
                if rule
                else "unmodeled"
            ),
        }
        if rule is None:
            continue
        for category in rule.categories or (None,):
            local[building][(rule.kind, category, destination.value)] += float(amount)
    matches, differences = 0, []
    for building, record in online["buildings"].items():
        for culture, observations in record["observations_by_culture"].items():
            expected = defaultdict(float)
            for fact in observations:
                expected[(fact["kind"], fact["category"], fact["reach"])] += fact[
                    "value"
                ]
            for key, value in expected.items():
                actual = local[building].get(key, 0)
                if abs(actual - value) <= 1e-6:
                    matches += 1
                else:
                    differences.append(
                        {
                            "building": building,
                            "culture": culture,
                            "kind": key[0],
                            "category": key[1],
                            "reach": key[2],
                            "local": actual,
                            "online": value,
                        }
                    )
    details = sorted(
        effect_status.values(), key=lambda v: (v["effect"], v["raw_scope"])
    )
    return {
        "schema_version": 2,
        "effect_rows": len(rows),
        "distinct_effects": len({r[1] for r in rows}),
        "effect_scope_pairs": len(details),
        "coverage": dict(Counter(v["status"] for v in details)),
        "imported_buildings": len(online["buildings"]),
        "online_numeric_matches": matches,
        "online_numeric_differences": differences,
        "effects": details,
        "note": "Third-party cross-check, not proof of in-game fidelity. Contextual/horde differences are retained; original effects are not overwritten.",
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, default=DATA / "effect_audit.json")
    args = cli.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("effects", "online_numeric_differences")
            },
            indent=2,
        )
    )
    print("Numeric differences:", len(report["online_numeric_differences"]))


if __name__ == "__main__":
    main()
