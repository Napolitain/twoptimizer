"""Resolve selected initial economic modifiers without executing campaign scripts.

Idea/technology hook exclusions and modifier scopes are documented in
``docs/hoi4/hoi4-modifier-resolution.md``. Consumer-goods factors multiply individually;
other supported country modifiers add before their owning mechanic uses them.
Unknown branches, scopes and values are retained as blockers, never zero bonuses.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from math import fsum, isfinite, prod
from pathlib import Path
from types import MappingProxyType

from games.hoi4.data_pipeline.selection import (
    SelectionContext,
    Truth,
    evaluate_trigger,
    select_history,
)
from games.hoi4.data_pipeline.syntax import (
    Atom,
    Block,
    Document,
    Entry,
    ScriptSyntaxError,
    Span,
    parse_bytes,
    recover_complete_children,
)

ECONOMIC_MODIFIERS = frozenset(
    {
        "consumer_goods_expected_value",
        "consumer_goods_factor",
        "civilian_factory_use",
        "industrial_capacity_factory",
        "industrial_capacity_dockyard",
        "min_export",
        "local_resources",
        "local_resources_factor",
        "global_building_slots_factor",
        "global_building_slots",
        "production_speed_buildings_factor",
        "production_factory_efficiency_gain_factor",
        "production_factory_max_efficiency_factor",
        "production_factory_start_efficiency_factor",
        "line_change_production_efficiency_factor",
        "production_lack_of_resource_penalty_factor",
        "equipment_conversion_speed",
        "resource_trade_cost_bonus_per_factory",
        "resource_trade_cost_bonus_per_factory_factor",
        "factory_energy_consumption",
        "factory_energy_consumption_factor",
        "factory_energy_consumption_multiplier",
        "energy_production",
        "energy_production_factor",
        "energy_gain_per_coal_factor",
        "energy_gain_factor",
        "coal_production",
        "coal_production_factor",
        "conscription",
        "conscription_factor",
        "mobilization_speed",
        "mobilization_speed_factor",
        "training_time_factor",
        "training_time_army_factor",
        "minimum_training_level",
        "army_training_factor",
        "max_training",
        "max_training_factor",
        "max_training_experience_factor",
        "recruitable_population",
        "recruitable_population_factor",
        "non_core_manpower",
        "non_core_manpower_factor",
        "monthly_population",
        "research_speed_factor",
        "conversion_cost_civ_to_mil_factor",
        "conversion_cost_mil_to_civ_factor",
        "repair_speed_factor",
        "industry_repair_factor",
        "industry_free_repair_factor",
        "fuel_gain_factor",
        "fuel_gain_factor_from_states",
        "max_fuel_factor",
        "cic_construction_boost",
        "cic_construction_boost_factor",
        "cic_bank_capacity_factor",
        "cic_bank_interest",
        "equipment_capture_factor",
        "stability_factor",
        "war_support_factor",
    }
)
SCOPED_ECONOMIC_FIELDS = frozenset({"build_cost_ic", "manpower", "training_time", "resources"})
HISTORY_OPERATIONS = frozenset(
    {
        "add_ideas",
        "remove_ideas",
        "swap_ideas",
        "set_technology",
        "add_dynamic_modifier",
        "remove_dynamic_modifier",
        "set_variable",
        "add_to_variable",
        "subtract_from_variable",
        "multiply_variable",
        "divide_variable",
        "add_country_modifier",
        "recruit_character",
    }
)
IDEA_METADATA = frozenset(
    {
        "picture",
        "name",
        "desc",
        "allowed",
        "allowed_civil_war",
        "allowed_to_remove",
        "visible",
        "available",
        "cancel",
        "cancel_if_invalid",
        "cost",
        "removal_cost",
        "level",
        "default",
        "ai_will_do",
        "on_add",
        "on_remove",
        "do_effect",
        "rule",
        "traits",
        "research_bonus",
    }
)
TECH_METADATA = frozenset(
    {
        "path",
        "folder",
        "ai_will_do",
        "categories",
        "xor",
        "dependencies",
        "allow",
        "allow_branch",
        "available",
        "visible",
        "research_cost",
        "start_year",
        "show_effect_as_desc",
        "enable_equipment",
        "enable_subunits",
        "enable_building",
        "enable_equipments",
        "doctrine",
        "on_research_complete",
        "on_research_complete_limit",
        "show_equipment_icon",
        "enable_equipment_modules",
        "sub_technologies",
        "xp_research_type",
        "xp_unlock_cost",
    }
)


def _economic(field: str | None) -> bool:
    return bool(field) and (
        field in ECONOMIC_MODIFIERS or field.startswith(("production_speed_", "local_resources_"))
    )


def _number(atom: Atom) -> int | float | None:
    value = atom.literal()
    return (
        value
        if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
        else None
    )


def _scalar(block: Block, name: str):
    values = block.assignments(name)
    return values[0].literal() if len(values) == 1 and isinstance(values[0], Atom) else None


@dataclass(frozen=True, slots=True)
class ModifierDefinition:
    document: Document
    entry: Entry
    category: str
    identifier_override: str | None = None

    @property
    def body(self) -> Block:
        assert isinstance(self.entry.value, Block)
        return self.entry.value

    @property
    def identifier(self) -> str:
        if self.identifier_override is not None:
            return self.identifier_override
        assert self.entry.name is not None
        return self.entry.name


@dataclass(frozen=True, slots=True)
class ModifierCatalog:
    ideas: Mapping[str, tuple[ModifierDefinition, ...]]
    technologies: Mapping[str, tuple[ModifierDefinition, ...]]
    dynamic_modifiers: Mapping[str, tuple[ModifierDefinition, ...]]
    law_categories: frozenset[str]
    parse_diagnostics: tuple[tuple[str, str], ...] = ()
    source_fingerprints: tuple[tuple[str, str, int], ...] = ()
    auxiliary: Mapping[str, Mapping[str, tuple[ModifierDefinition, ...]]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def input_sources(self) -> tuple[dict, ...]:
        """Unique fingerprints for every parsed definition used to build this index."""
        if self.source_fingerprints:
            return tuple(
                {"path": path, "sha256": digest, "bytes": size}
                for path, digest, size in self.source_fingerprints
            )
        documents = {
            definition.document.source: definition.document
            for index in (
                self.ideas,
                self.technologies,
                self.dynamic_modifiers,
                *self.auxiliary.values(),
            )
            for definitions in index.values()
            for definition in definitions
        }
        return tuple(
            {"path": path, "sha256": document.sha256, "bytes": len(document.text.encode("utf-8"))}
            for path, document in sorted(documents.items())
        )


def _definitions(document: Document, container: str):
    for entry in document.root.named(container):
        if isinstance(entry.value, Block):
            yield from entry.value.entries


def _index(definitions: Iterable[ModifierDefinition]):
    result: dict[str, list[ModifierDefinition]] = defaultdict(list)
    for definition in definitions:
        result[definition.identifier].append(definition)
    return MappingProxyType({key: tuple(value) for key, value in result.items()})


def build_modifier_catalog(
    idea_documents: Iterable[Document],
    technology_documents: Iterable[Document],
    dynamic_documents: Iterable[Document] = (),
    *,
    auxiliary_documents: Mapping[str, Iterable[Document]] | None = None,
) -> ModifierCatalog:
    """Build an immutable index; duplicate source definitions remain ambiguous."""
    ideas, technologies, dynamics, law_categories = [], [], [], set()
    for document in idea_documents:
        for category in _definitions(document, "ideas"):
            if category.name is None or not isinstance(category.value, Block):
                continue
            if _scalar(category.value, "law") is True:
                law_categories.add(category.name)
            ideas.extend(_members(document, category.value, category.name))
    for document in technology_documents:
        technologies.extend(
            _members(
                document,
                Block(tuple(_definitions(document, "technologies")), document.root.span),
                "technology",
            )
        )
    for document in dynamic_documents:
        dynamics.extend(_members(document, document.root, "dynamic_modifier"))
    auxiliary = _auxiliary_indexes(auxiliary_documents or {})
    return ModifierCatalog(
        _index(ideas),
        _index(technologies),
        _index(dynamics),
        frozenset(law_categories),
        auxiliary=auxiliary,
    )


def _auxiliary_indexes(documents: Mapping[str, Iterable[Document]]):
    result = {}
    containers = {"characters": "characters", "traits": "leader_traits"}
    for category, sources in documents.items():
        definitions = []
        for document in sources:
            body = (
                Block(tuple(_definitions(document, containers[category])), document.root.span)
                if category in containers
                else document.root
            )
            definitions.extend(_members(document, body, category))
        result[category] = _index(definitions)
    advisors = []
    for definitions in result.get("characters", {}).values():
        for definition in definitions:
            for entry in definition.body.named("advisor"):
                token = (
                    _scalar(entry.value, "idea_token") if isinstance(entry.value, Block) else None
                )
                if isinstance(token, str):
                    advisors.append(
                        ModifierDefinition(definition.document, entry, "advisor", token)
                    )
    result["advisors"] = _index(advisors)
    return MappingProxyType(result)


def _members(document: Document, block: Block, category: str):
    return [
        ModifierDefinition(document, entry, category)
        for entry in block.entries
        if entry.name and entry.operator == "=" and isinstance(entry.value, Block)
    ]


def load_modifier_catalog(source_root: Path | str) -> ModifierCatalog:
    """Read one caller-selected checkout; source identity is the importer's concern."""
    root = Path(source_root)
    documents: dict[str, list[Document]] = defaultdict(list)
    diagnostics, fingerprints = [], []
    paths = {
        "ideas": "ideas",
        "technologies": "technologies",
        "dynamic_modifiers": "dynamic_modifiers",
        "characters": "characters",
        "traits": "country_leader",
        "equipment_groups": "equipment_groups",
        "static_modifiers": "modifiers",
    }
    for category, folder in paths.items():
        for path in sorted((root / "common" / folder).glob("*.txt")):
            source = path.relative_to(root).as_posix()
            payload = path.read_bytes()
            fingerprints.append((source, hashlib.sha256(payload).hexdigest(), len(payload)))
            try:
                documents[category].append(parse_bytes(payload, source=source))
            except ScriptSyntaxError as exc:
                diagnostics.append((source, str(exc)))
                if recovered := _recover_container(payload, source, exc):
                    documents[category].append(recovered)
    catalog = build_modifier_catalog(
        documents["ideas"],
        documents["technologies"],
        documents["dynamic_modifiers"],
        auxiliary_documents={
            key: documents[key]
            for key in paths
            if key not in {"ideas", "technologies", "dynamic_modifiers"}
        },
    )
    return ModifierCatalog(
        catalog.ideas,
        catalog.technologies,
        catalog.dynamic_modifiers,
        catalog.law_categories,
        tuple(diagnostics),
        tuple(fingerprints),
        catalog.auxiliary,
    )


