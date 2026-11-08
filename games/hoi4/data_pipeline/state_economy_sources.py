"""Small source supplements for state slots and province-level landmark effects."""

from pathlib import Path

from games.hoi4.data_pipeline.syntax import Atom, Block, Document, parse_file


def _line(document: Document, node) -> int:
    return document.position(node.span.start)[0]


def _flat(document: Document, block: Block) -> list[dict]:
    return [
        {"field": entry.name, "value": entry.value.literal(), "line": _line(document, entry)}
        for entry in block.entries
        if entry.operator == "=" and isinstance(entry.value, Atom)
    ]


def _blocks(block: Block, name: str) -> list[Block]:
    return [value for value in block.assignments(name) if isinstance(value, Block)]


def _conditions(document: Document, block: Block, name: str) -> list[dict]:
    return [
        {"script": document.fragment(value), "line": _line(document, value)}
        for value in block.assignments(name)
    ]


def _placements(document: Document, history: Block) -> list[dict]:
    result = []
    for buildings in _blocks(history, "buildings"):
        for province in buildings.entries:
            if not (province.name or "").isdigit() or not isinstance(province.value, Block):
                continue
            for entry in province.value.entries:
                if entry.operator != "=":
                    continue
                result.append(_placement(document, province.name, entry))
    return result


def _placement(document: Document, province, entry) -> dict:
    scalar = isinstance(entry.value, Atom)
    return {
        "province_id": int(province),
        "building_id": entry.name,
        "line": _line(document, entry),
        "declarations": (
            [{"field": "level", "value": entry.value.literal(), "line": _line(document, entry)}]
            if scalar
            else _flat(document, entry.value)
            if isinstance(entry.value, Block)
            else []
        ),
        "conditions": (
            _conditions(document, entry.value, "allowed") if isinstance(entry.value, Block) else []
        ),
    }


def _modifier_blocks(document: Document, block: Block) -> list[dict]:
    result = []
    for modifier in _blocks(block, "country_modifiers"):
        controllers = _blocks(modifier, "enable_for_controllers")
        tags = [
            entry.value.literal()
            for controller in controllers
            for entry in controller.entries
            if entry.key is None and isinstance(entry.value, Atom)
        ]
        result.append(
            {
                "line": _line(document, modifier),
                "controllers": tags,
                "controller_lists": len(controllers),
                "controllers_resolved": len(controllers) <= 1
                and len(tags) == sum(len(value.entries) for value in controllers)
                and all(isinstance(tag, str) for tag in tags),
                "modifiers": [
                    declaration
                    for values in _blocks(modifier, "modifiers")
                    for declaration in _flat(document, values)
                ],
            }
        )
    return result


def read_state_economy_inputs(source_root: Path | str, country_profile: dict) -> dict:
    """Read factual supplements only; no condition or effect is executed here."""
    root = Path(source_root)
    states, catalog, sources = [], [], {}
    for state in country_profile["states"]:
        path = root / state["source"]["path"]
        document = parse_file(path)
        source = {
            "path": state["source"]["path"],
            "sha256": document.sha256,
            "bytes": path.stat().st_size,
        }
        sources[source["path"]] = source
        for block in _blocks(document.root, "state"):
            states.append(
                {
                    "id": state["id"],
                    "source": source,
                    "state_declarations": _flat(document, block),
                    "province_buildings": [
                        row
                        for history in _blocks(block, "history")
                        for row in _placements(document, history)
                    ],
                }
            )
    for path in sorted((root / "common" / "buildings").glob("*.txt")):
        document = parse_file(path)
        source = {
            "path": path.relative_to(root).as_posix(),
            "sha256": document.sha256,
            "bytes": path.stat().st_size,
        }
        sources[source["path"]] = source
        for buildings in _blocks(document.root, "buildings"):
            for entry in buildings.entries:
                if not isinstance(entry.value, Block) or not (entry.name or "").startswith(
                    "landmark_"
                ):
                    continue
                catalog.append(
                    {
                        "id": entry.name,
                        "source": source,
                        "line": _line(document, entry),
                        "conditions": _conditions(document, entry.value, "dlc_allowed"),
                        "country_modifiers": _modifier_blocks(document, entry.value),
                    }
                )
    return {
        "states": states,
        "landmark_definitions": catalog,
        "input_sources": list(sources.values()),
    }
