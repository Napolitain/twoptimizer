"""Check declared source relationships without selecting gameplay inheritance.

An existing reference is not a resolved equipment type or a runnable scenario.
In particular ``parent``, ``archetype`` and ``duplicate_archetypes`` are separate
relationships; this module never folds them into one guessed override order.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

type Record = Mapping[str, Any]

UNEVALUATED_MECHANICS = (
    "DLC branches, dated history and country/state/scripted effects",
    "Equipment inheritance, duplicate-archetype generation and load order",
    "Equipment variants, designer modules, upgrades and production modifiers",
    "Technology unlocks, ideas, laws, focuses and dynamic modifiers",
    "Existing division equipment, stockpiles, manpower and training state",
    "Hourly construction, production, resources, power and training rules",
)


def _declarations(record: Record, field: str) -> list[Record]:
    return [row for row in record.get("declarations", ()) if row["field"] == field]


def _origin(record: Record) -> dict:
    return {"source": dict(record.get("source", {})), "line": record.get("line")}


def _definition_index(equipment: Record) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = defaultdict(list)
    for section, namespace in (
        ("equipment", "equipment"),
        ("duplicate_archetypes", "equipment"),
        ("units", "unit"),
    ):
        for record in equipment.get(section, ()):
            key = f"{namespace}:{record['id']}"
            index[key].append({"node": key, "kind": section, "record": record})
    return dict(index)


def _reference(source: str, namespace: str, target, relation: str, record: Record) -> dict:
    literal = isinstance(target, str) and not target.startswith(("@", "["))
    return {
        "from": source,
        "to": f"{namespace}:{target}" if literal else None,
        "target_literal": target,
        "relation": relation,
        **_origin(record),
    }


def _equipment_edges(index: Mapping[str, list[dict]]) -> list[dict]:
    edges = []
    for definitions in index.values():
        for definition in definitions:
            record, node = definition["record"], definition["node"]
            if definition["kind"] == "units":
                edges.extend(_unit_edges(node, record))
                continue
            for field in ("parent", "archetype"):
                for row in _declarations(record, field):
                    origin = {**record, "line": row["line"]}
                    relation = (
                        "duplicates_archetype"
                        if definition["kind"] == "duplicate_archetypes"
                        else field
                    )
                    edges.append(_reference(node, "equipment", row["value"], relation, origin))
    return edges


def _unit_edges(node: str, record: Record) -> list[dict]:
    return [
        {
            **_reference(
                node, "equipment", row["field"], "needs_equipment", {**record, "line": row["line"]}
            ),
            "declared_amount": row["value"],
        }
        for block in record.get("need", ())
        for row in block["declarations"]
    ]


def _template_edges(node: str, template: Record, oob: Record) -> list[dict]:
    return [
        _reference(node, "unit", row["unit"], field, {**oob, "line": row["line"]})
        for field in ("regiments", "support")
        for row in template.get(field, ())
    ]


def _country_graph(countries: Iterable[Record]) -> tuple[list[dict], list[dict], list[dict]]:
    nodes, edges, diagnostics = [], [], []
    for country in countries:
        for oob in country.get("oob_candidates", ()):
            prefix = f"{country['tag']}:{oob['source']['path']}"
            diagnostics.extend(
                {"country": country["tag"], **row} for row in oob.get("parse_diagnostics", ())
            )
            for template in oob.get("templates", ()):
                node = f"template:{prefix}:{template['line']}"
                nodes.append(
                    {
                        "node": node,
                        "kind": "template",
                        "id": template["name"],
                        **_origin({**oob, **template}),
                    }
                )
                edges.extend(_template_edges(node, template, oob))
            for production in oob.get("production_lines", ()):
                node = f"production:{prefix}:{production['line']}"
                nodes.append({"node": node, "kind": "production", **_origin({**oob, **production})})
                edges.extend(_production_edges(node, production, oob))
    return nodes, edges, diagnostics


def _production_edges(node: str, production: Record, oob: Record) -> list[dict]:
    return [
        _reference(
            node, "equipment", row["value"], "produces_equipment_type", {**oob, "line": row["line"]}
        )
        for block in production.get("equipment_blocks", ())
        for row in block["declarations"]
        if row["field"] == "type"
    ]


def _reference_issues(index: Mapping[str, list[dict]], edges: list[dict]) -> list[dict]:
    issues = []
    for edge in edges:
        definitions = index.get(edge["to"], ())
        if edge["to"] is None:
            status = "nonliteral_reference"
        elif not definitions:
            status = "missing_reference"
        elif len(definitions) > 1:
            status = "ambiguous_reference"
        else:
            continue
        issues.append({"status": status, **edge})
    return issues


def _cycles(index: Mapping[str, list[dict]], edges: list[dict]) -> list[list[str]]:
    """Find cycles in declared equipment relations, not in runtime effects."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge["from"].startswith("equipment:") and edge["to"] in index:
            adjacency[edge["from"]].append(edge["to"])
    visited, active, path, result = set(), set(), [], []

    def visit(node):
        if node in active:
            result.append([*path[path.index(node) :], node])
            return
        if node in visited:
            return
        visited.add(node)
        active.add(node)
        path.append(node)
        for target in adjacency[node]:
            visit(target)
        path.pop()
        active.remove(node)

    for node in sorted(index):
        visit(node)
    return result


