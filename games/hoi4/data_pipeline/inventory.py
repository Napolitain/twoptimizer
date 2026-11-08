"""Deterministic source inventory and factual coverage, without effect execution."""

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path

from games.hoi4.data_pipeline.syntax import (
    Atom,
    Block,
    Document,
    ScriptSyntaxError,
    parse_bytes,
    syntax_record,
)

SEMANTICS = (
    "Syntax and displayed source facts only. Conditions, effects, variables, load-order "
    "overrides and prerequisite-group logic are not evaluated. Parsed is not executable."
)
KNOWN_CATEGORIES = {
    "buildings",
    "state_category",
    "ideas",
    "national_focus",
    "states",
    "countries",
    "equipment",
    "units",
    "technologies",
    "defines",
}
FACT_FIELDS = {
    "building": {
        "base_cost",
        "base_cost_conversion",
        "military_production",
        "general_production",
        "naval_production",
        "infrastructure",
        "province_max",
        "repair_speed_factor",
    },
    "state_category": {"local_building_slots"},
    "idea": {"cost", "removal_cost", "level"},
    "focus": {"id", "cost", "x", "y", "relative_position_id"},
    "shared_focus": {"id", "cost", "x", "y", "relative_position_id"},
}


@dataclass(frozen=True, slots=True)
class SourceContext:
    origin_url: str | None = None
    revision: str | None = None
    game_build: str | None = None
    retrieved_at_utc: str | None = None


def _blocks(block, name):
    return tuple(value for value in block.assignments(name) if isinstance(value, Block))


def _identifier(block):
    ids = block.assignments("id")
    return ids[0].text if len(ids) == 1 and isinstance(ids[0], Atom) else None


def record_blocks(document: Document, category: str):
    """Yield kind, identifier, body and containing group; duplicates stay separate."""
    if category in {"buildings", "state_category"}:
        root_name, kind = (
            ("buildings", "building")
            if category == "buildings"
            else ("state_categories", "state_category")
        )
        for container in _blocks(document.root, root_name):
            for entry in container.entries:
                if (
                    entry.key is not None
                    and entry.operator == "="
                    and isinstance(entry.value, Block)
                ):
                    yield kind, entry.name, entry.value, None
    elif category == "ideas":
        yield from _idea_blocks(document)
    elif category == "national_focus":
        yield from _focus_blocks(document)


def _idea_blocks(document):
    for container in _blocks(document.root, "ideas"):
        for group in container.entries:
            if not isinstance(group.value, Block):
                continue
            for entry in group.value.entries:
                if (
                    entry.key is not None
                    and entry.operator == "="
                    and isinstance(entry.value, Block)
                ):
                    yield "idea", entry.name, entry.value, group.name


def _focus_blocks(document):
    for kind in ("focus", "shared_focus"):
        for block in _blocks(document.root, kind):
            yield kind, _identifier(block), block, None
    for tree in _blocks(document.root, "focus_tree"):
        for block in _blocks(tree, "focus"):
            yield "focus", _identifier(block), block, _identifier(tree)


def _position(document, node):
    line, column = document.position(node.span.start)
    return {"start": node.span.start, "end": node.span.end, "line": line, "column": column}


def _field_record(document, entry):
    return {
        "field": entry.name,
        "operator": entry.operator,
        "location": _position(document, entry),
        "syntax": syntax_record(entry.value),
    }


def _record(document, kind, identifier, block, group):
    facts, remaining = [], []
    for entry in block.entries:
        if (
            entry.name in FACT_FIELDS[kind]
            and entry.operator == "="
            and isinstance(entry.value, Atom)
        ):
            facts.append(_field_record(document, entry))
        else:
            remaining.append(
                {
                    "field": entry.name,
                    "operator": entry.operator,
                    "location": _position(document, entry),
                }
            )
    result = {
        "kind": kind,
        "id": identifier,
        "group": group,
        "location": _position(document, block),
        "facts": facts,
        "unhandled_fields": remaining,
    }
    if kind in {"focus", "shared_focus"}:
        result["prerequisite_groups"] = [
            {"location": _position(document, entry), "syntax": syntax_record(entry.value)}
            for entry in block.named("prerequisite")
        ]
    return result


def inspect_document(document: Document, category: str) -> dict:
    records = [_record(document, *record) for record in record_blocks(document, category)]
    identities = Counter((row["kind"], row["group"], row["id"]) for row in records)
    return {
        "status": "parsed",
        "top_level": [
            {
                "field": entry.name,
                "operator": entry.operator,
                "location": _position(document, entry),
            }
            for entry in document.root.entries
        ],
        "records": records,
        "duplicate_record_ids": [
            {"kind": kind, "group": group, "id": identifier, "occurrences": count}
            for (kind, group, identifier), count in identities.items()
            if count > 1
        ],
        "semantic_execution": "not_implemented",
        "fact_schema": "declared"
        if category in {"buildings", "state_category", "ideas", "national_focus"}
        else "unknown",
    }


def _category(path):
    return next((part for part in reversed(path.parts[:-1]) if part in KNOWN_CATEGORIES), "unknown")


def inspect_file(path: Path, *, relative_to: Path) -> dict:
    relative = path.relative_to(relative_to)
    payload = path.read_bytes()
    category = _category(relative)
    source = {
        "path": relative.as_posix(),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "category": category,
        "utf8_bom": payload.startswith(b"\xef\xbb\xbf"),
    }
    if path.suffix.lower() != ".txt":
        return {
            **source,
            "status": "unsupported_format",
            "reason": "Only Clausewitz .txt syntax is inspected",
            "semantic_execution": "not_implemented",
        }
    try:
        document = parse_bytes(payload, source=relative.as_posix())
        return {**source, **inspect_document(document, category)}
    except ScriptSyntaxError as error:
        return {
            **source,
            "status": "syntax_error",
            "error": str(error),
            "line": error.line,
            "column": error.column,
            "offset": error.offset,
            "semantic_execution": "not_implemented",
        }
    except UnicodeDecodeError as error:
        return {
            **source,
            "status": "encoding_error",
            "error": str(error),
            "byte_offset": error.start,
            "semantic_execution": "not_implemented",
        }


def inventory_sources(root: Path | str, *, context: SourceContext | None = None) -> dict:
    """Inspect every file beneath a supplied source directory, without network I/O."""
    root = Path(root)
    if not root.is_dir():
        raise ValueError("HoI4 source root must be an existing directory")
    sources = [
        inspect_file(path, relative_to=root) for path in sorted(root.rglob("*")) if path.is_file()
    ]
    fingerprints = [(source["path"], source["sha256"]) for source in sources]
    digest = sha256()
    for path, fingerprint in fingerprints:
        digest.update(path.encode("utf-8") + b"\0" + fingerprint.encode("ascii") + b"\n")
    return {
        "schema_version": 1,
        "source_context": asdict(context or SourceContext()),
        "source_set_sha256": digest.hexdigest(),
        "semantics": SEMANTICS,
        "coverage": {
            "files": len(sources),
            "statuses": dict(Counter(source["status"] for source in sources)),
            "categories": dict(Counter(source["category"] for source in sources)),
            "records": dict(
                Counter(
                    record["kind"] for source in sources for record in source.get("records", ())
                )
            ),
            "executed_effects": 0,
            "missing_categories": sorted(
                KNOWN_CATEGORIES - {source["category"] for source in sources}
            ),
        },
        "sources": sources,
    }
