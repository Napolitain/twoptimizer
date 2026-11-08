"""Conservative history-branch selection; game effects are never executed.

Logic follows the pinned wiki's Triggers and Country creation documentation:
https://github.com/thelight0211/hoi4-wiki/tree/1477082f0088e228c26266ca08893890690ba43d
NOT is NOR over its children. Dated history requires a strictly later start.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from games.hoi4.data_pipeline.syntax import Atom, Block, Document, Entry
from games.hoi4.planning.time import CampaignDate


class Truth(StrEnum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SelectionContext:
    start: CampaignDate
    known_dlcs: frozenset[str]
    enabled_dlcs: frozenset[str]

    def __post_init__(self):
        if not isinstance(self.start, CampaignDate):
            raise ValueError("History selection requires an explicit CampaignDate start")
        if not isinstance(self.known_dlcs, frozenset) or not isinstance(
            self.enabled_dlcs, frozenset
        ):
            raise ValueError("DLC identifiers must be immutable frozensets")
        if not self.enabled_dlcs <= self.known_dlcs:
            raise ValueError("Enabled DLC identifiers must be explicitly catalogued")


@dataclass(frozen=True, slots=True)
class SelectionIssue:
    code: str
    field: str | None
    offset: int


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    field: str | None
    outcome: Truth
    offset: int


@dataclass(frozen=True, slots=True)
class Selection:
    entries: tuple[Entry, ...]
    blockers: tuple[SelectionIssue, ...]
    decisions: tuple[SelectionDecision, ...]


def _truth(value: bool) -> Truth:
    return Truth.TRUE if value else Truth.FALSE


def _combine(values: tuple[Truth, ...], mode: str) -> Truth:
    decisive = Truth.FALSE if mode == "and" else Truth.TRUE
    if decisive in values:
        result = decisive
    elif Truth.UNKNOWN in values:
        result = Truth.UNKNOWN
    else:
        result = Truth.TRUE if mode == "and" else Truth.FALSE
    if mode != "not" or result == Truth.UNKNOWN:
        return result
    return Truth.FALSE if result == Truth.TRUE else Truth.TRUE


def _date_trigger(entry: Entry, context: SelectionContext) -> Truth:
    if not isinstance(entry.value, Atom) or entry.operator not in {"<", ">"}:
        return Truth.UNKNOWN
    try:
        date = CampaignDate.parse(entry.value.text)
    except ValueError:
        return Truth.UNKNOWN
    return _truth(context.start < date if entry.operator == "<" else context.start > date)


def evaluate_trigger(entry: Entry, context: SelectionContext) -> Truth:
    """Unknown identifiers and unsupported predicates never become true by default."""
    name = (entry.name or "").lower()
    if name in {"date", "has_start_date"}:
        return _date_trigger(entry, context)
    if entry.operator != "=":
        return Truth.UNKNOWN
    if name in {"and", "or", "not"} and isinstance(entry.value, Block):
        return evaluate_guard(entry.value, context, mode=name)
    if not isinstance(entry.value, Atom):
        return Truth.UNKNOWN
    if name == "has_dlc" and entry.value.text in context.known_dlcs:
        return _truth(entry.value.text in context.enabled_dlcs)
    if name == "always" and isinstance(entry.value.literal(), bool):
        return _truth(entry.value.literal() is True)
    return Truth.UNKNOWN


def evaluate_guard(block: Block, context: SelectionContext, *, mode: str = "and") -> Truth:
    if mode not in {"and", "or", "not"}:
        raise ValueError("Unknown boolean guard mode")
    return _combine(tuple(evaluate_trigger(entry, context) for entry in block.entries), mode)


def _name(entry: Entry) -> str:
    return (entry.name or "").lower()


def _alternatives(entries: tuple[Entry, ...], index: int):
    end = index + 1
    while end < len(entries) and _name(entries[end]) in {"else", "else_if"}:
        end += 1
    return entries[index:end], end


def _unattached_alternatives(entries: tuple[Entry, ...]) -> tuple[Entry, ...]:
    """An inner if owns its adjacent alternatives, even inside a legacy outer if."""
    result = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        if _name(entry) == "if":
            _, index = _alternatives(entries, index)
            continue
        if _name(entry) in {"else", "else_if"}:
            result.append(entry)
        index += 1
    return tuple(result)


class _Selector:
    def __init__(self, context: SelectionContext):
        self.context = context
        self.entries: list[Entry] = []
        self.blockers: list[SelectionIssue] = []
        self.decisions: list[SelectionDecision] = []

    def issue(self, code: str, entry: Entry):
        self.blockers.append(SelectionIssue(code, entry.name, entry.span.start))

    def walk(self, entries: tuple[Entry, ...]):
        index = 0
        while index < len(entries):
            entry = entries[index]
            index += 1
            if _name(entry) == "if":
                chain, index = _alternatives(entries, index - 1)
                self.chain(chain)
            elif _name(entry) in {"else", "else_if"}:
                self.issue("orphan_alternative", entry)
            elif entry.name and re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", entry.name):
                self.dated(entry)
            else:
                self.entries.append(entry)

    def dated(self, entry: Entry):
        if not isinstance(entry.value, Block) or entry.operator != "=":
            self.issue("invalid_dated_history", entry)
            return
        try:
            date = CampaignDate.parse(entry.name or "")
        except ValueError:
            self.issue("invalid_dated_history", entry)
            return
        outcome = _truth(self.context.start > date)
        self.decisions.append(SelectionDecision(entry.name, outcome, entry.span.start))
        if outcome == Truth.TRUE:
            self.walk(entry.value.entries)

    def chain(self, chain: tuple[Entry, ...]):
        first = chain[0]
        if not isinstance(first.value, Block):
            self.issue("invalid_if_block", first)
            return
        nested = _unattached_alternatives(first.value.entries)
        if nested and len(chain) > 1:
            self.issue("mixed_alternative_placement", first)
            return
        alternatives = (first, *nested) if nested else chain
        if any(_name(e) == "else" for e in alternatives[:-1]):
            self.issue("alternative_after_else", first)
            return
        for branch in alternatives:
            outcome = self.branch_guard(branch)
            self.decisions.append(SelectionDecision(branch.name, outcome, branch.span.start))
            if outcome == Truth.UNKNOWN:
                self.issue("unknown_or_invalid_guard", branch)
                return
            if outcome == Truth.TRUE:
                self.branch_body(branch, nested if branch is first else ())
                return

    def branch_guard(self, branch: Entry) -> Truth:
        if not isinstance(branch.value, Block) or branch.operator != "=":
            return Truth.UNKNOWN
        if _name(branch) == "else":
            return Truth.UNKNOWN if branch.value.named("limit") else Truth.TRUE
        limits = tuple(e for e in branch.value.entries if _name(e) == "limit")
        if len(limits) != 1 or limits[0].operator != "=" or not isinstance(limits[0].value, Block):
            return Truth.UNKNOWN
        return evaluate_guard(limits[0].value, self.context)

    def branch_body(self, branch: Entry, alternatives: tuple[Entry, ...]):
        assert isinstance(branch.value, Block)
        ignored = {entry.span.start for entry in alternatives}
        self.walk(
            tuple(
                e
                for e in branch.value.entries
                if _name(e) != "limit" and e.span.start not in ignored
            )
        )


def select_history(document: Document, context: SelectionContext) -> Selection:
    """Return source statement candidates, preserving unknown-parent blockers.

    This selects control flow only. Every returned statement still needs an
    owning game-effect implementation before it can change scenario state.
    """
    selector = _Selector(context)
    selector.walk(document.root.entries)
    return Selection(tuple(selector.entries), tuple(selector.blockers), tuple(selector.decisions))


def all_gameplay_context(start: CampaignDate, catalog_path: Path | str) -> SelectionContext:
    """Use only explicit gameplay identifiers from a caller-supplied sourced catalog."""
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    enabled = frozenset(row["script_id"] for row in catalog["dlcs"] if row["gameplay"] is True)
    return SelectionContext(start, enabled, enabled)