def build_dependency_report(
    equipment: Record, countries: Iterable[Record] = (), *, include_graph: bool = False
) -> dict:
    """Return caller-owned diagnostics for imported facts, with an optional graph."""
    index = _definition_index(equipment)
    nodes, country_edges, diagnostics = _country_graph(countries)
    definitions = [definition for group in index.values() for definition in group]
    nodes[:0] = [
        {
            "node": item["node"],
            "kind": item["kind"],
            "id": item["record"]["id"],
            **_origin(item["record"]),
        }
        for item in definitions
    ]
    edges = [*_equipment_edges(index), *country_edges]
    issues = _reference_issues(index, edges)
    cycles = _cycles(index, edges)
    report = {
        "schema_version": 1,
        "semantics": (
            "Declared source dependencies only; no inheritance, DLC branch or gameplay "
            "effects evaluated."
        ),
        "runnable_scenario_established": False,
        "counts": {
            "definitions": len(definitions),
            "nodes": len(nodes),
            "edges": len(edges),
            "by_kind": dict(Counter(node["kind"] for node in nodes)),
            "reference_issues": dict(Counter(issue["status"] for issue in issues)),
            "cycles": len(cycles),
        },
        "duplicate_definitions": [
            {"node": node, "occurrences": [_origin(item["record"]) for item in group]}
            for node, group in index.items()
            if len(group) > 1
        ],
        "reference_issues": issues,
        "cycles": cycles,
        "source_diagnostics": diagnostics,
        "unevaluated_mechanics": list(UNEVALUATED_MECHANICS),
    }
    if include_graph:
        report["graph"] = {"nodes": nodes, "edges": edges}
    return report


def trace_equipment_field(equipment: Record, identifier: str, field: str) -> dict:
    """List candidate declarations along distinct relations without picking a winner."""
    index = _definition_index(equipment)
    edges = _equipment_edges(index)
    by_origin: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        by_origin[edge["from"]].append(edge)
    pending = [(f"equipment:{identifier}", [])]
    visited, candidates, unresolved = set(), [], []
    while pending:
        node, path = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        definitions = index.get(node, ())
        if len(definitions) != 1:
            unresolved.append(
                {"node": node, "reason": "missing" if not definitions else "ambiguous"}
            )
            continue
        record = definitions[0]["record"]
        candidates.extend(
            {"node": node, "path": path, "declaration": dict(row), **_origin(record)}
            for row in _declarations(record, field)
        )
        pending.extend(
            (edge["to"], [*path, edge["relation"]])
            for edge in by_origin[node]
            if edge["to"] is not None
        )
    return {
        "field": field,
        "equipment": identifier,
        "selection": "not_evaluated",
        "candidates": candidates,
        "unresolved": unresolved,
    }