def _recover_container(payload: bytes, source: str, error: ScriptSyntaxError) -> Document | None:
    """Recover complete categories only when the sole missing brace is their parent."""
    text = payload.decode("utf-8")
    header = re.match(r"\ufeff?\s*(ideas|technologies)\s*=\s*\{", text)
    if header is None or error.offset != header.end() - 1 or "Unclosed block" not in str(error):
        return None
    recovery = recover_complete_children(text, error.offset, source=source)
    if recovery.error is None or recovery.error.offset != error.offset:
        return None
    span = Span(0, len(text))
    parent = Entry(
        Atom(header[1], "bare", Span(header.start(1), header.end(1))),
        "=",
        Block(recovery.entries, Span(error.offset, len(text))),
        span,
    )
    return Document(source, text, hashlib.sha256(payload).hexdigest(), Block((parent,), span))


def _origin(document: Document, entry: Entry) -> dict:
    return {
        "source": {"path": document.source, "sha256": document.sha256},
        "line": document.position(entry.span.start)[0],
    }


def _guard(
    block: Block,
    context: SelectionContext,
    tag: str,
    mode: str = "and",
    government: str | None = None,
) -> Truth:
    values = tuple(_trigger(entry, context, tag, government) for entry in block.entries)
    decisive = Truth.FALSE if mode == "and" else Truth.TRUE
    result = (
        decisive
        if decisive in values
        else Truth.UNKNOWN
        if Truth.UNKNOWN in values
        else Truth.TRUE
        if mode == "and"
        else Truth.FALSE
    )
    return (
        (Truth.FALSE if result == Truth.TRUE else Truth.TRUE)
        if mode == "not" and result != Truth.UNKNOWN
        else result
    )


