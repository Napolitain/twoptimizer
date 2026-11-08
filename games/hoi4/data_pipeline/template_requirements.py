"""Aggregate declared base template needs without evaluating gameplay effects.

Equipment and manpower add across battalions/companies; base training duration
uses the slowest constituent. The latter rule is sourced in the template/training
observations in ``data/public_reference/rules_evidence.json``. Neither these
totals nor a complete literal summary establish an eligible, trained division.
"""

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

type Record = Mapping[str, Any]

SEMANTICS = (
    "Literal base requirements only: equipment and manpower sum across listed units; "
    "base training days use the slowest constituent. Modifiers, eligibility, equipment "
    "substitutions, DLC selection and actual training progress are not resolved. "
    "Unknown fields remain null; this is not a trained or runnable scenario."
)


def _literal_id(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not value.startswith(("@", "["))


def _number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value >= 0
    )


def _scalar(record: Record, field: str, unknowns: list[dict]):
    declarations = [row for row in record.get("declarations", ()) if row["field"] == field]
    unresolved = any(row["field"] == field for row in record.get("unresolved_statements", ()))
    if unresolved:
        reason = "unresolved_declaration"
    elif not declarations:
        reason = "missing_declaration"
    elif len(declarations) != 1:
        reason = "ambiguous_declaration"
    elif not _number(declarations[0]["value"]):
        reason = "nonliteral_or_invalid_number"
    else:
        return declarations[0]["value"]
    unknowns.append({"field": field, "reason": reason})
    return None


def _equipment(record: Record, unknowns: list[dict]) -> dict | None:
    blocks = record.get("need", ())
    unresolved = any(row["field"] == "need" for row in record.get("unresolved_statements", ()))
    if len(blocks) != 1 or unresolved:
        reason = "missing_need" if not blocks else "ambiguous_or_unresolved_need"
        unknowns.append({"field": "need", "reason": reason})
        return None
    block = blocks[0]
    if "declarations" not in block:
        unknowns.append({"field": "need", "reason": "missing_need_declarations"})
        return None
    if block.get("unresolved_statements"):
        unknowns.append({"field": "need", "reason": "unresolved_need"})
        return None
    result = {}
    for row in block.get("declarations", ()):
        field, value = row["field"], row["value"]
        if not _literal_id(field) or not _number(value) or field in result:
            unknowns.append({"field": "need", "reason": "ambiguous_or_nonliteral_need"})
            return None
        result[field] = value
    return result


def _unit_summary(unit: str, occurrences: list[dict], definitions: list[Record]) -> dict:
    unknowns: list[dict] = []
    summary = {
        "unit": unit,
        "count": len(occurrences),
        "occurrences": occurrences,
        "definitions": deepcopy(definitions),
        "base_equipment": None,
        "base_manpower": None,
        "base_training_days": None,
        "unknowns": unknowns,
    }
    if not _literal_id(unit) or len(definitions) != 1:
        reason = "nonliteral_unit" if not _literal_id(unit) else "missing_unit"
        if _literal_id(unit) and len(definitions) > 1:
            reason = "ambiguous_unit"
        unknowns.append({"field": "unit", "reason": reason})
        return summary
    record = definitions[0]
    summary.update(
        base_equipment=_equipment(record, unknowns),
        base_manpower=_scalar(record, "manpower", unknowns),
        base_training_days=_scalar(record, "training_time", unknowns),
    )
    return summary


def _composition(template: Record) -> tuple[dict[str, list[dict]], list[dict]]:
    occurrences: dict[str, list[dict]] = defaultdict(list)
    unknowns = []
    for group in ("regiments", "support"):
        rows = template.get(group)
        if not isinstance(rows, (list, tuple)):
            unknowns.append({"field": group, "reason": "missing_or_invalid_composition"})
            continue
        for row in rows:
            unit = row.get("unit")
            if not isinstance(unit, str):
                unknowns.append({"field": group, "reason": "nonliteral_unit"})
                continue
            occurrences[unit].append({"group": group, **deepcopy(row)})
    if not occurrences:
        unknowns.append({"field": "template", "reason": "empty_composition"})
    if template.get("unresolved_statements"):
        unknowns.append({"field": "template", "reason": "unresolved_template_statements"})
    return dict(occurrences), unknowns


def _total(units: list[dict], field: str):
    if any(unit[field] is None for unit in units):
        return None
    if field == "base_training_days":
        return max(unit[field] for unit in units)
    if field == "base_manpower":
        return sum(unit["count"] * unit[field] for unit in units)
    result = {}
    for unit in units:
        for equipment, amount in unit[field].items():
            result[equipment] = result.get(equipment, 0) + unit["count"] * amount
    return result


def summarize_template_requirements(template: Record, equipment_payload: Record) -> dict:
    """Return caller-owned base requirements and evidence for one imported template.

    Per-unit quantities describe one battalion/company; top-level quantities
    include its occurrence count. A missing or ambiguous contributor makes that
    entire aggregate unknown, while independent known aggregates remain useful.
    The enclosing OOB record supplies the template's source/branch identity.
    """
    index: dict[str, list[Record]] = defaultdict(list)
    for definition in equipment_payload.get("units", ()):
        index[definition["id"]].append(definition)
    occurrences, composition_unknowns = _composition(template)
    units = [_unit_summary(unit, rows, index.get(unit, [])) for unit, rows in occurrences.items()]
    unknowns = [
        *composition_unknowns,
        *({"unit": unit["unit"], **issue} for unit in units for issue in unit["unknowns"]),
    ]
    return {
        "schema_version": 1,
        "kind": "base_template_requirements",
        "template": deepcopy(
            {key: value for key, value in template.items() if key != "base_requirements"}
        ),
        "semantics": SEMANTICS,
        "aggregation_rule_evidence": "rules_evidence.json#training.duration",
        "source_repository": equipment_payload.get("source_repository"),
        "source_revision": equipment_payload.get("source_revision"),
        "base_requirements_complete": not unknowns,
        "effective_requirements_resolved": False,
        "unit_counts": {unit: len(rows) for unit, rows in occurrences.items()},
        **{
            field: None if composition_unknowns else _total(units, field)
            for field in ("base_equipment", "base_manpower", "base_training_days")
        },
        "units": units,
        "unknowns": unknowns,
    }
