"""Derive source-level state economic facts and separately eligible landmark bonuses."""

import re
from collections import Counter, defaultdict
from math import isfinite

from games.hoi4.data_pipeline.selection import SelectionContext, Truth, evaluate_guard
from games.hoi4.data_pipeline.state_economy_sources import read_state_economy_inputs
from games.hoi4.data_pipeline.syntax import Block, parse_script
from games.hoi4.planning.time import CampaignDate

__all__ = ["read_state_economy_inputs", "summarize_country_states"]

STATE_RULE_SOURCE = (
    "https://github.com/klimPaskov/Agentic-HOI4-Modding/blob/"
    "daf409fcba6c3f7c4bf68109d453f02874a71892/hoi4_wiki/state_modding.md"
)
BUILDING_RULE_SOURCE = STATE_RULE_SOURCE.replace("state_modding.md", "building_modding.md")
FACTORIES = ("industrial_complex", "arms_factory", "dockyard")
METADATA = frozenset({"provinces", "victory_points", "name", "color"})


def _index(records: list[dict]) -> dict[str, list[dict]]:
    indexed = defaultdict(list)
    for record in records:
        indexed[str(record["id"])].append(record)
    return dict(indexed)


def _declarations(blocks: list[dict]) -> list[dict]:
    return [row for block in blocks for row in block["declarations"]]


def _number(rows: list[dict], field: str, *, missing=None):
    values = [row["value"] for row in rows if row["field"] == field]
    if not values:
        return missing
    if len(values) != 1:
        return None
    value = values[0]
    return value if type(value) in {int, float} and isfinite(value) and value >= 0 else None


def _shares_slots(records: list[dict]) -> bool | None:
    if len(records) != 1:
        return None
    caps = _declarations(records[0]["level_cap"])
    values = [row["value"] for row in caps if row["field"] == "shares_slots"]
    if not values:
        return False
    return values[0] if len(values) == 1 and isinstance(values[0], bool) else None


def _core_status(state: dict, tag: str) -> bool | None:
    core = False
    for row in state["history_declarations"]:
        if row["field"] not in {"add_core_of", "remove_core_of"}:
            continue
        if not isinstance(row["value"], str) or row["value"].startswith(("@", "[")):
            return None
        if row["value"] == tag:
            core = row["field"] == "add_core_of"
    return core


def _gap_kind(field, context: SelectionContext | None) -> str:
    if field in METADATA:
        return "metadata"
    if isinstance(field, str) and field.isdigit():
        return "province_building_scope"
    if isinstance(field, str) and re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", field):
        try:
            if context and CampaignDate.parse(field) > context.start:
                return "future_history"
        except ValueError:
            pass
        return "dated_history"
    if str(field).lower() in {"if", "else", "else_if", "limit"}:
        return "conditional_economy"
    return "unresolved_economy"


def _state_gaps(state: dict, context) -> list[dict]:
    rows = [
        *state["unresolved_history_statements"],
        *state["unresolved_state_statements"],
        *(row for block in state["base_building_blocks"] for row in block["unresolved_statements"]),
        *(row for block in state["resource_blocks"] for row in block["unresolved_statements"]),
    ]
    return [
        {**row, "state_id": state["id"], "kind": _gap_kind(row["field"], context)} for row in rows
    ]


def _state_slots(state, buildings, categories):
    category = categories.get(state["category"], [])
    capacity = (
        _number(category[0]["declarations"], "local_building_slots") if len(category) == 1 else None
    )
    declarations = _declarations(state["base_building_blocks"])
    used, unknown = 0, []
    for field in dict.fromkeys(row["field"] for row in declarations):
        count = _number(declarations, field)
        shares = _shares_slots(buildings.get(field, []))
        if count is None or shares is None:
            unknown.append({"code": "unresolved_building_level_or_slot_type", "field": field})
        elif shares:
            used += count
    if capacity is None:
        unknown.append({"code": "unresolved_state_category_slots", "field": state["category"]})
    return (
        capacity,
        None if unknown and any("building" in row["code"] for row in unknown) else used,
        unknown,
    )


