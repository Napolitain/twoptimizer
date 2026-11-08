"""Resolve sourced base equipment economics through declared archetypes.

The predecessor ``parent`` is not a generic numeric fallback. Designer effects,
country modifiers and production eligibility are separate from resolved base IC
and resource requirements. Missing values never become invented zero defaults.
"""

from collections import Counter, defaultdict
from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

type Record = Mapping[str, Any]

RULE_SOURCES = (
    {
        "id": "equipment_archetype_inheritance",
        "url": "https://hoi4.paradoxwikis.com/index.php?title=Equipment_modding&oldid=104717",
        "mirror": "https://github.com/CooderAtom/hoi4-zh-wiki/blob/9f15dbe333f50742f0afd075bcb5a69c7c2ff39c/site/Equipment_modding.html",
        "rule": (
            "Ordinary equipment inherits general attributes via archetype; "
            "parent denotes its predecessor."
        ),
    },
    {
        "id": "duplicate_archetypes",
        "url": "https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/units/equipment/x_tank_chassis.txt",
        "rule": (
            "Duplicate archetypes/types after their source; for_each excludes the archetype. "
            "Alias/type/variant names are not copied."
        ),
    },
    {
        "id": "upgrade_resource_thresholds",
        "url": "https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/units/equipment/upgrades/land_upgrades.txt#L68",
        "rule": "Upgrade resource thresholds declare total added cost, not cumulative costs.",
    },
)


def _number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(value)
        and value >= 0
    )


def _rows(record: Record, field: str) -> list[dict]:
    return [row for row in record.get("declarations", ()) if row["field"] == field]


def _identifier(record: Record, field: str) -> str | None:
    rows = _rows(record, field)
    if (
        len(rows) == 1
        and isinstance(rows[0]["value"], str)
        and not rows[0]["value"].startswith("@")
    ):
        return rows[0]["value"]
    return None


def _evidence(record: Record, row: Record, field: str) -> dict:
    result = {
        "equipment": record["id"],
        "field": field,
        "source": deepcopy(row.get("definition_source", record.get("source", {}))),
        "line": row.get("line", record.get("line")),
    }
    if "patch_overlay" in row:
        result["patch_overlay"] = deepcopy(row["patch_overlay"])
    if "generated_from" in record:
        result["generated_from"] = deepcopy(record["generated_from"])
    return result


def _unknown(identifier: str, field: str, reason: str) -> dict:
    return {"equipment": identifier, "field": field, "reason": reason}


def _has_unresolved(record: Record, field: str) -> bool:
    return any(row["field"] == field for row in record.get("unresolved_statements", ()))


def _resources(record: Record) -> tuple[dict | None, list[dict], str | None]:
    blocks = record.get("resources", ())
    if len(blocks) != 1:
        return None, [], "ambiguous_resources" if blocks else None
    block = blocks[0]
    if block.get("unresolved_statements"):
        return None, [], "unresolved_resources"
    values, sources = {}, []
    for row in block.get("declarations", ()):
        name, value = row["field"], row["value"]
        if not isinstance(name, str) or name in values or not _number(value):
            return None, [], "ambiguous_or_invalid_resource"
        values[name] = value
        sources.append(_evidence(record, row, "resources"))
    return values, sources or [_evidence(record, block, "resources")], None


def _direct(record: Record, field: str) -> tuple[Any, list[dict], str | None]:
    if field in record.get("economic_blockers", ()):
        return None, [], "unresolved_duplicate_transformation"
    if _has_unresolved(record, field):
        return None, [], "unresolved_declaration"
    if field == "resources":
        return _resources(record)
    rows = _rows(record, field)
    if not rows:
        return None, [], None
    if len(rows) != 1 or not _number(rows[0]["value"]):
        return None, [], "ambiguous_or_invalid_number"
    return rows[0]["value"], [_evidence(record, rows[0], field)], None


def _generation_blockers(duplicate: Record) -> list[str]:
    if not duplicate.get("duplication_details_available"):
        return ["build_cost_ic", "resources"]
    blockers = set()
    for block in duplicate.get("for_each", ()):
        for row in [*block.get("declarations", ()), *block.get("unresolved_statements", ())]:
            if row["field"] in {"build_cost_ic", "resources"}:
                blockers.add(row["field"])
            elif row["field"] not in {"variant_name", "hardness", "air_superiority"}:
                blockers.update(("build_cost_ic", "resources"))
    return sorted(blockers)


def _replace_field(record: dict, name: str, value, line: int | None, source: Record):
    record["declarations"] = [row for row in record["declarations"] if row["field"] != name]
    record["declarations"].append(
        {"field": name, "value": value, "line": line, "definition_source": deepcopy(dict(source))}
    )