def _trigger(
    entry: Entry, context: SelectionContext, tag: str, government: str | None = None
) -> Truth:
    name = (entry.name or "").lower()
    if entry.operator == "=" and name in {"and", "or", "not"} and isinstance(entry.value, Block):
        return _guard(entry.value, context, tag, name, government)
    if entry.operator == "=" and name in {"tag", "original_tag"} and isinstance(entry.value, Atom):
        return Truth.TRUE if entry.value.text == tag else Truth.FALSE
    if (
        entry.operator == "="
        and name == "has_government"
        and isinstance(entry.value, Atom)
        and government is not None
    ):
        return Truth.TRUE if entry.value.text == government else Truth.FALSE
    return evaluate_trigger(entry, context)


def _fields(block: Block) -> set[str]:
    result = set()
    for entry in block.entries:
        if entry.name is not None and (
            _economic(entry.name) or entry.name in SCOPED_ECONOMIC_FIELDS
        ):
            result.add(entry.name)
        if isinstance(entry.value, Block):
            result.update(_fields(entry.value))
    return result


def _history_branch(block: Block, offset: int) -> Entry | None:
    for entry in block.entries:
        if entry.span.start == offset:
            return entry
        if isinstance(entry.value, Block) and entry.span.start < offset < entry.span.end:
            return _history_branch(entry.value, offset)
    return None