def _state_record(state, tag, buildings, categories, supplement):
    capacity, used, unknown = _state_slots(state, buildings, categories)
    declarations = _declarations(state["base_building_blocks"])
    resources = _declarations(state["resource_blocks"])
    deposits = {
        field: _number(resources, field)
        for field in dict.fromkeys(row["field"] for row in resources)
    }
    factories = {field: _number(declarations, field, missing=0) for field in FACTORIES}
    population = state["manpower"]
    if type(population) is not int or population < 0:
        population = None
        unknown.append({"code": "unresolved_base_population", "field": "manpower"})
    core = _core_status(state, tag)
    if core is None:
        unknown.append({"code": "unresolved_base_core", "field": "add_core_of"})
    for field, value in {**factories, **deposits}.items():
        if value is None:
            unknown.append({"code": "ambiguous_or_nonnumeric_declaration", "field": field})
    scalars = supplement.get("state_declarations", []) if supplement else []
    return {
        "id": state["id"],
        "source": state["source"],
        "category": state["category"],
        "category_shared_slot_capacity": capacity,
        "declared_shared_slots_used": used,
        "category_slots_minus_declared_use": capacity - used
        if capacity is not None and used is not None
        else None,
        "declared_factories": factories,
        "declared_resource_deposits": deposits,
        "base_population": population,
        "base_core": core,
        "base_core_population": population if core is True else 0 if core is False else None,
        "state_slot_multiplier": _number(scalars, "buildings_max_level_factor")
        if supplement
        else None,
        "effective_free_slots": None,
        "unknowns": [{**row, "state_id": state["id"]} for row in unknown],
    }


def _sum_known(values):
    return None if any(value is None for value in values) else sum(values)


def _totals(states):
    resources = dict.fromkeys(
        key for state in states for key in state["declared_resource_deposits"]
    )
    return {
        "state_count": len(states),
        "category_shared_slot_capacity": _sum_known(
            [state["category_shared_slot_capacity"] for state in states]
        ),
        "declared_shared_slots_used": _sum_known(
            [state["declared_shared_slots_used"] for state in states]
        ),
        "declared_factories": {
            field: _sum_known([state["declared_factories"][field] for state in states])
            for field in FACTORIES
        },
        "declared_resource_deposits": {
            field: _sum_known(
                [state["declared_resource_deposits"].get(field, 0) for state in states]
            )
            for field in resources
        },
        "base_population": _sum_known([state["base_population"] for state in states]),
        "base_core_population": _sum_known([state["base_core_population"] for state in states]),
    }


def _all_true(*values: Truth) -> Truth:
    return (
        Truth.FALSE
        if Truth.FALSE in values
        else Truth.UNKNOWN
        if Truth.UNKNOWN in values
        else Truth.TRUE
    )


def _condition_status(conditions: list[dict], context) -> Truth:
    values = []
    for condition in conditions:
        if context is None:
            values.append(Truth.UNKNOWN)
            continue
        document = parse_script("guard = " + condition["script"])
        value = document.root.assignments("guard")[0]
        values.append(evaluate_guard(value, context) if isinstance(value, Block) else Truth.UNKNOWN)
    return _all_true(*values)


def _landmarks(country, supplements, context):
    catalog = _index(supplements.get("landmark_definitions", []))
    state_index = _index(country["states"])
    supplement_counts = Counter(state["id"] for state in supplements.get("states", []))
    findings = []
    for state in supplements.get("states", []):
        matches = state_index.get(str(state["id"]), [])
        if (
            len(matches) != 1
            or supplement_counts[state["id"]] != 1
            or state["source"]["sha256"] != matches[0]["source"]["sha256"]
        ):
            findings.append({"state_id": state["id"], "status": "state_source_mismatch"})
            continue
        for placement in state["province_buildings"]:
            if not str(placement["building_id"]).startswith("landmark_"):
                continue
            definitions = catalog.get(placement["building_id"], [])
            if len(definitions) != 1:
                findings.append(
                    {**placement, "state_id": state["id"], "status": "unknown_definition"}
                )
                continue
            controller = _controller_tag(matches[0], country["tag"])
            findings.extend(
                _landmark_effects(
                    country["tag"], controller, state, placement, definitions[0], context
                )
            )
    return findings


def _controller_tag(state, owner):
    values = [row["value"] for row in state["history_declarations"] if row["field"] == "controller"]
    if not values:
        return owner
    return values[0] if len(values) == 1 and isinstance(values[0], str) else None