def _copy_definition(
    original: Record, duplicate: Record, identifier: str, *, archetype=False
) -> dict:
    result = deepcopy(dict(original))
    result["id"] = identifier
    result["generated_from"] = {
        "equipment": original["id"],
        "declaration": duplicate["id"],
        "source": deepcopy(duplicate.get("source", {})),
        "line": duplicate.get("line"),
    }
    if archetype:
        result["economic_blockers"] = [
            field for field in ("build_cost_ic", "resources") if _has_unresolved(duplicate, field)
        ]
        for field in ("build_cost_ic", "module_slots", "is_buildable", "active"):
            overrides = _rows(duplicate, field)
            if overrides:
                result["declarations"] = [
                    row for row in result["declarations"] if row["field"] != field
                ]
                result["declarations"].extend(
                    {**row, "definition_source": deepcopy(duplicate.get("source", {}))}
                    for row in overrides
                )
        if duplicate.get("resources"):
            result["resources"] = deepcopy(duplicate["resources"])
            for block in result["resources"]:
                block["definition_source"] = deepcopy(duplicate.get("source", {}))
                for row in block["declarations"]:
                    row["definition_source"] = deepcopy(duplicate.get("source", {}))
        return result
    _replace_field(
        result, "archetype", duplicate["id"], duplicate.get("line"), duplicate.get("source", {})
    )
    parent, original_archetype = _identifier(original, "parent"), _identifier(original, "archetype")
    if parent and original_archetype and parent.startswith(original_archetype + "_"):
        _replace_field(
            result,
            "parent",
            duplicate["id"] + parent[len(original_archetype) :],
            duplicate.get("line"),
            duplicate.get("source", {}),
        )
    result["economic_blockers"] = _generation_blockers(duplicate)
    return result


def _expanded_definitions(payload: Record) -> tuple[list[dict], list[dict]]:
    originals = deepcopy(payload.get("equipment", []))
    index = defaultdict(list)
    for record in originals:
        index[record["id"]].append(record)
    generated, diagnostics = [], []
    for duplicate in payload.get("duplicate_archetypes", ()):
        source = _identifier(duplicate, "archetype")
        if source is None or len(index.get(source, ())) != 1:
            diagnostics.append(
                {"equipment": duplicate["id"], "reason": "missing_or_ambiguous_duplicate_source"}
            )
            continue
        generated.append(
            _copy_definition(index[source][0], duplicate, duplicate["id"], archetype=True)
        )
        only = _rows(duplicate, "only_duplicate_archetype")
        if not duplicate.get("duplication_details_available") or (
            only and only[0]["value"] is True
        ):
            continue
        generated.extend(_duplicate_children(originals, duplicate, source))
    return originals + generated, diagnostics


def _duplicate_children(originals: list[dict], duplicate: Record, source: str):
    for original in originals:
        if _identifier(original, "archetype") != source:
            continue
        if not original["id"].startswith(source + "_"):
            continue
        identifier = duplicate["id"] + original["id"][len(source) :]
        yield _copy_definition(original, duplicate, identifier)


class _Resolver:
    def __init__(self, records: list[dict]):
        self.index: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            self.index[record["id"]].append(record)
        self.cache: dict[tuple[str, str], tuple[Any, list[dict], list[dict]]] = {}

    def field(self, identifier: str, field: str, chain: tuple[str, ...] = ()):
        key = identifier, field
        if key in self.cache:
            return self.cache[key]
        if identifier in chain:
            return None, [], [_unknown(identifier, field, "archetype_cycle")]
        records = self.index.get(identifier, ())
        if len(records) != 1:
            reason = "missing_equipment" if not records else "ambiguous_equipment"
            return None, [], [_unknown(identifier, field, reason)]
        record = records[0]
        value, sources, problem = _direct(record, field)
        if problem:
            result = None, sources, [_unknown(identifier, field, problem)]
        elif value is not None:
            result = self._checked_direct(record, field, value, sources, (*chain, identifier))
        else:
            result = self._inherited(record, field, (*chain, identifier))
        self.cache[key] = result
        return result

    def _inherited(self, record: Record, field: str, chain):
        archetype = _identifier(record, "archetype")
        if archetype is None:
            return None, [], [_unknown(record["id"], field, "missing_value_or_archetype")]
        value, sources, unknowns = self.field(archetype, field, chain)
        return (
            value,
            [*sources, _evidence(record, _rows(record, "archetype")[0], "archetype")],
            unknowns,
        )

    def _checked_direct(self, record: Record, field: str, value, sources, chain):
        archetype = _identifier(record, "archetype")
        if field != "resources" or archetype is None:
            return value, sources, []
        inherited, _, unknowns = self.field(archetype, field, chain)
        if unknowns or (
            inherited is not None
            and any(amount and name not in value for name, amount in inherited.items())
        ):
            return (
                None,
                sources,
                [_unknown(record["id"], field, "partial_resource_override_unverified")],
            )
        return value, sources, []

    def modular(self, identifier: str, chain=()) -> bool | None:
        records = self.index.get(identifier, ())
        if len(records) != 1 or identifier in chain:
            return None
        record = records[0]
        layouts = _rows(record, "module_slots")
        if layouts:
            if len(layouts) != 1:
                return None
            if layouts[0]["value"] == "none":
                return False
            return True if layouts[0]["value"] == "inherit" else None
        if _has_unresolved(record, "module_slots"):
            return True
        archetype = _identifier(record, "archetype")
        return self.modular(archetype, (*chain, identifier)) if archetype else False


