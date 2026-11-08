"""Resolve source-backed starting armies without inventing reserve or rounding rules.

History/OOB defaults are documented in the pinned Country creation wiki. The
source game's initialization order and target-patch agreement remain separate
validation requirements. This module never deducts spawned equipment from a
country's reserve: the documented OOB behavior creates that equipment directly.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import replace
from fractions import Fraction
from math import isfinite
from typing import Any

from games.hoi4.data_pipeline.selection import SelectionContext, select_history
from games.hoi4.data_pipeline.syntax import Atom, Block, Document, Entry
from games.hoi4.data_pipeline.template_requirements import summarize_template_requirements

type Record = Mapping[str, Any]

RULE_SOURCE = (
    "https://github.com/thelight0211/hoi4-wiki/blob/"
    "1477082f0088e228c26266ca08893890690ba43d/"
    "Country%20creation%20-%20Hearts%20of%20Iron%204%20Wiki.md"
)
OOB_FIELDS = {"oob": "land", "set_oob": "land", "set_air_oob": "air", "set_naval_oob": "naval"}
LOGISTICS_FIELDS = {"starting_train_buffer", "starting_truck_buffer", "set_convoys"}
ARMY_EFFECTS = {
    *OOB_FIELDS,
    *LOGISTICS_FIELDS,
    "load_oob",
    "units",
    "division",
    "division_template",
    "create_unit",
    "delete_unit",
    "delete_unit_template_and_units",
    "add_equipment_production",
    "add_equipment_to_stockpile",
    "set_equipment_fraction",
    "create_equipment_variant",
    "add_manpower",
    "set_num_convoys",
}


def _source(document: Document, entry: Entry | Block | None = None) -> dict:
    result = {"path": document.source, "sha256": document.sha256}
    if entry is not None:
        result["line"] = document.position(entry.span.start)[0]
    return result


def _one(block: Block, field: str):
    values = block.assignments(field)
    return values[0].literal() if len(values) == 1 and isinstance(values[0], Atom) else None


def _defaulted(block: Block, field: str, default):
    return default if not block.named(field) else _one(block, field)


def _number(value, upper=None):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value >= 0
        and (upper is None or value <= upper)
    )


def _blocks(block: Block, field: str) -> tuple[Block, ...]:
    return tuple(value for value in block.assignments(field) if isinstance(value, Block))


def _declarations(document: Document, block: Block):
    return [
        {
            "field": entry.name,
            "value": entry.value.literal(),
            "line": document.position(entry.span.start)[0],
        }
        for entry in block.entries
        if entry.operator == "=" and isinstance(entry.value, Atom)
    ]


def _flat_blocks(document: Document, block: Block, field: str):
    return [
        {
            "source": _source(document, child),
            "declarations": _declarations(document, child),
            "unhandled_fields": [
                entry.name for entry in child.entries if not isinstance(entry.value, Atom)
            ],
        }
        for child in _blocks(block, field)
    ]


def _relevant(entry: Entry) -> bool:
    if entry.name in ARMY_EFFECTS:
        return True
    return isinstance(entry.value, Block) and any(_relevant(child) for child in entry.value.entries)


def _at_offset(block: Block, offset: int) -> Entry | None:
    for entry in block.entries:
        if entry.span.start == offset:
            return entry
        if isinstance(entry.value, Block) and entry.span.start < offset < entry.span.end:
            return _at_offset(entry.value, offset)
    return None


def _select(document: Document, context: SelectionContext, entries=None):
    body = document.root if entries is None else Block(tuple(entries), document.root.span)
    selected = select_history(replace(document, root=body), context)
    issues = []
    for issue in selected.blockers:
        entry = _at_offset(body, issue.offset)
        if entry is not None and _relevant(entry):
            issues.append(
                {"code": issue.code, "field": issue.field, "source": _source(document, entry)}
            )
    return selected.entries, issues


def _references(entries: tuple[Entry, ...], document: Document):
    grouped: dict[str, list] = defaultdict(list)
    issues = []
    for entry in entries:
        if entry.name in OOB_FIELDS:
            grouped[OOB_FIELDS[entry.name]].append(entry)
    refs = []
    for kind, rows in grouped.items():
        if (
            len(rows) == 1
            and isinstance(rows[0].value, Atom)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", rows[0].value.text)
        ):
            refs.append(
                {"kind": kind, "name": rows[0].value.text, "source": _source(document, rows[0])}
            )
        else:
            issues.append(
                {
                    "code": "ambiguous_oob_reference",
                    "kind": kind,
                    "source": _source(document, rows[0]),
                }
            )
    if "land" not in grouped:
        issues.append({"code": "missing_land_oob_reference", "source": _source(document)})
    return refs, issues


def _template_summary(template: Record, equipment: Record):
    resolved = summarize_template_requirements(template, equipment)
    fields = ("base_equipment", "base_manpower", "base_training_days", "unit_counts", "unknowns")
    return {
        "name": template.get("name"),
        **{field: resolved[field] for field in fields},
        "base_requirements_complete": resolved["base_requirements_complete"],
        "unit_sources": [
            {
                "unit": unit["unit"],
                "sources": [definition.get("source") for definition in unit["definitions"]],
            }
            for unit in resolved["units"]
        ],
        "_units": resolved["units"],
    }


def _template_index(profile: Record, oob_name: str, equipment: Record, document: Document):
    candidates = [
        row
        for row in profile.get("oob_candidates", ())
        if row["source"]["path"].endswith(f"/{oob_name}.txt")
    ]
    templates = []
    if len(candidates) != 1:
        return templates, {"code": "missing_or_ambiguous_imported_template_source", "oob": oob_name}
    if candidates[0]["source"].get("sha256") != document.sha256:
        return templates, {"code": "template_source_hash_mismatch", "oob": oob_name}
    for template in candidates[0].get("templates", ()):
        templates.append(
            {
                **_template_summary(template, equipment),
                "source": {**candidates[0]["source"], "line": template["line"]},
            }
        )
    return templates, None


def _factor(block: Block, field: str, default=None):
    value = _one(block, field)
    if not block.named(field):
        return {
            "value": default,
            "origin": "documented_default" if default is not None else "unknown",
            "rule_source": RULE_SOURCE,
        }
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return {"value": None, "origin": "invalid_or_ambiguous_declaration"}
    return {"value": value, "origin": "declared"}


def _forced_equipment(document: Document, division: Block):
    return [
        {
            "type": entry.name,
            "owner": _one(entry.value, "owner"),
            "creator": _defaulted(entry.value, "creator", _one(entry.value, "owner")),
            "amount": _one(entry.value, "amount"),
            "version_name": _one(entry.value, "version_name"),
            "source": _source(document, entry),
        }
        for container in _blocks(division, "force_equipment_variants")
        for entry in container.entries
        if isinstance(entry.value, Block) and entry.operator == "="
    ]


def _archetype(type_id: str, equipment: Record):
    records = [row for row in equipment.get("equipment", ()) if row.get("id") == type_id]
    if len(records) != 1:
        return None
    values = [row["value"] for row in records[0]["declarations"] if row["field"] == "archetype"]
    if len(values) == 1:
        return values[0]
    archetype = [
        row["value"] for row in records[0]["declarations"] if row["field"] == "is_archetype"
    ]
    return type_id if archetype == [True] else None


def _scaled_equipment(template: Record, factor):
    if factor is None or template["base_equipment"] is None:
        return None, []
    ratio = Fraction(str(factor))
    totals: Counter = Counter()
    uncertain = set()
    for unit in template["_units"]:
        for type_id, amount in unit["base_equipment"].items():
            target = Fraction(str(amount)) * ratio
            if target.denominator != 1:
                uncertain.add(type_id)
            totals[type_id] += target * unit["count"]
    known = {
        type_id: None if type_id in uncertain else int(amount) for type_id, amount in totals.items()
    }
    return known, [
        {"code": "equipment_rounding_unverified", "equipment": name} for name in sorted(uncertain)
    ]


def _apply_forced(quantities, forced: list, equipment: Record, factor):
    issues = []
    seen = set()
    if quantities is None:
        return issues
    for row in forced:
        family = _archetype(row["type"], equipment)
        row["archetype"] = family
        if family is None or family not in quantities:
            issues.append({"code": "forced_equipment_family_unresolved", "equipment": row["type"]})
            continue
        if family in seen:
            quantities[family] = None
            issues.append({"code": "multiple_forced_variants_unresolved", "equipment": family})
            continue
        seen.add(family)
        if row["amount"] is not None:
            amount = row["amount"]
            valid = isinstance(amount, int) and not isinstance(amount, bool) and amount >= 0
            if (
                valid
                and factor == 1
                and quantities[family] is not None
                and amount <= quantities[family]
            ):
                quantities[family] = amount
            else:
                quantities[family] = None
                issues.append(
                    {"code": "forced_amount_factor_interaction_unresolved", "equipment": family}
                )
    return issues


def _division(document: Document, block: Block, index: int, templates: list, equipment: Record):
    name = _one(block, "division_template")
    matches = [i for i, template in enumerate(templates) if template["name"] == name]
    factors = {
        field: _factor(block, field, default)
        for field, default in (
            ("start_equipment_factor", 1),
            ("start_experience_factor", 0),
            ("start_manpower_factor", None),
        )
    }
    forced = _forced_equipment(document, block)
    quantities, issues = None, []
    template_index = matches[0] if len(matches) == 1 else None
    if template_index is None:
        issues.append({"code": "missing_or_ambiguous_division_template", "template": name})
    else:
        factor = factors["start_equipment_factor"]["value"]
        quantities, issues = _scaled_equipment(templates[template_index], factor)
        issues.extend(_apply_forced(quantities, forced, equipment, factor))
    return {
        "index": index,
        "name": _one(block, "name"),
        "name_group": _flat_blocks(document, block, "division_name"),
        "template": name,
        "template_index": template_index,
        "location": _one(block, "location"),
        "source": _source(document, block),
        **factors,
        "equipment_by_archetype": quantities,
        "forced_equipment": forced,
        "manpower_allocated": None,
        "manpower_status": "requires_available_reserve"
        if factors["start_manpower_factor"]["value"] is None
        else "declared_factor_requires_reserve_resolution",
        "unknowns": issues,
    }


def _production(document: Document, entry: Entry, tag: str, kind: str, incomplete: bool):
    assert isinstance(entry.value, Block)
    fields = (
        "requested_factories",
        "progress",
        "efficiency",
        "amount",
        "name",
        "industrial_manufacturer",
    )
    values = {field: _one(entry.value, field) for field in fields}
    equipment_blocks = _blocks(entry.value, "equipment")
    equipment = equipment_blocks[0] if len(equipment_blocks) == 1 else None
    resolved = {
        "requested_factories": values["requested_factories"]
        if isinstance(values["requested_factories"], int) and _number(values["requested_factories"])
        else None,
        "progress_fraction": values["progress"] if _number(values["progress"], 1) else None,
        "efficiency_ratio": values["efficiency"] / 100
        if _number(values["efficiency"], 100)
        else None,
    }
    return {
        "source": _source(document, entry),
        "source_kind": kind,
        "parent_incomplete": incomplete,
        "equipment": {
            field: _one(equipment, field) for field in ("type", "creator", "version_name")
        }
        if equipment is not None
        else None,
        **values,
        "efficiency_units": "percent_0_to_100",
        "progress_units": "fraction_of_one_item",
        "producer_country": tag,
        "assigned_factories": None,
        "resolved_literals": resolved,
        "unknown_defaults": [
            field
            for field in ("requested_factories", "progress", "efficiency")
            if values[field] is None
        ],
    }


def _variant(document: Document, entry: Entry, tag: str):
    assert isinstance(entry.value, Block)
    return {
        "country": tag,
        "name": _one(entry.value, "name"),
        "type": _one(entry.value, "type"),
        "source": _source(document, entry),
        "declarations": _declarations(document, entry.value),
        "modules": _flat_blocks(document, entry.value, "modules"),
        "upgrades": _flat_blocks(document, entry.value, "upgrades"),
    }


def _stockpile(document: Document, entry: Entry, tag: str):
    assert isinstance(entry.value, Block)
    return {
        "type": _one(entry.value, "type"),
        "requested_change": _one(entry.value, "amount"),
        "producer": _defaulted(entry.value, "producer", tag),
        "variant_name": _one(entry.value, "variant_name"),
        "source": _source(document, entry),
        "applied_change": None,
        "eligibility_resolved": False,
    }


def _collect_effects(document, entries, report, tag, kind, incomplete=False):
    handlers = {
        "add_equipment_production": (
            "production_lines",
            lambda e: _production(document, e, tag, kind, incomplete),
        ),
        "create_equipment_variant": ("variants", lambda e: _variant(document, e, tag)),
        "add_equipment_to_stockpile": ("stockpile_changes", lambda e: _stockpile(document, e, tag)),
    }
    for entry in entries:
        if entry.name in LOGISTICS_FIELDS:
            report["logistics_declarations"].append(
                {
                    "field": entry.name,
                    "value": entry.value.literal() if isinstance(entry.value, Atom) else None,
                    "operator": entry.operator,
                    "source": _source(document, entry),
                    "resolved_inventory": None,
                }
            )
        if entry.name in handlers and isinstance(entry.value, Block):
            key, handler = handlers[entry.name]
            report[key].append(handler(entry))
        elif entry.name not in {
            *OOB_FIELDS,
            "division",
            "division_template",
            "units",
            "instant_effect",
        } and _relevant(entry):
            report["unhandled_army_effects"].append(
                {"field": entry.name, "source": _source(document, entry)}
            )


def _process_oob(reference, document, profile, equipment, context, partial, report):
    entries, issues = _select(document, context)
    report["blockers"].extend(issues)
    report["sources"].append(_source(document))
    if reference["kind"] == "land":
        templates, issue = _template_index(profile, reference["name"], equipment, document)
        report["templates"] = templates
        if issue:
            report["blockers"].append(issue)
        divisions = []
        for entry in entries:
            if entry.name != "units" or not isinstance(entry.value, Block):
                continue
            units, issues = _select(document, context, entry.value.entries)
            report["blockers"].extend(issues)
            divisions.extend(
                unit.value
                for unit in units
                if unit.name == "division" and isinstance(unit.value, Block)
            )
            _collect_effects(document, units, report, profile["tag"], "land")
        report["land_roster_source_loaded"] = True
        report["divisions"] = [
            _division(document, block, i, templates, equipment) for i, block in enumerate(divisions)
        ]
    _collect_effects(document, entries, report, profile["tag"], reference["kind"])
    for entry in entries:
        if entry.name == "instant_effect" and isinstance(entry.value, Block):
            effects, issues = _select(document, context, entry.value.entries)
            report["blockers"].extend(issues)
            _collect_effects(document, effects, report, profile["tag"], reference["kind"])
    effects, issues = _select(document, context, partial)
    report["blockers"].extend(issues)
    _collect_effects(document, effects, report, profile["tag"], reference["kind"], incomplete=True)


def _sum_requirements(divisions, templates):
    equipment: Counter = Counter()
    manpower = 0
    unknown_equipment = unknown_manpower = unresolved = 0
    for division in divisions:
        index = division["template_index"]
        template = templates[index] if index is not None else None
        if template is None:
            unresolved += 1
            unknown_equipment += 1
            unknown_manpower += 1
            continue
        if template["base_equipment"] is None:
            unknown_equipment += 1
        else:
            equipment.update(template["base_equipment"])
        if template["base_manpower"] is None:
            unknown_manpower += 1
        else:
            manpower += template["base_manpower"]
        unresolved += template["base_equipment"] is None or template["base_manpower"] is None
    return {
        "full_equipment_requirements": dict(equipment) if not unknown_equipment else None,
        "full_manpower_requirement": manpower if not unknown_manpower else None,
        "divisions_with_unresolved_requirements": unresolved,
    }


def resolve_starting_army(
    country_profile: Record,
    equipment_payload: Record,
    country_document: Document,
    oob_documents: Mapping[str, Document],
    context: SelectionContext,
    *,
    partial_effects: Mapping[str, tuple[Entry, ...]] | None = None,
    tutorial: bool | None = None,
) -> dict:
    """Resolve selected roster/base equipment targets and preserve material unknowns.

    Documents are keyed by OOB name, while recovered children are keyed by their
    source path. Source hashes are unchanged. Manpower reserves, variant combat
    stats, factory assignment and startup effects outside supplied documents are
    not invented. Equipment payload can be an explicitly sourced patch overlay.
    """
    if country_profile["source"].get("sha256") != country_document.sha256:
        raise ValueError("Country profile and source document hashes differ")
    if tutorial is not None:
        context = replace(context, tutorial=tutorial)
    entries, issues = _select(country_document, context)
    references, ref_issues = _references(entries, country_document)
    report: dict[str, Any] = {
        "schema_version": 1,
        "country": country_profile["tag"],
        "start": context.start.to_dict(),
        "tutorial": context.tutorial,
        "semantics": (
            "Source roster and base allocation targets. Equipment identity/eligibility, "
            "fractional rounding, manpower reserves and unhandled startup effects can prevent "
            "these targets from being a resolved in-game inventory. Spawned equipment is not "
            "deducted from reserve stockpiles."
        ),
        "rule_source": RULE_SOURCE,
        "sources": [_source(country_document)],
        "selected_oobs": references,
        "land_roster_source_loaded": False,
        "templates": [],
        "divisions": [],
        "production_lines": [],
        "variants": [],
        "stockpile_changes": [],
        "logistics_declarations": [],
        "stockpile_totals": None,
        "blockers": [*issues, *ref_issues],
        "unhandled_army_effects": [],
        "fully_resolved_starting_army": False,
    }
    _collect_effects(country_document, entries, report, country_profile["tag"], "country")
    for reference in references:
        document = oob_documents.get(reference["name"])
        if document is None:
            report["blockers"].append({"code": "missing_oob_document", "oob": reference["name"]})
            continue
        partial = (partial_effects or {}).get(document.source, ())
        _process_oob(
            reference, document, country_profile, equipment_payload, context, partial, report
        )
    report["summary"] = {
        "division_count": len(report["divisions"]),
        "template_count": len(report["templates"]),
        "production_line_count": len(report["production_lines"]),
        "variant_count": len(report["variants"]),
        "stockpile_change_count": len(report["stockpile_changes"]),
        **_sum_requirements(report["divisions"], report["templates"]),
        "equipment_allocation_targets_complete": sum(
            row["equipment_by_archetype"] is not None
            and all(v is not None for v in row["equipment_by_archetype"].values())
            for row in report["divisions"]
        ),
        "manpower_allocations_resolved": 0,
    }
    if not report["land_roster_source_loaded"]:
        for field in ("full_equipment_requirements", "full_manpower_requirement"):
            report["summary"][field] = None
    for template in report["templates"]:
        template.pop("_units", None)
    return report