def _controller_allowed(controller, block) -> Truth:
    if not block["controllers_resolved"]:
        return Truth.UNKNOWN
    if not block["controllers"]:
        return Truth.TRUE
    if controller is None:
        return Truth.UNKNOWN
    return Truth.TRUE if controller in block["controllers"] else Truth.FALSE


def _known_boolean(status: Truth) -> bool | None:
    return None if status == Truth.UNKNOWN else status == Truth.TRUE


def _landmark_effects(country_tag, controller, state, placement, definition, context):
    level = _number(placement["declarations"], "level")
    status = _condition_status([*placement["conditions"], *definition["conditions"]], context)
    if level is None or level > 1:
        status = _all_true(status, Truth.UNKNOWN)
    elif level == 0:
        status = Truth.FALSE
    controlled = (
        Truth.UNKNOWN
        if controller is None
        else Truth.TRUE
        if controller == country_tag
        else Truth.FALSE
    )
    findings = []
    for block in definition["country_modifiers"]:
        allowed = _controller_allowed(controller, block)
        applicable = _all_true(status, allowed, controlled)
        modifiers = _modifier_values(block["modifiers"])
        findings.append(
            {
                "building_id": placement["building_id"],
                "state_id": state["id"],
                "province_id": placement["province_id"],
                "level": level,
                "condition_status": status.value,
                "controller_tag": controller,
                "controller_allowed": _known_boolean(allowed),
                "controller_is_country": _known_boolean(controlled),
                "applicability_status": applicable.value,
                "applicable_under_declared_owner": applicable == Truth.TRUE,
                "modifiers": modifiers,
                "source": definition["source"],
                "placement_source": state["source"],
                "line": placement["line"],
            }
        )
    return findings


def _modifier_values(rows):
    values = defaultdict(list)
    for row in rows:
        values[row["field"]].append(row["value"])
    return {field: items[0] if len(items) == 1 else None for field, items in values.items()}


def summarize_country_states(
    country_profile: dict,
    building_rules: dict,
    *,
    supplements: dict | None = None,
    context: SelectionContext | None = None,
) -> dict:
    """Summarize base declarations, preserving gaps separately from map/display metadata."""
    supplements = supplements or {}
    indexed = _index(supplements.get("states", []))
    buildings, categories = (
        _index(building_rules["buildings"]),
        _index(building_rules["state_categories"]),
    )
    states, gaps = [], []
    for state in country_profile["states"]:
        extra = indexed.get(str(state["id"]), [])
        supplement = (
            extra[0]
            if len(extra) == 1 and extra[0]["source"]["sha256"] == state["source"]["sha256"]
            else None
        )
        states.append(
            _state_record(state, country_profile["tag"], buildings, categories, supplement)
        )
        gaps.extend(_state_gaps(state, context))
    landmarks = _landmarks(country_profile, supplements, context)
    return {
        "schema_version": 1,
        "country_tag": country_profile["tag"],
        "semantics": (
            "Base source declarations, before dated/conditional effects, ownership changes, "
            "technology, occupation, trade, resource extraction and population growth. "
            "Category slots are not effective construction capacity."
        ),
        "defaults_evidence": {
            "absent_initial_building_level": {"value": 0, "source": STATE_RULE_SOURCE},
            "state_building_type_without_shared_flag": {
                "value": "state",
                "source": BUILDING_RULE_SOURCE,
            },
            "absent_initial_controller": {"value": "owner", "source": STATE_RULE_SOURCE},
        },
        "totals": _totals(states),
        "states": states,
        "gaps": gaps,
        "gap_counts": dict(Counter(row["kind"] for row in gaps)),
        "unknowns": [row for state in states for row in state["unknowns"]],
        "landmark_effects": landmarks,
        "landmark_country_modifiers": _landmark_totals(landmarks),
        "effective_economy_resolved": False,
    }


def _landmark_totals(landmarks):
    values = defaultdict(list)
    for landmark in landmarks:
        if landmark.get("applicable_under_declared_owner"):
            for field, value in landmark["modifiers"].items():
                values[field].append(value)
        elif landmark.get("applicability_status") == Truth.UNKNOWN:
            for field in landmark["modifiers"]:
                values[field].append(None)
    return {
        field: sum(items)
        if all(type(value) in {int, float} and isfinite(value) for value in items)
        else None
        for field, items in values.items()
    }