def _history_affects_modifiers(entry: Entry) -> bool:
    if entry.name in HISTORY_OPERATIONS:
        return True
    return isinstance(entry.value, Block) and any(
        _history_affects_modifiers(child) for child in entry.value.entries
    )


def _arithmetic(operation: str, current: int | float | None, operand: int | float | None):
    if operation == "set_variable":
        return operand
    if current is None or operand is None:
        return None
    operations = {
        "add_to_variable": lambda: current + operand,
        "subtract_from_variable": lambda: current - operand,
        "multiply_variable": lambda: current * operand,
        "divide_variable": lambda: current / operand if operand else None,
    }
    result = operations[operation]()
    return result if result is not None and isfinite(result) else None


def _equipment_selectors(
    catalog: ModifierCatalog, identifier: str, active: frozenset[str] = frozenset()
) -> tuple[str, ...] | None:
    groups = catalog.auxiliary.get("equipment_groups", {})
    if identifier not in groups:
        return (identifier,)
    if identifier in active or len(groups[identifier]) != 1:
        return None
    values = groups[identifier][0].body.assignments("equipment_type")
    if len(values) != 1 or not isinstance(values[0], Block):
        return None
    result = set()
    for entry in values[0].entries:
        if entry.name is not None or not isinstance(entry.value, Atom):
            return None
        children = _equipment_selectors(catalog, entry.value.text, active | {identifier})
        if children is None:
            return None
        result.update(children)
    return tuple(sorted(result))


