"""Inventory special-building evidence without inferring availability from names.

This report is audit data, not solver input. Rebuild it offline with the bundled
tables and public-source observations; no game installation or solve is needed.
"""

import argparse
import csv
import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
from typing import NotRequired, TypedDict

from games.tw.attila.effects import RULES, Reach, reach
from games.tw.attila.special_slots import PATRIARCHAL_SLOTS
from games.tw.attila.tools.import_online import DATA

INPUTS = (
    "building_culture_variants_table.tsv",
    "building_effects_junction_table.tsv",
    "online_buildings.json",
    "special_building_sources.json",
)
EXTRA_CANDIDATES = frozenset({"att_bld_eos_marib_dam", "att_bld_eos_mint"})
UNIMPORTED_FIELDS = (
    "only_in_capital",
    "faction_unique",
    "first_in_world_bundle",
    "religion_requirement",
    "resource_requirement",
)


class SiteRule(TypedDict):
    kind: str
    religion: NotRequired[str]
    slot_templates: NotRequired[list[str]]
    region: NotRequired[str]


class EffectFact(TypedDict):
    effect: str
    raw_scope: str
    reach: str
    value: float
    model_kind: str


class BuildingAudit(TypedDict):
    names: list[str]
    culture_variants: list[list[str]]
    income_metadata: object
    income_metadata_status: str
    online_sources: object
    modeled_site_rule: SiteRule
    raw_availability_fields: dict[str, None]
    effects: list[EffectFact]


def _identities(data_dir, external_buildings):
    records = defaultdict(lambda: {"names": set(), "culture_variants": set()})
    with (data_dir / INPUTS[0]).open() as stream:
        for row in csv.reader(stream, delimiter="\t"):
            building = row[0]
            if not building.startswith("att_"):
                continue
            if (
                "legendary" not in building
                and building not in EXTRA_CANDIDATES
                and building not in external_buildings
            ):
                continue
            records[building]["names"].add(row[4])
            records[building]["culture_variants"].add(tuple(row[1:4]))
    return records


def _effects(data_dir):
    records: defaultdict[str, list[EffectFact]] = defaultdict(list)
    with (data_dir / INPUTS[1]).open() as stream:
        for building, effect, scope, amount in csv.reader(stream, delimiter="\t"):
            rule = RULES.get(effect)
            records[building].append(
                {
                    "effect": effect,
                    "raw_scope": scope,
                    "reach": reach(scope).value,
                    "value": float(amount),
                    "model_kind": rule.kind if rule else "unmodeled",
                }
            )
    return records


def _site_rule(building) -> SiteRule:
    if building.startswith("att_bld_religion_") and "_legendary_" in building:
        faith = building.removeprefix("att_bld_religion_").split("_", 1)[0]
        if faith in {"arian", "catholic", "orthodox"}:
            return {
                "kind": "patriarchal_site_and_religion",
                "religion": faith,
                "slot_templates": sorted(PATRIARCHAL_SLOTS),
            }
    if building == "att_bld_eos_marib_dam":
        return {"kind": "fixed_site", "region": "att_reg_arabia_felix_zafar"}
    return {"kind": "no_verified_special_site_rule"}


def audit(data_dir=DATA):
    online = json.loads((data_dir / "online_buildings.json").read_text())
    sources = json.loads((data_dir / "special_building_sources.json").read_text())
    effects = _effects(data_dir)
    buildings: dict[str, BuildingAudit] = {}
    for building, identity in sorted(_identities(data_dir, sources["external_buildings"]).items()):
        record = online["buildings"].get(building, {})
        buildings[building] = {
            "names": sorted(identity["names"]),
            "culture_variants": [list(v) for v in sorted(identity["culture_variants"])],
            "income_metadata": record.get("metadata"),
            "income_metadata_status": "present" if record else "missing_excluded_by_default",
            "online_sources": record.get("sources", []),
            "modeled_site_rule": _site_rule(building),
            "raw_availability_fields": dict.fromkeys(UNIMPORTED_FIELDS),
            "effects": effects[building],
        }
    return {
        "schema_version": 1,
        "purpose": "audit_only_not_solver_input",
        "selection": "Attila legendary IDs, Ma'rib Dam, Aksum Royal Mint and sourced external IDs",
        "selection_note": (
            "An inventory heuristic; neither a cap nor a complete special-building list."
        ),
        "inputs": {name: sha256((data_dir / name).read_bytes()).hexdigest() for name in INPUTS},
        "online_game_build": online["game_build"],
        "summary": {
            "local_candidates": len(buildings),
            "income_metadata": dict(
                Counter(b["income_metadata_status"] for b in buildings.values())
            ),
            "site_rules": dict(Counter(b["modeled_site_rule"]["kind"] for b in buildings.values())),
            "with_faction_effects": sum(
                any(e["reach"] == Reach.FACTION for e in b["effects"]) for b in buildings.values()
            ),
            "with_adjacent_effects": sum(
                any(e["reach"] == Reach.ADJACENT for e in b["effects"]) for b in buildings.values()
            ),
            "external_candidates_missing_locally": sorted(
                b for b in sources["external_buildings"] if b not in buildings
            ),
            "external_candidates_missing_income_metadata": sorted(
                b for b in sources["external_buildings"] if b not in online["buildings"]
            ),
        },
        "buildings": buildings,
        "limitation": (
            "Faction-capital requirements and vanilla uniqueness flags are not imported. "
            "Income from layouts selecting legendary civic buildings may exceed legal campaign "
            "income. Capital placement is distinct from a one-per-faction or world cap. "
            "Null flags are unknown, not false."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATA / "special_building_audit.json")
    args = parser.parse_args()
    report = audit()
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
