"""Read equipment economics and unlock declarations without executing scripts."""

from hashlib import sha256
from pathlib import Path

from games.hoi4.data_pipeline.syntax import Atom, Block, Document, parse_file, syntax_record

EQUIPMENT_FIELDS = {
    "archetype",
    "parent",
    "build_cost_ic",
    "active",
    "is_archetype",
    "is_buildable",
    "year",
    "only_duplicate_archetype",
    "module_slots",
    "is_frame",
}


def _origin(document: Document, node) -> dict:
    return {"line": document.position(node.span.start)[0]}


def _flat(document: Document, block: Block, *, fields=None) -> dict:
    declarations, unresolved = [], []
    for entry in block.entries:
        if fields is not None and entry.name not in fields:
            continue
        if entry.operator == "=" and isinstance(entry.value, Atom):
            declarations.append(
                {"field": entry.name, "value": entry.value.literal(), **_origin(document, entry)}
            )
        else:
            unresolved.append(
                {"field": entry.name, "operator": entry.operator, **_origin(document, entry)}
            )
    return {
        **_origin(document, block),
        "declarations": declarations,
        "unresolved_statements": unresolved,
    }


def _nested(document: Document, block: Block, name: str) -> list[dict]:
    values = [value for value in block.assignments(name) if isinstance(value, Block)]
    if name == "resource_cost_thresholds":
        return [_thresholds(document, value) for value in values]
    return [_flat(document, value) for value in values]


def _thresholds(document: Document, block: Block) -> dict:
    """Retain complete threshold maps, including invalid syntax for diagnostics."""
    thresholds, unresolved = [], []
    for entry in block.entries:
        if entry.operator == "=" and entry.key is not None and isinstance(entry.value, Block):
            thresholds.append(
                {
                    "level": entry.key.literal(),
                    "resources": _flat(document, entry.value),
                    **_origin(document, entry),
                }
            )
        else:
            unresolved.append(syntax_record(entry.value))
    return {
        **_origin(document, block),
        "thresholds": thresholds,
        "unresolved_statements": unresolved,
    }


def _records(root: Path, paths, container: str, fields=None, nested=()):
    records = []
    for path in sorted(paths):
        document = parse_file(path)
        source = {
            "path": path.relative_to(root).as_posix(),
            "sha256": document.sha256,
            "bytes": path.stat().st_size,
        }
        for body in document.root.assignments(container):
            if not isinstance(body, Block):
                continue
            for entry in body.entries:
                if (
                    entry.operator != "="
                    or not isinstance(entry.value, Block)
                    or entry.name == "limit"
                ):
                    continue
                record = {
                    "id": entry.name,
                    "source": source,
                    **_flat(document, entry.value, fields=fields),
                }
                record.update({name: _nested(document, entry.value, name) for name in nested})
                record["conditions"] = [syntax_record(value) for value in body.assignments("limit")]
                records.append(record)
    return records


def _equipment_records(root: Path, paths, container: str) -> list[dict]:
    records = _records(root, paths, container, EQUIPMENT_FIELDS, ("resources", "for_each"))
    for record in records:
        record["duplication_details_available"] = True
    return records


def _unlocks(root: Path) -> list[dict]:
    result = []
    for path in sorted((root / "common" / "technologies").glob("*.txt")):
        document = parse_file(path)
        for container in document.root.assignments("technologies"):
            if isinstance(container, Block):
                result.extend(_technology_unlocks(root, path, document, container))
    return result


def _technology_unlocks(root: Path, path: Path, document: Document, container: Block):
    rows = []
    for technology in container.entries:
        if technology.operator != "=" or not isinstance(technology.value, Block):
            continue
        for entry in technology.value.named("enable_equipments"):
            if entry.operator == "=" and isinstance(entry.value, Block):
                rows.append(
                    {
                        "technology": technology.name,
                        "equipment": [
                            item.value.text
                            for item in entry.value.entries
                            if item.key is None and isinstance(item.value, Atom)
                        ],
                        "unresolved": [
                            syntax_record(item.value)
                            for item in entry.value.entries
                            if item.key is not None or not isinstance(item.value, Atom)
                        ],
                        "source": {
                            "path": path.relative_to(root).as_posix(),
                            "sha256": document.sha256,
                        },
                        **_origin(document, entry),
                    }
                )
    return rows


def read_equipment_resolution_inputs(source_root: Path | str) -> dict:
    """Return raw economic declarations needed by the separate resolver.

    Repeated stat blocks, conditions and duplicate-archetype transformations are
    retained. Technology references describe unlock relationships, not whether a
    country's research or DLC makes equipment currently available.
    """
    root = Path(source_root)
    directory = root / "common" / "units" / "equipment"
    if not directory.is_dir():
        raise ValueError("Equipment source root must contain common/units/equipment")
    paths = list(directory.glob("*.txt"))
    source_paths = {
        *paths,
        *(directory / "modules").glob("*.txt"),
        *(directory / "upgrades").glob("*.txt"),
        *(root / "common" / "technologies").glob("*.txt"),
    }
    documentation = directory / "_documentation.md"
    if documentation.is_file():
        source_paths.add(documentation)
    return {
        "schema_version": 1,
        "input_sources": [
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in sorted(source_paths)
        ],
        "equipment": _equipment_records(root, paths, "equipments"),
        "duplicate_archetypes": _equipment_records(root, paths, "duplicate_archetypes"),
        "modules": _records(
            root,
            (directory / "modules").glob("*.txt"),
            "equipment_modules",
            nested=("add_stats", "multiply_stats", "build_cost_resources"),
        ),
        "upgrades": _records(
            root,
            (directory / "upgrades").glob("*.txt"),
            "upgrades",
            nested=("cost", "add_stats", "multiply_stats", "resource_cost_thresholds"),
        ),
        "technology_unlocks": _unlocks(root),
    }