def _resolved_record(resolver: _Resolver, identifier: str, technologies) -> dict:
    cost, cost_sources, cost_unknowns = resolver.field(identifier, "build_cost_ic")
    resources, resource_sources, resource_unknowns = resolver.field(identifier, "resources")
    unknowns = cost_unknowns + resource_unknowns
    definitions = resolver.index[identifier]
    definition = definitions[0] if len(definitions) == 1 else {}
    archetype_flags = _rows(definition, "is_archetype")
    is_archetype = len(archetype_flags) == 1 and archetype_flags[0]["value"] is True
    return {
        "id": identifier,
        "archetype_id": identifier if is_archetype else _identifier(definition, "archetype"),
        "predecessor_id": _identifier(definition, "parent"),
        "status": "resolved_base"
        if not unknowns
        else "partial"
        if cost is not None or resources is not None
        else "unresolved",
        "base_cost_ic": cost,
        "base_resources": resources,
        "requires_variant": resolver.modular(identifier),
        "field_sources": {"base_cost_ic": cost_sources, "base_resources": resource_sources},
        "unknowns": unknowns,
        "unlocked_by": [
            deepcopy(row) for row in technologies if identifier in row.get("equipment", ())
        ],
        "eligibility_evaluated": False,
    }


def resolve_equipment_catalog(payload: Record, *, technology_records=None) -> dict:
    """Resolve base costs/resources, including supported generated equipment IDs."""
    definitions, generation_diagnostics = _expanded_definitions(payload)
    resolver = _Resolver(definitions)
    technologies = (
        payload.get("technology_unlocks", ()) if technology_records is None else technology_records
    )
    equipment = [
        _resolved_record(resolver, identifier, technologies)
        for identifier in sorted(resolver.index)
    ]
    return {
        "schema_version": 1,
        "semantics": (
            "Base equipment economics only. Country/MIO modifiers, designer variants and "
            "eligibility are separate; the source snapshot remains unverified "
            "against the target patch."
        ),
        "equipment": equipment,
        "counts": {
            "equipment": len(equipment),
            "statuses": dict(Counter(row["status"] for row in equipment)),
            "generated_definitions": len(definitions) - len(payload.get("equipment", ())),
        },
        "generation_diagnostics": generation_diagnostics,
        "rule_sources": deepcopy(RULE_SOURCES),
    }


def _component_economics(record: Record) -> dict:
    result = {
        "id": record["id"],
        "source": deepcopy(record.get("source", {})),
        "line": record.get("line"),
        "declarations": deepcopy(_rows(record, "build_cost_ic")),
        "build_cost_resources": deepcopy(record.get("build_cost_resources", ())),
        "unresolved_statements": deepcopy(record.get("unresolved_statements", ())),
        "conditions": deepcopy(record.get("conditions", ())),
        "max_level": deepcopy(_rows(record, "max_level")),
        "resource_cost_thresholds": deepcopy(record.get("resource_cost_thresholds", ())),
    }
    for field in ("add_stats", "multiply_stats"):
        result[field] = [
            {**deepcopy(block), "declarations": deepcopy(_rows(block, "build_cost_ic"))}
            for block in record.get(field, ())
        ]
    return result


