"""HoI4 source syntax and provenance; game semantics are supplied separately."""

from games.hoi4.data_pipeline.inventory import SourceContext, inspect_document, inventory_sources
from games.hoi4.data_pipeline.syntax import (
    Atom,
    Block,
    Document,
    Entry,
    ScriptSyntaxError,
    TaggedBlock,
    parse_bytes,
    parse_file,
    parse_script,
    syntax_record,
)

__all__ = [
    "Atom",
    "Block",
    "Document",
    "Entry",
    "ScriptSyntaxError",
    "SourceContext",
    "TaggedBlock",
    "inspect_document",
    "inventory_sources",
    "parse_bytes",
    "parse_file",
    "parse_script",
    "syntax_record",
]