class _Resolver:
    def __init__(
        self, document: Document, context: SelectionContext, catalog: ModifierCatalog, tag: str
    ):
        self.document, self.context, self.catalog, self.tag = document, context, catalog, tag
        self.ideas: dict[str, str] = {}
        self.technologies: dict[str, int] = {}
        self.dynamics: set[str] = set()
        self.variables: dict[str, int | float | None] = {}
        self.contributions: list[dict] = []
        self.blockers: list[dict] = []
        self.scoped: list[dict] = []
        self.operations: list[dict] = []
        self.ignored_fields: set[str] = set()
        self.variable_diagnostics: list[dict] = []
        self.other_history_branches: list[dict] = []
        self.recruited_characters: set[str] = set()
        self.government: str | None = None
        self.uncertain_variables: set[str] = set()
        self.unresolved_variable_writes = False

    def issue(self, code: str, document: Document, entry: Entry, fields=(), **extra):
        self.blockers.append(
            {
                "code": code,
                "field": entry.name,
                "affected_modifiers": sorted(fields),
                **_origin(document, entry),
                **extra,
            }
        )

    def definition(
        self, index: Mapping[str, tuple[ModifierDefinition, ...]], identifier: str, entry: Entry
    ):
        definitions = index.get(identifier, ())
        if len(definitions) == 1:
            return definitions[0]
        self.issue(
            "missing_definition" if not definitions else "ambiguous_definition",
            self.document,
            entry,
            identifier=identifier,
        )
        return None

    def defaults(self):
        candidates: dict[str, list[str]] = defaultdict(list)
        for identifier, definitions in self.catalog.ideas.items():
            if len(definitions) != 1:
                continue
            definition = definitions[0]
            if (
                definition.category not in self.catalog.law_categories
                or _scalar(definition.body, "default") is not True
            ):
                continue
            allowed = definition.body.named("allowed")
            outcome = (
                _guard(allowed[0].value, self.context, self.tag)
                if len(allowed) == 1 and isinstance(allowed[0].value, Block)
                else Truth.UNKNOWN
                if allowed
                else Truth.TRUE
            )
            if outcome == Truth.TRUE:
                candidates[definition.category].append(identifier)
            elif outcome == Truth.UNKNOWN:
                self.issue(
                    "unknown_default_eligibility",
                    definition.document,
                    definition.entry,
                    _fields(definition.body),
                )
        for category, identifiers in candidates.items():
            if len(identifiers) == 1:
                self.ideas[identifiers[0]] = "default"
            else:
                definition = self.catalog.ideas[identifiers[0]][0]
                self.issue(
                    "ambiguous_default_law",
                    definition.document,
                    definition.entry,
                    identifiers=identifiers,
                    category=category,
                )

    def idea(self, identifier: str, operation: str, entry: Entry):
        if operation == "remove_ideas":
            self.ideas.pop(identifier, None)
            return
        index = (
            self.catalog.ideas
            if identifier in self.catalog.ideas
            else self.catalog.auxiliary.get("advisors", {})
        )
        definition = self.definition(index, identifier, entry)
        if definition is not None and definition.category in self.catalog.law_categories:
            for active in tuple(self.ideas):
                definitions = self.catalog.ideas.get(active, ())
                if len(definitions) == 1 and definitions[0].category == definition.category:
                    del self.ideas[active]
        self.ideas[identifier] = "history"

    def idea_operation(self, entry: Entry):
        if isinstance(entry.value, Atom):
            self.idea(entry.value.text, entry.name or "", entry)
        elif isinstance(entry.value, Block):
            for child in entry.value.entries:
                if child.name is None and isinstance(child.value, Atom):
                    self.idea(child.value.text, entry.name or "", entry)
                else:
                    self.issue("invalid_idea_operation", self.document, child)
        else:
            self.issue("invalid_idea_operation", self.document, entry)

    def technology_operation(self, entry: Entry):
        if not isinstance(entry.value, Block):
            self.issue("invalid_technology_operation", self.document, entry)
            return
        for child in entry.value.entries:
            if child.name == "popup":
                continue
            level = _number(child.value) if isinstance(child.value, Atom) else None
            if child.name and child.operator == "=" and level in (0, 1):
                self.technologies[child.name] = int(level)
            else:
                self.issue("unresolved_technology_level", self.document, child)

    def variable_operation(self, entry: Entry):
        if not isinstance(entry.value, Block):
            self.unresolved_variable_writes = True
            self.variable_diagnostics.append(
                {"code": "unresolved_variable_operation", **_origin(self.document, entry)}
            )
            return
        for child in entry.value.entries:
            if child.name and child.operator == "=" and isinstance(child.value, Atom):
                value = _number(child.value)
                operand = (
                    value
                    if value is not None
                    else self.variable_value(child.value.text)
                    if child.value.kind == "bare"
                    else None
                )
                self.variables[child.name] = _arithmetic(
                    entry.name or "", self.variable_value(child.name), operand
                )
            else:
                self.variable_diagnostics.append(
                    {"code": "unresolved_variable_operation", **_origin(self.document, child)}
                )
                if child.name is not None:
                    self.uncertain_variables.add(child.name)

    def variable_value(self, name: str):
        if (
            self.unresolved_variable_writes
            or name in self.uncertain_variables
            or re.fullmatch(r"[A-Za-z_]\w*", name) is None
        ):
            return None
        return self.variables.get(name, 0)

    def character_operation(self, entry: Entry):
        if isinstance(entry.value, Atom):
            self.recruited_characters.add(entry.value.text)
        else:
            self.issue("unresolved_character_recruitment", self.document, entry)

    def politics_operation(self, entry: Entry):
        value = _scalar(entry.value, "ruling_party") if isinstance(entry.value, Block) else None
        self.government = value if isinstance(value, str) else None

    def dynamic_operation(self, entry: Entry):
        identifier = _scalar(entry.value, "modifier") if isinstance(entry.value, Block) else None
        if not isinstance(identifier, str):
            self.issue("invalid_dynamic_modifier_operation", self.document, entry)
        elif entry.name == "remove_dynamic_modifier":
            self.dynamics.discard(identifier)
        elif isinstance(entry.value, Block) and any(
            child.name not in {"modifier"} for child in entry.value.entries
        ):
            self.issue(
                "scoped_or_timed_dynamic_modifier", self.document, entry, identifier=identifier
            )
        else:
            self.dynamics.add(identifier)

    def history(self):
        selection = select_history(self.document, self.context)
        for issue in selection.blockers:
            diagnostic = {
                "code": "unresolved_history_branch",
                "field": issue.field,
                "line": self.document.position(issue.offset)[0],
                "selection_code": issue.code,
                "affected_modifiers": [],
            }
            branch = _history_branch(self.document.root, issue.offset)
            if branch is None or _history_affects_modifiers(branch):
                self.blockers.append(diagnostic)
                if branch is not None:
                    self._uncertain_branch_variables(branch)
            else:
                self.other_history_branches.append(diagnostic)
        handlers = {
            "add_ideas": self.idea_operation,
            "remove_ideas": self.idea_operation,
            "set_technology": self.technology_operation,
            "set_variable": self.variable_operation,
            "add_dynamic_modifier": self.dynamic_operation,
            "remove_dynamic_modifier": self.dynamic_operation,
            "recruit_character": self.character_operation,
            "set_politics": self.politics_operation,
        }
        for name in (
            "add_to_variable",
            "subtract_from_variable",
            "multiply_variable",
            "divide_variable",
        ):
            handlers[name] = self.variable_operation
        for entry in selection.entries:
            if entry.name in handlers:
                handlers[entry.name](entry)
                self.operations.append({"operation": entry.name, **_origin(self.document, entry)})
            elif entry.name in HISTORY_OPERATIONS:
                self.issue("unsupported_economic_history_operation", self.document, entry)

    def _uncertain_branch_variables(self, entry: Entry):
        if not isinstance(entry.value, Block):
            return
        if entry.name and "variable" in entry.name:
            self.uncertain_variables.update(
                child.name for child in entry.value.entries if child.name
            )
        for child in entry.value.entries:
            self._uncertain_branch_variables(child)

    def enabled(self, definition: ModifierDefinition, guard_name: str) -> bool:
        guards = definition.body.named(guard_name)
        if not guards:
            return True
        outcome = (
            _guard(guards[0].value, self.context, self.tag, government=self.government)
            if len(guards) == 1 and isinstance(guards[0].value, Block)
            else Truth.UNKNOWN
        )
        if outcome == Truth.UNKNOWN:
            self.issue(
                "unknown_modifier_guard",
                definition.document,
                guards[0],
                _fields(definition.body),
                identifier=definition.identifier,
            )
        return outcome == Truth.TRUE

    def numeric(self, definition: ModifierDefinition, entry: Entry, *, dynamic: bool):
        value = _number(entry.value) if isinstance(entry.value, Atom) else None
        variable = None
        if value is None and dynamic and isinstance(entry.value, Atom):
            variable = entry.value.text
            value = self.variable_value(variable) if entry.value.kind == "bare" else None
        if value is None or entry.operator != "=":
            self.issue(
                "unresolved_economic_value",
                definition.document,
                entry,
                {entry.name},
                identifier=definition.identifier,
            )
            return
        self.contributions.append(
            {
                "field": entry.name,
                "value": value,
                "kind": definition.category,
                "identifier": definition.identifier,
                "variable": variable,
                "value_origin": "unset_variable_default"
                if variable is not None and variable not in self.variables
                else "history_variable"
                if variable is not None
                else "literal",
                **_origin(definition.document, entry),
            }
        )

    def modifiers(self, definition: ModifierDefinition, block: Block, *, dynamic: bool = False):
        repeated = {
            entry.name
            for entry in block.entries
            if _economic(entry.name) and len(block.named(entry.name or "")) > 1
        }
        for entry in block.entries:
            if entry.name in repeated:
                self.issue(
                    "ambiguous_economic_declaration",
                    definition.document,
                    entry,
                    {entry.name},
                    identifier=definition.identifier,
                )
            elif _economic(entry.name):
                self.numeric(definition, entry, dynamic=dynamic)
            elif isinstance(entry.value, Block) and (fields := _fields(entry.value)):
                self.scoped.append(
                    {
                        "scope": entry.name,
                        "fields": sorted(fields),
                        "identifier": definition.identifier,
                        **_origin(definition.document, entry),
                    }
                )
                self.issue(
                    "unresolved_scoped_economic_modifier",
                    definition.document,
                    entry,
                    fields,
                    identifier=definition.identifier,
                )
            else:
                self.ignored_fields.add(entry.name or "<unkeyed>")

    def idea_modifiers(self, definition: ModifierDefinition):
        if not self.enabled(definition, "do_effect"):
            return
        for entry in definition.body.entries:
            if entry.name == "modifier" and isinstance(entry.value, Block):
                self.modifiers(definition, entry.value)
            elif entry.name == "equipment_bonus" and isinstance(entry.value, Block):
                for bonus in entry.value.entries:
                    self.equipment_bonus(definition, bonus)
            elif (
                entry.name not in IDEA_METADATA
                and isinstance(entry.value, Block)
                and (fields := _fields(entry.value))
            ):
                self.issue(
                    "unresolved_scoped_idea_effect",
                    definition.document,
                    entry,
                    fields,
                    identifier=definition.identifier,
                )

    def equipment_bonus(self, definition: ModifierDefinition, entry: Entry):
        if entry.name is None or not isinstance(entry.value, Block):
            self.issue("invalid_equipment_bonus", definition.document, entry)
            return
        economic = tuple(
            child for child in entry.value.entries if child.name in SCOPED_ECONOMIC_FIELDS
        )
        if not economic:
            return
        selectors = _equipment_selectors(self.catalog, entry.name)
        if _scalar(entry.value, "instant") is not True or selectors is None:
            self.issue(
                "unresolved_equipment_bonus_application",
                definition.document,
                entry,
                {child.name for child in economic},
                identifier=definition.identifier,
            )
            return
        for child in economic:
            value = _number(child.value) if isinstance(child.value, Atom) else None
            if (
                child.name != "build_cost_ic"
                or value is None
                or len(entry.value.named(child.name)) != 1
            ):
                self.issue(
                    "unresolved_equipment_bonus_value",
                    definition.document,
                    child,
                    {child.name},
                    identifier=definition.identifier,
                )
                continue
            self.scoped.append(
                {
                    "scope": "equipment_bonus",
                    "identifier": definition.identifier,
                    "group": entry.name,
                    "selectors": list(selectors),
                    "field": child.name,
                    "value": value,
                    "application": "instant",
                    "operation": "relative_cost_factor",
                    **_origin(definition.document, child),
                }
            )

    def resolve(self):
        self.defaults()
        self.history()
        for identifier in self.ideas:
            definitions = self.catalog.ideas.get(identifier, ())
            if len(definitions) == 1:
                self.idea_modifiers(definitions[0])
            else:
                self.advisor_modifiers(identifier)
        for identifier, level in self.technologies.items():
            if level:
                self.resolve_other(identifier, self.catalog.technologies, dynamic=False)
        for identifier in sorted(self.dynamics):
            self.resolve_other(identifier, self.catalog.dynamic_modifiers, dynamic=True)
        return self.report()

    def advisor_modifiers(self, identifier: str):
        advisors = self.catalog.auxiliary.get("advisors", {}).get(identifier, ())
        if len(advisors) != 1:
            return
        advisor = advisors[0]
        characters = self.catalog.auxiliary.get("characters", {})
        recruited = any(
            definition.document.source == advisor.document.source
            and definition.entry.span.start < advisor.entry.span.start < definition.entry.span.end
            for name in self.recruited_characters
            for definition in characters.get(name, ())
        )
        if not recruited:
            self.issue(
                "advisor_character_not_recruited",
                advisor.document,
                advisor.entry,
                identifier=identifier,
            )
            return
        self.idea_modifiers(advisor)
        for entry in advisor.body.named("traits"):
            if not isinstance(entry.value, Block):
                self.issue("invalid_advisor_traits", advisor.document, entry, identifier=identifier)
                continue
            for trait in entry.value.entries:
                self.advisor_trait(advisor, trait)

    def advisor_trait(self, advisor: ModifierDefinition, entry: Entry):
        name = entry.value.text if entry.name is None and isinstance(entry.value, Atom) else None
        definitions = self.catalog.auxiliary.get("traits", {}).get(name or "", ())
        if len(definitions) != 1:
            self.issue("unresolved_advisor_trait", advisor.document, entry, identifier=name)
            return
        self.modifiers(definitions[0], definitions[0].body)

    def resolve_other(
        self, identifier: str, index: Mapping[str, tuple[ModifierDefinition, ...]], *, dynamic: bool
    ):
        definitions = index.get(identifier, ())
        if len(definitions) != 1:
            self.blockers.append(
                {
                    "code": "missing_definition" if not definitions else "ambiguous_definition",
                    "identifier": identifier,
                    "affected_modifiers": [],
                }
            )
            return
        definition = definitions[0]
        if dynamic and not self.enabled(definition, "enable"):
            return
        if dynamic:
            for entry in definition.body.named("remove_trigger"):
                fields = _fields(definition.body)
                outcome = (
                    _guard(entry.value, self.context, self.tag, government=self.government)
                    if isinstance(entry.value, Block)
                    else Truth.UNKNOWN
                )
                if fields and outcome != Truth.FALSE:
                    self.issue(
                        "unresolved_dynamic_removal_condition",
                        definition.document,
                        entry,
                        fields,
                        identifier=identifier,
                    )
        ignored = {"enable", "icon", "remove_trigger"} if dynamic else TECH_METADATA
        block = Block(
            tuple(entry for entry in definition.body.entries if entry.name not in ignored),
            definition.body.span,
        )
        self.modifiers(definition, block, dynamic=dynamic)

    def report(self):
        amounts: dict[str, list[int | float]] = defaultdict(list)
        for contribution in self.contributions:
            amounts[contribution["field"]].append(contribution["value"])
        factors = amounts.pop("consumer_goods_factor", [])
        additive = {field: fsum(values) for field, values in sorted(amounts.items())}
        return {
            "schema_version": 1,
            "country": self.tag,
            "start": self.context.start.to_dict(),
            "semantics": (
                "Known initial country-modifier contributions only; incomplete totals must not "
                "be used as effective capacity. History hooks are not executed. State, character, "
                "stability, war-support and campaign script effects require separate resolution."
            ),
            "active_ideas": [{"id": key, "origin": value} for key, value in self.ideas.items()],
            "researched_technologies": sorted(
                key for key, level in self.technologies.items() if level
            ),
            "active_dynamic_modifiers": sorted(self.dynamics),
            "contributions": self.contributions,
            "additive_modifiers": additive,
            "multiplicative_modifiers": {"consumer_goods_factor": factors},
            "consumer_goods_factor_product": prod(1 + value for value in factors),
            "blocked_fields": sorted(
                {field for issue in self.blockers for field in issue["affected_modifiers"]}
            ),
            "scoped_modifiers": self.scoped,
            "blockers": self.blockers,
            "selected_country_modifiers_complete": not self.blockers,
            "effective_country_economy_resolved": False,
            "scenario_ready": False,
            "ignored_non_economic_fields": sorted(self.ignored_fields),
            "history_operations": self.operations,
            "catalog_parse_diagnostics": [
                {"source": source, "message": message}
                for source, message in self.catalog.parse_diagnostics
            ],
            "variable_diagnostics": self.variable_diagnostics,
            "other_history_branch_diagnostics": self.other_history_branches,
        }


