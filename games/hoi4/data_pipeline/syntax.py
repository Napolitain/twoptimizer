"""Ordered Clausewitz syntax with source spans; no game rules are evaluated.

Original text is retained verbatim, including comments and a UTF-8 BOM. Blocks
keep repeated assignments, comparison operators and unkeyed list items rather
than collapsing them into Python dictionaries.
"""

from __future__ import annotations

import hashlib
import math
import re
from bisect import bisect_right
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, NoReturn, cast

type AtomKind = Literal["bare", "quoted", "expression"]


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Atom:
    text: str
    kind: AtomKind
    span: Span

    def literal(self) -> str | int | float | bool:
        """Decode scalar syntax only; variables/dates/expressions remain text."""
        if self.kind != "bare":
            return self.text
        if self.text in {"yes", "no"}:
            return self.text == "yes"
        if re.fullmatch(r"[+-]?\d+", self.text):
            return int(self.text)
        if re.fullmatch(
            r"[+-]?(?:\d+\.\d*|\.\d+|\d+)[eE][+-]?\d+|[+-]?(?:\d+\.\d*|\.\d+)", self.text
        ):
            value = float(self.text)
            return value if math.isfinite(value) else self.text
        return self.text


@dataclass(frozen=True, slots=True)
class Entry:
    key: Atom | None
    operator: str | None
    value: Atom | Block | TaggedBlock
    span: Span

    @property
    def name(self) -> str | None:
        return None if self.key is None else self.key.text


@dataclass(frozen=True, slots=True)
class Block:
    entries: tuple[Entry, ...]
    span: Span

    @property
    def form(self) -> str:
        """Empty braces remain ambiguous, rather than being assumed an object."""
        if not self.entries:
            return "empty"
        keyed = sum(entry.key is not None for entry in self.entries)
        return "object" if keyed == len(self.entries) else "list" if keyed == 0 else "mixed"

    def named(self, name: str) -> tuple[Entry, ...]:
        return tuple(entry for entry in self.entries if entry.name == name)

    def assignments(self, name: str) -> tuple[Atom | Block | TaggedBlock, ...]:
        return tuple(entry.value for entry in self.named(name) if entry.operator == "=")


@dataclass(frozen=True, slots=True)
class TaggedBlock:
    tag: Atom
    block: Block
    span: Span


@dataclass(frozen=True, slots=True)
class Document:
    source: str
    text: str
    sha256: str
    root: Block
    _line_starts: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(
            self,
            "_line_starts",
            (0, *(index + 1 for index, char in enumerate(self.text) if char == "\n")),
        )

    def position(self, offset: int) -> tuple[int, int]:
        """One-based line/column for a character offset, including BOM position."""
        if not 0 <= offset <= len(self.text):
            raise ValueError("Source offset is outside the document")
        line = bisect_right(self._line_starts, offset)
        return line, offset - self._line_starts[line - 1] + 1

    def fragment(self, node: Atom | Entry | Block | TaggedBlock) -> str:
        return self.text[node.span.start : node.span.end]


class ScriptSyntaxError(ValueError):
    def __init__(self, message: str, source: str, text: str, offset: int):
        self.source = source
        self.offset = offset
        self.line = text.count("\n", 0, offset) + 1
        self.column = offset - text.rfind("\n", 0, offset)
        super().__init__(f"{source}:{self.line}:{self.column}: {message}")


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    span: Span


