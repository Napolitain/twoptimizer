"""Audit effect coverage and compare checked-in numeric effects with online facts."""

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

from games.tw.attila.effects import RULES, Reach, reach
from games.tw.attila.tools.import_online import DATA


def audit_campaign_modifiers():
    from games.tw.attila.modifiers import catalog, modifier_profile
    from games.tw.attila.traits import profile

    data = catalog()
    factions = json.loads((DATA / "online_factions.json").read_text())["factions"]
    faction_facts = [
        {"faction": f, **record} for f in factions for record in profile(f)["traits"]
    ]
    technology_facts = []
    for faction, slug in data["faction_slugs"].items():
        if (
            "separatist" in faction
            or "rebel" in faction
            or not profile(faction)["ruling_party_identified"]
        ):
            continue
        game = SimpleNamespace(faction=SimpleNamespace(value=faction), religion=None)
        report, _ = modifier_profile(game)
        technology_facts.extend({"tree": slug, **fact} for fact in report["facts"])
    religion_facts = []
    from games.tw.attila.modifiers import RELIGION_KEYS

    for faith in RELIGION_KEYS:
        game = SimpleNamespace(
            faction=SimpleNamespace(value="att_fact_eastern_roman_empire"),
            religion=SimpleNamespace(value=faith),
        )
        report, _ = modifier_profile(game, scenario={"technology_effects": False})
        religion_facts.extend({"religion": faith, **fact} for fact in report["facts"])
    return {
        "faction_entries": len(factions),
        "technology_trees": len(data["technologies"]),
        "religions": len(data["religions"]["records"]),
        "coverage": {
            name: dict(Counter(f["status"] for f in facts))
            for name, facts in (
                ("faction_traits", faction_facts),
                ("active_technology_facts", technology_facts),
                ("state_religion_facts", religion_facts),
            )
        },
        "unmodeled": [
            f
            for f in faction_facts + technology_facts + religion_facts
            if f["status"] == "unmodeled"
        ],
        "note": "Supported conditional faction traits still need campaign inputs. Interest is excluded by the requested objective. Missing building metadata is reported separately in each layout's catalogue_exclusions.",
    }


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
        "campaign_modifiers": audit_campaign_modifiers(),
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
