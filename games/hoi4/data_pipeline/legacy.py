"""Compatibility projections for old display models; never a script evaluator.

The ordered Document remains authoritative. These dictionaries cannot express
script ordering or prerequisite-group logic and must not drive hourly planning.
"""

from collections import defaultdict
from typing import Any

from games.hoi4.data_pipeline.syntax import Atom, Block, TaggedBlock, syntax_record


def legacy_value(value: Atom | Block | TaggedBlock) -> Any:
    if isinstance(value, Atom):
        return value.literal()
    if isinstance(value, TaggedBlock) or value.form == "mixed":
        return syntax_record(value)
    if value.form == "list":
        return [legacy_value(entry.value) for entry in value.entries]
    return legacy_object(value)


def legacy_object(block: Block) -> dict[str, Any]:
    """Retain repeated fields as lists instead of merging their child objects."""
    fields: dict[str, list[Any]] = defaultdict(list)
    for entry in block.entries:
        if entry.name is None:
            continue
        value = legacy_value(entry.value)
        if entry.operator != "=":
            value = {"operator": entry.operator, "value": value}
        fields[entry.name].append(value)
    return {name: values[0] if len(values) == 1 else values for name, values in fields.items()}