class _Parser:
    def __init__(self, text: str, source: str, *, offset: int = 0):
        self.text, self.source = text, source
        self.offset = offset
        self.tokens = self._tokens()
        self.current = next(self.tokens)

    def error(self, message: str, offset: int | None = None) -> NoReturn:
        raise ScriptSyntaxError(
            message, self.source, self.text, self.offset if offset is None else offset
        )

    def advance(self):
        token = self.current
        self.current = next(self.tokens)
        return token

    def _tokens(self):
        while self.offset < len(self.text):
            char = self.text[self.offset]
            if char.isspace() or (self.offset == 0 and char == "\ufeff"):
                self.offset += 1
            elif char == "#":
                end = self.text.find("\n", self.offset)
                self.offset = len(self.text) if end < 0 else end
            else:
                yield self._token()
        yield _Token("end", "", Span(len(self.text), len(self.text)))

    def _token(self):
        start = self.offset
        char = self.text[start]
        if char in "{}":
            self.offset += 1
            return _Token(char, char, Span(start, self.offset))
        if char in "\"'":
            return self._quoted(char)
        if self.text.startswith("@[", start):
            return self._expression()
        if operator := self._operator(start):
            self.offset += len(operator)
            return _Token("operator", operator, Span(start, self.offset))
        while self.offset < len(self.text) and not self._separator(self.offset):
            self.offset += 1
        if self.offset == start:
            self.error("Unexpected character")
        return _Token("bare", self.text[start : self.offset], Span(start, self.offset))

    def _separator(self, offset):
        return (
            self.text[offset].isspace()
            or self.text[offset] in "{}#\"'"
            or bool(self._operator(offset))
        )

    def _operator(self, offset):
        pair = self.text[offset : offset + 2]
        if pair in {"!=", "<=", ">=", "==", "?=", "+=", "-=", "*=", "/="}:
            return pair
        return self.text[offset] if self.text[offset] in "=<>" else None

    def _quoted(self, quote):
        start = self.offset
        self.offset += 1
        content = []
        while self.offset < len(self.text):
            char = self.text[self.offset]
            self.offset += 1
            if char == quote:
                return _Token("quoted", "".join(content), Span(start, self.offset))
            if char == "\\" and self.offset < len(self.text):
                following = self.text[self.offset]
                if following in {quote, "\\"}:
                    char = following
                    self.offset += 1
            content.append(char)
        self.error("Unterminated quoted string", start)

    def _expression(self):
        start = self.offset
        self.offset += 2
        depth = 1
        while self.offset < len(self.text):
            char = self.text[self.offset]
            self.offset += 1
            depth += (char == "[") - (char == "]")
            if depth == 0:
                return _Token(
                    "expression", self.text[start : self.offset], Span(start, self.offset)
                )
        self.error("Unterminated script expression", start)

    def block(self, *, root=False, depth=0):
        if depth > 200:
            self.error("Script nesting exceeds 200 blocks", self.current.span.start)
        start = 0 if root else self.advance().span.start
        entries = []
        while self.current.kind not in {"}", "end"}:
            entries.append(self.entry(depth))
        if root:
            if self.current.kind != "end":
                self.error("Unexpected closing brace", self.current.span.start)
            end = len(self.text)
        else:
            if self.current.kind != "}":
                self.error("Unclosed block", start)
            end = self.advance().span.end
        return Block(tuple(entries), Span(start, end))

    def atom(self):
        token = self.current
        if token.kind not in {"bare", "quoted", "expression"}:
            self.error("Expected a scalar value", token.span.start)
        self.advance()
        return Atom(token.text, cast(AtomKind, token.kind), token.span)

    def value(self, depth):
        if self.current.kind == "{":
            return self.block(depth=depth + 1)
        atom = self.atom()
        if self.current.kind == "{":
            block = self.block(depth=depth + 1)
            return TaggedBlock(atom, block, Span(atom.span.start, block.span.end))
        return atom

    def entry(self, depth):
        first = self.value(depth)
        if isinstance(first, Atom) and self.current.kind == "operator":
            operator = self.advance().text
            value = self.value(depth)
            return Entry(first, operator, value, Span(first.span.start, value.span.end))
        return Entry(None, None, first, first.span)


def parse_script(text: str, *, source: str = "<memory>") -> Document:
    parser = _Parser(text, source)
    return Document(
        source, text, hashlib.sha256(text.encode("utf-8")).hexdigest(), parser.block(root=True)
    )


def parse_bytes(payload: bytes, *, source: str = "<memory>") -> Document:
    """Decode strictly without dropping a BOM or invalid bytes from the hash."""
    return parse_script(payload.decode("utf-8"), source=source)


def parse_file(path: Path | str) -> Document:
    path = Path(path)
    return parse_bytes(path.read_bytes(), source=str(path))


@dataclass(frozen=True, slots=True)
class RecoveredChildren:
    """Individually complete entries, retaining an incomplete parent's error."""

    entries: tuple[Entry, ...]
    complete: bool
    error: ScriptSyntaxError | None


def recover_complete_children(
    text: str, opening_brace_offset: int, *, source: str = "<memory>"
) -> RecoveredChildren:
    """Inspect balanced children at a known brace without inventing source text.

    ``complete`` means the parent closing brace was encountered. If an entry is
    incomplete it is excluded, along with everything after it. Returned spans
    always address the original input; callers must retain the incomplete-parent
    diagnostic and must not treat recovery as successful whole-file parsing.
    """
    if not 0 <= opening_brace_offset < len(text) or text[opening_brace_offset] != "{":
        raise ValueError("Recovery offset must identify an opening brace")
    entries = []
    try:
        parser = _Parser(text, source, offset=opening_brace_offset + 1)
        while parser.current.kind not in {"}", "end"}:
            entries.append(parser.entry(1))
        if parser.current.kind == "}":
            return RecoveredChildren(tuple(entries), True, None)
        parser.error("Unclosed block", opening_brace_offset)
    except ScriptSyntaxError as error:
        return RecoveredChildren(tuple(entries), False, error)


def syntax_record(value: Atom | Block | TaggedBlock) -> dict:
    """JSON-safe ordered syntax, with character offsets into the original text."""
    span = {"start": value.span.start, "end": value.span.end}
    if isinstance(value, Atom):
        return {"kind": value.kind, "text": value.text, "span": span}
    if isinstance(value, TaggedBlock):
        return {
            "kind": "tagged",
            "tag": syntax_record(value.tag),
            "block": syntax_record(value.block),
            "span": span,
        }
    return {
        "kind": value.form,
        "span": span,
        "entries": [
            {
                "key": None if entry.key is None else syntax_record(entry.key),
                "operator": entry.operator,
                "value": syntax_record(entry.value),
            }
            for entry in value.entries
        ],
    }