def _valid_level(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _upgrade_level(record: Record, selection: Record) -> tuple[int | None, str | None]:
    level = selection["value"]
    if not _valid_level(level):
        return None, "invalid_upgrade_level"
    limits = _rows(record, "max_level")
    if len(limits) != 1 or not _valid_level(limits[0]["value"]):
        return None, "missing_or_ambiguous_max_level"
    if level > limits[0]["value"]:
        return None, "upgrade_level_exceeds_maximum"
    return level, None


def _selected_resource_threshold(record: Record, level: int) -> tuple[dict | None, str | None]:
    blocks = record.get("resource_cost_thresholds", ())
    if not blocks:
        return None, None
    if len(blocks) != 1 or blocks[0].get("unresolved_statements"):
        return None, "ambiguous_resource_thresholds"
    thresholds = blocks[0].get("thresholds", ())
    levels = [row["level"] for row in thresholds]
    if any(not _valid_level(value) for value in levels) or len(levels) != len(set(levels)):
        return None, "invalid_or_duplicate_resource_threshold"
    applicable = [row for row in thresholds if row["level"] <= level]
    if not applicable:
        return None, None
    selected = max(applicable, key=lambda row: row["level"])
    resources, evidence, problem = _resources({**record, "resources": [selected["resources"]]})
    if problem:
        return None, problem
    return {
        "level": selected["level"],
        "resources": resources,
        "field_sources": evidence,
        "semantics": "total_added_resources_not_cumulative",
    }, None


def _upgrade_effects(record: Record, selection: Record) -> dict:
    """Select sourced upgrade inputs without inventing the designer's aggregate."""
    level, problem = _upgrade_level(record, selection)
    selected = None
    if level is not None:
        selected, problem = _selected_resource_threshold(record, level)
    return {
        "level": level,
        "selected_resource_threshold": selected,
        "status": "selected_inputs" if problem is None else "unresolved_inputs",
        "unknowns": [{"field": "upgrades", "id": record["id"], "reason": problem}]
        if problem
        else [],
        "aggregation_applied": False,
    }


def _variant_components(variant: Record, field: str, definitions) -> tuple[list[dict], list[dict]]:
    index = defaultdict(list)
    for record in definitions:
        index[record["id"]].append(record)
    components, unknowns = [], []
    for block in variant.get(field, ()):
        if block.get("unhandled_fields") or block.get("unresolved_statements"):
            unknowns.append({"field": field, "reason": "unresolved_selection"})
        for row in block.get("declarations", ()):
            identifier = row["value"] if field == "modules" else row["field"]
            if field == "modules" and identifier == "empty":
                continue
            matches = index.get(identifier, ())
            if len(matches) != 1:
                unknowns.append(
                    {"field": field, "id": identifier, "reason": "missing_or_ambiguous_definition"}
                )
            components.append(
                {
                    "selection": deepcopy(row),
                    "definitions": [_component_economics(record) for record in matches],
                }
            )
            if field == "upgrades" and len(matches) == 1:
                effects = _upgrade_effects(matches[0], row)
                components[-1]["selected_effects"] = effects
                unknowns.extend(effects["unknowns"])
    return components, unknowns


def resolve_equipment_variant(
    catalog: Record, variant: Record, *, module_records=(), upgrade_records=()
) -> dict:
    """Resolve cosmetic variants and expose designer economic inputs explicitly.

    Named designer variants retain source-linked module and upgrade records. Their
    combined cost/resources stay unknown until aggregation, limits and rounding
    are established; a chassis cost is never silently used as a designed cost.
    """
    matches = [row for row in catalog["equipment"] if row["id"] == variant.get("type")]
    base = deepcopy(matches[0]) if len(matches) == 1 else None
    modules, module_unknowns = _variant_components(variant, "modules", module_records)
    upgrades, upgrade_unknowns = _variant_components(variant, "upgrades", upgrade_records)
    unknowns = module_unknowns + upgrade_unknowns
    if base is None:
        unknowns.append({"field": "type", "reason": "missing_or_ambiguous_equipment"})
    elif base["status"] != "resolved_base":
        unknowns.append({"field": "type", "reason": "unresolved_base_economics"})
    if modules or upgrades or (base is not None and base["requires_variant"] is not False):
        unknowns.append(
            {"field": "variant_economics", "reason": "designer_aggregation_not_validated"}
        )
    return {
        "name": variant.get("name"),
        "type": variant.get("type"),
        "country": variant.get("country"),
        "source": deepcopy(variant.get("source", {})),
        "status": "resolved_variant_base" if not unknowns else "unresolved_variant",
        "variant_cost_ic": base["base_cost_ic"] if base is not None and not unknowns else None,
        "variant_resources": base["base_resources"] if base is not None and not unknowns else None,
        "base": base,
        "modules": modules,
        "upgrades": upgrades,
        "unknowns": unknowns,
        "country_and_mio_modifiers_applied": False,
        "eligibility_evaluated": False,
    }
