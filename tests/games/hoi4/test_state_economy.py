"""State facts and landmark eligibility retain source and conditional uncertainty."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest

from games.hoi4.data_pipeline.public_import import REFERENCE_ROOT, load_reference_country
from games.hoi4.data_pipeline.selection import SelectionContext
from games.hoi4.data_pipeline.state_economy import (
    read_state_economy_inputs,
    summarize_country_states,
)
from games.hoi4.planning.time import CampaignDate


def _rules():
    return json.loads((REFERENCE_ROOT / "building_rules.json").read_text())


def _context(*, enabled=True):
    return SelectionContext(
        CampaignDate(1936, 1, 1, 12),
        frozenset({"Gotterdammerung"}),
        frozenset({"Gotterdammerung"}) if enabled else frozenset(),
    )


def test_france_base_slots_resources_and_core_population_are_useful_source_facts():
    country = load_reference_country("FRA")
    original = deepcopy(country)
    result = summarize_country_states(country, _rules(), context=_context())
    totals = result["totals"]
    assert totals["category_shared_slot_capacity"] == 205
    assert totals["declared_shared_slots_used"] == 55
    assert totals["declared_factories"] == {
        "industrial_complex": 35,
        "arms_factory": 8,
        "dockyard": 11,
    }
    assert totals["declared_resource_deposits"]["coal"] == 53
    assert totals["base_core_population"] == 42197733
    assert totals["base_population"] == 108932389
    assert result["effective_economy_resolved"] is False
    assert all(state["effective_free_slots"] is None for state in result["states"])
    assert result["gap_counts"]["metadata"] > 0
    assert result["gap_counts"]["future_history"] > 0
    assert result["defaults_evidence"]["absent_initial_building_level"]["value"] == 0
    assert country == original


def test_unmentioned_factory_is_zero_but_repeated_and_nonnumeric_values_stay_unknown():
    country = load_reference_country("FRA")
    country["states"] = country["states"][:1]
    state = country["states"][0]
    declarations = state["base_building_blocks"][0]["declarations"]
    declarations.append({"field": "industrial_complex", "value": 2})
    state["resource_blocks"] = [
        {"declarations": [{"field": "coal", "value": "@coal"}], "unresolved_statements": []}
    ]
    result = summarize_country_states(country, _rules())
    assert result["totals"]["declared_factories"]["dockyard"] == 0
    assert result["totals"]["declared_factories"]["industrial_complex"] is None
    assert result["totals"]["declared_shared_slots_used"] is None
    assert result["totals"]["declared_resource_deposits"]["coal"] is None
    assert result["unknowns"]


@pytest.mark.parametrize("category", [None, "unknown_category"])
def test_unknown_category_does_not_invent_capacity(category):
    country = load_reference_country("FRA")
    country["states"] = country["states"][:1]
    country["states"][0]["category"] = category
    result = summarize_country_states(country, _rules())
    assert result["totals"]["category_shared_slot_capacity"] is None
    assert result["states"][0]["category_slots_minus_declared_use"] is None


def test_core_population_uses_direct_ordered_core_declarations_and_preserves_unknowns():
    country = load_reference_country("FRA")
    country["states"] = country["states"][:1]
    state = country["states"][0]
    state["history_declarations"].append({"field": "remove_core_of", "value": "FRA"})
    assert summarize_country_states(country, _rules())["totals"]["base_core_population"] == 0
    state["history_declarations"].append({"field": "add_core_of", "value": "@tag"})
    state["manpower"] = None
    result = summarize_country_states(country, _rules())
    assert result["totals"]["base_core_population"] is None
    assert result["totals"]["base_population"] is None


def test_economic_scopes_are_not_hidden_among_display_metadata():
    country = load_reference_country("FRA")
    country["states"] = country["states"][:1]
    country["states"][0]["unresolved_history_statements"] = [
        {"field": field, "line": 1}
        for field in ["victory_points", "if", "1936.1.1.12", "1939.1.1", "FRA"]
    ]
    result = summarize_country_states(country, _rules(), context=_context())
    kinds = {row["field"]: row["kind"] for row in result["gaps"]}
    assert kinds["victory_points"] == "metadata"
    assert kinds["if"] == "conditional_economy"
    assert kinds["1936.1.1.12"] == "dated_history"
    assert kinds["1939.1.1"] == "future_history"
    assert kinds["FRA"] == "unresolved_economy"


@pytest.fixture
def landmark_source(tmp_path):
    source = tmp_path / "history/states/test.txt"
    source.parent.mkdir(parents=True)
    source.write_text("""state = { id = 1 manpower = 100 state_category = town
    buildings_max_level_factor = 1.0
    history = { owner = FRA add_core_of = FRA buildings = {
        industrial_complex = 1
        9523 = { landmark_eiffel_tower = { level = 1 allowed = { has_dlc = "Gotterdammerung" } } }
    } } }""")
    buildings = tmp_path / "common/buildings/test.txt"
    buildings.parent.mkdir(parents=True)
    buildings.write_text("""buildings = { landmark_eiffel_tower = {
    dlc_allowed = { has_dlc = "Gotterdammerung" }
    country_modifiers = { enable_for_controllers = { FRA } modifiers = { stability_factor = 0.05 } }
    } }""")
    country = load_reference_country("FRA")
    country["states"] = country["states"][:1]
    country["states"][0]["source"] = {
        "path": "history/states/test.txt",
        "sha256": sha256(source.read_bytes()).hexdigest(),
        "bytes": source.stat().st_size,
    }
    supplements = read_state_economy_inputs(tmp_path, country)
    assert all(
        item["bytes"] == (tmp_path / item["path"]).stat().st_size
        for item in supplements["input_sources"]
    )
    return country, supplements


def test_landmark_bonus_requires_matching_source_dlc_and_controller(landmark_source):
    country, supplements = landmark_source
    result = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert result["landmark_country_modifiers"] == {"stability_factor": 0.05}
    assert result["landmark_effects"][0]["province_id"] == 9523
    assert result["landmark_effects"][0]["placement_source"] == country["states"][0]["source"]
    assert result["states"][0]["state_slot_multiplier"] == 1
    disabled = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context(enabled=False)
    )
    assert disabled["landmark_country_modifiers"] == {}
    assert disabled["landmark_effects"][0]["condition_status"] == "false"
    country["states"][0]["history_declarations"].append({"field": "controller", "value": "GER"})
    occupied = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert occupied["landmark_country_modifiers"] == {}
    supplements["landmark_definitions"][0]["country_modifiers"][0]["controllers"] = ["GER"]
    foreign = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert foreign["landmark_country_modifiers"] == {}
    assert foreign["landmark_effects"][0]["controller_allowed"]
    assert not foreign["landmark_effects"][0]["controller_is_country"]


def test_unknown_landmark_guard_and_repeated_modifier_do_not_become_zero(landmark_source):
    country, supplements = landmark_source
    unknown = summarize_country_states(country, _rules(), supplements=supplements)
    assert unknown["landmark_country_modifiers"]["stability_factor"] is None
    block = supplements["landmark_definitions"][0]["country_modifiers"][0]
    block["modifiers"].append(deepcopy(block["modifiers"][0]))
    ambiguous = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert ambiguous["landmark_country_modifiers"]["stability_factor"] is None


def test_ambiguous_controller_does_not_hide_a_possible_country_bonus(landmark_source):
    country, supplements = landmark_source
    country["states"][0]["history_declarations"].extend(
        [{"field": "controller", "value": "FRA"}, {"field": "controller", "value": "GER"}]
    )
    report = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert report["landmark_country_modifiers"]["stability_factor"] is None


def test_landmark_source_mismatch_and_duplicate_supplements_cannot_double_bonuses(landmark_source):
    country, supplements = landmark_source
    supplements["states"].append(deepcopy(supplements["states"][0]))
    result = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert result["landmark_country_modifiers"] == {}
    assert result["landmark_effects"][0]["status"] == "state_source_mismatch"
    supplements["states"].pop()
    supplements["states"][0]["source"]["sha256"] = "different"
    result = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert result["landmark_country_modifiers"] == {}
    assert result["states"][0]["state_slot_multiplier"] is None


def test_missing_landmark_definition_is_an_explicit_unknown(landmark_source):
    country, supplements = landmark_source
    supplements["landmark_definitions"].clear()
    result = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert result["landmark_effects"][0]["status"] == "unknown_definition"


def test_unresolved_controller_scope_does_not_drop_possible_bonus_or_contaminate_other_blocks(
    landmark_source,
):
    country, supplements = landmark_source
    definition = supplements["landmark_definitions"][0]
    unresolved = definition["country_modifiers"][0]
    unresolved.update(controllers=["GER"], controllers_resolved=False)
    independent = deepcopy(unresolved)
    independent.update(
        controllers=["FRA"],
        controllers_resolved=True,
        modifiers=[{"field": "industrial_capacity_factory", "value": 0.1}],
    )
    definition["country_modifiers"].append(independent)
    forward = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert forward["landmark_country_modifiers"] == {
        "stability_factor": None,
        "industrial_capacity_factory": 0.1,
    }
    first, second = forward["landmark_effects"]
    assert first["controller_allowed"] is None and first["applicability_status"] == "unknown"
    assert second["condition_status"] == second["applicability_status"] == "true"
    definition["country_modifiers"].reverse()
    reverse = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context()
    )
    assert reverse["landmark_country_modifiers"] == forward["landmark_country_modifiers"]


def test_disabled_dlc_remains_definitely_inactive_with_unknown_controller_scope(landmark_source):
    country, supplements = landmark_source
    definition = supplements["landmark_definitions"][0]
    definition["country_modifiers"][0].update(controllers=[], controllers_resolved=False)
    report = summarize_country_states(
        country, _rules(), supplements=supplements, context=_context(enabled=False)
    )
    effect = report["landmark_effects"][0]
    assert effect["condition_status"] == effect["applicability_status"] == "false"
    assert report["landmark_country_modifiers"] == {}


def test_known_foreign_controller_rules_out_bonus_despite_unknown_dlc_guard(landmark_source):
    country, supplements = landmark_source
    country["states"][0]["history_declarations"].append({"field": "controller", "value": "GER"})
    supplements["landmark_definitions"][0]["country_modifiers"][0]["controllers"] = ["FRA", "GER"]
    report = summarize_country_states(country, _rules(), supplements=supplements)
    effect = report["landmark_effects"][0]
    assert effect["condition_status"] == "unknown"
    assert effect["applicability_status"] == "false"
    assert report["landmark_country_modifiers"] == {}