def resolve_country_modifiers(
    document: Document,
    context: SelectionContext,
    catalog: ModifierCatalog,
    *,
    tag: str,
) -> dict:
    """Resolve initial history for one tag; return caller-owned facts and blockers.

    This is not the runtime executor for later focus/law/research schedules: the
    game suppresses initial-history on-add and on-research hooks specifically.
    """
    return _Resolver(document, context, catalog, tag).resolve()


def resolve_support_profile(catalog: ModifierCatalog) -> dict:
    """Extract source-specific economic endpoint tables for the pure support evaluator."""
    tables, contributions, blockers = {}, [], []
    names = (
        "stability_good_modifier",
        "stability_bad_modifier",
        "war_support_good_modifier",
        "war_support_bad_modifier",
        "war_support_during_war",
    )
    for name in names:
        definitions = catalog.auxiliary.get("static_modifiers", {}).get(name, ())
        if len(definitions) != 1:
            blockers.append({"code": "unresolved_static_modifier_definition", "identifier": name})
            continue
        definition = definitions[0]
        values = {}
        for entry in definition.body.entries:
            if not _economic(entry.name):
                continue
            value = _number(entry.value) if isinstance(entry.value, Atom) else None
            if value is None or len(definition.body.named(entry.name or "")) != 1:
                blockers.append(
                    {
                        "code": "unresolved_static_modifier_value",
                        "identifier": name,
                        "field": entry.name,
                        **_origin(definition.document, entry),
                    }
                )
            else:
                values[entry.name] = value
                contributions.append(
                    {
                        "identifier": name,
                        "field": entry.name,
                        "value": value,
                        **_origin(definition.document, entry),
                    }
                )
        tables[name] = values
    return {
        "tables": tables,
        "contributions": contributions,
        "blockers": blockers,
        "source_values_complete": not blockers,
        "semantics": (
            "Source endpoint modifiers only; current effective stability and war support "
            "are explicit evaluator inputs."
        ),
    }
