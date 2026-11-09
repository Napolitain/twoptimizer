"""Starting army extraction preserves provenance, incomplete sources and unknowns."""

import hashlib
from copy import deepcopy
from dataclasses import replace

import pytest

from games.hoi4.data_pipeline.oob_resolution import resolve_starting_army
from games.hoi4.data_pipeline.selection import SelectionContext
from games.hoi4.data_pipeline.syntax import Document, parse_script, recover_complete_children
from games.hoi4.planning.time import CampaignDate


def _facts(**values):
    return [{"field": field, "value": value} for field, value in values.items()]


def _inputs(division="", *, country="", effects="", needs=None):
    country_doc = parse_script("set_oob = LAND\n" + country, source="history/countries/FRA.txt")
    land_doc = parse_script(
        'units = { division = { name = "First" location = 1 division_template = "Infantry" '
        + division
        + "} }\ninstant_effect = {"
        + effects
        + "}",
        source="history/units/LAND.txt",
    )
    profile = {
        "tag": "FRA",
        "source": {"path": country_doc.source, "sha256": country_doc.sha256},
        "oob_candidates": [
            {
                "source": {"path": land_doc.source, "sha256": land_doc.sha256},
                "templates": [
                    {
                        "name": "Infantry",
                        "line": 1,
                        "regiments": [{"unit": "infantry", "line": 1}],
                        "support": [],
                        "unresolved_statements": [],
                    }
                ],
            }
        ],
    }
    equipment = {
        "units": [
            {
                "id": "infantry",
                "declarations": _facts(manpower=1000, training_time=90),
                "source": {"path": "common/units/infantry.txt", "sha256": "unit-hash"},
                "need": [
                    {
                        "declarations": _facts(**(needs or {"rifles": 100})),
                        "unresolved_statements": [],
                    }
                ],
                "unresolved_statements": [],
            }
        ],
        "equipment": [
            {"id": "rifles_1", "declarations": _facts(archetype="rifles")},
            {"id": "rifles_0", "declarations": _facts(archetype="rifles")},
            {"id": "rifles", "declarations": _facts(is_archetype=True)},
        ],
    }
    context = SelectionContext(CampaignDate(1936, 1, 1, 12), frozenset(), frozenset())
    return profile, equipment, country_doc, {"LAND": land_doc}, context


def test_documented_equipment_and_experience_defaults_do_not_fill_manpower():
    inputs = _inputs()
    before = deepcopy(inputs[:2])
    report = resolve_starting_army(*inputs)
    division = report["divisions"][0]
    assert division["equipment_by_archetype"] == {"rifles": 100}
    assert division["start_equipment_factor"]["origin"] == "documented_default"
    assert division["start_experience_factor"]["value"] == 0
    assert division["manpower_allocated"] is None
    assert division["manpower_status"] == "requires_available_reserve"
    assert report["summary"]["full_manpower_requirement"] == 1000
    assert report["stockpile_totals"] is None
    assert inputs[:2] == before


def test_fractional_equipment_rounding_does_not_poison_independent_quantities():
    report = resolve_starting_army(
        *_inputs("start_equipment_factor = 0.5", needs={"rifles": 100, "support": 3})
    )
    division = report["divisions"][0]
    assert division["equipment_by_archetype"] == {"rifles": 50, "support": None}
    assert division["unknowns"] == [
        {"code": "equipment_rounding_unverified", "equipment": "support"}
    ]
    assert report["summary"]["full_equipment_requirements"] == {"rifles": 100, "support": 3}


@pytest.mark.parametrize(
    "declaration",
    [
        "start_equipment_factor = yes",
        "start_equipment_factor = -1",
        "start_equipment_factor = 2",
        "start_equipment_factor = 1 start_equipment_factor = .5",
    ],
)
def test_invalid_or_duplicate_factors_stay_unknown(declaration):
    division = resolve_starting_army(*_inputs(declaration))["divisions"][0]
    assert division["start_equipment_factor"]["value"] is None
    assert division["equipment_by_archetype"] is None


def test_forced_variant_identity_and_amount_are_source_backed():
    report = resolve_starting_army(
        *_inputs(
            "force_equipment_variants = { rifles_1 = { owner = FRA amount = 14 "
            'version_name = "Model" } }'
        )
    )
    division = report["divisions"][0]
    assert division["equipment_by_archetype"] == {"rifles": 14}
    assert division["forced_equipment"][0]["creator"] == "FRA"
    assert division["forced_equipment"][0]["archetype"] == "rifles"


@pytest.mark.parametrize(
    "forced",
    [
        "rifles_1 = { owner = FRA amount = 14 }",
        "rifles_1 = { owner = FRA } rifles_0 = { owner = FRA }",
    ],
)
def test_forced_quantity_interactions_are_not_guessed(forced):
    report = resolve_starting_army(
        *_inputs("start_equipment_factor = .5 force_equipment_variants = { " + forced + " }")
    )
    assert report["divisions"][0]["equipment_by_archetype"]["rifles"] is None


def test_unknown_forced_family_is_reported():
    report = resolve_starting_army(
        *_inputs("force_equipment_variants = { unknown = { owner = FRA } }")
    )
    assert report["divisions"][0]["unknowns"][0]["code"] == "forced_equipment_family_unresolved"


def test_production_percentages_and_missing_defaults_are_distinct():
    effects = """
      add_equipment_production = { equipment = { type = rifles_1 creator = FRA }
        requested_factories = 2 progress = .3 efficiency = 50 }
      add_equipment_production = { equipment = { type = rifles_0 } }
    """
    report = resolve_starting_army(*_inputs(effects=effects))
    line = report["production_lines"][0]
    assert line["resolved_literals"] == {
        "requested_factories": 2,
        "progress_fraction": 0.3,
        "efficiency_ratio": 0.5,
    }
    assert line["assigned_factories"] is None
    assert set(report["production_lines"][1]["unknown_defaults"]) == {
        "requested_factories",
        "progress",
        "efficiency",
    }


def test_tutorial_guard_needs_explicit_context_and_ignores_portrait_guard():
    inputs = _inputs(
        country="if = { limit = { unknown = yes } portrait = something }",
        effects="if = { limit = { is_tutorial = no } "
        "add_equipment_production = { equipment = { type = rifles_1 } } }",
    )
    unknown = resolve_starting_army(*inputs)
    assert len(unknown["blockers"]) == 1
    assert unknown["production_lines"] == []
    normal = resolve_starting_army(*inputs, tutorial=False)
    assert len(normal["production_lines"]) == 1
    assert normal["blockers"] == []
    contextual = (*inputs[:-1], replace(inputs[-1], tutorial=False))
    assert resolve_starting_army(*contextual)["tutorial"] is False


def test_stockpile_deltas_and_variant_modules_are_not_resolved_inventory():
    country = """
      add_equipment_to_stockpile = { type = rifles_1 amount = 20 }
      create_equipment_variant = { name = "Model" type = tank_chassis
        modules = { gun = cannon_1 } upgrades = { engine = 2 } }
      every_owned_state = { add_manpower = 100 }
    """
    report = resolve_starting_army(*_inputs(country=country))
    assert report["stockpile_changes"][0]["producer"] == "FRA"
    assert report["stockpile_changes"][0]["requested_change"] == 20
    assert report["stockpile_changes"][0]["applied_change"] is None
    assert report["variants"][0]["modules"][0]["declarations"][0]["value"] == "cannon_1"
    assert report["unhandled_army_effects"][0]["field"] == "every_owned_state"


def test_balanced_recovered_production_keeps_original_hash():
    inputs = _inputs()
    original = inputs[3]["LAND"]
    text = (
        original.text
        + "\ninstant_effect = { add_equipment_production = { equipment = { type = rifles_1 } }"
    )
    prefix = parse_script(original.text, source=original.source)
    document = Document(
        original.source, text, hashlib.sha256(text.encode()).hexdigest(), prefix.root
    )
    recovery = recover_complete_children(
        text, text.rfind("instant_effect") + len("instant_effect = "), source=original.source
    )
    profile = deepcopy(inputs[0])
    profile["oob_candidates"][0]["source"]["sha256"] = document.sha256
    report = resolve_starting_army(
        profile,
        inputs[1],
        inputs[2],
        {"LAND": document},
        inputs[4],
        partial_effects={document.source: recovery.entries},
    )
    line = report["production_lines"][0]
    assert line["parent_incomplete"]
    assert line["source"]["sha256"] == document.sha256


def test_missing_and_ambiguous_templates_and_oob_sources_are_visible():
    inputs = _inputs()
    profile = deepcopy(inputs[0])
    profile["oob_candidates"][0]["templates"] *= 2
    report = resolve_starting_army(profile, *inputs[1:])
    assert report["divisions"][0]["template_index"] is None
    assert report["summary"]["full_manpower_requirement"] is None
    missing = resolve_starting_army(*inputs[:3], {}, inputs[4])
    assert missing["blockers"][0]["code"] == "missing_oob_document"
    assert not missing["land_roster_source_loaded"]
    assert missing["summary"]["full_equipment_requirements"] is None
    assert missing["summary"]["full_manpower_requirement"] is None


def test_hash_mismatch_cannot_produce_resolved_template_data():
    inputs = _inputs()
    profile = deepcopy(inputs[0])
    profile["oob_candidates"][0]["source"]["sha256"] = "mismatch"
    report = resolve_starting_army(profile, *inputs[1:])
    assert report["blockers"][0]["code"] == "template_source_hash_mismatch"
    profile["source"]["sha256"] = "mismatch"
    with pytest.raises(ValueError, match="hashes differ"):
        resolve_starting_army(profile, *inputs[1:])


def test_unknown_manpower_requirement_preserves_known_equipment():
    inputs = _inputs()
    equipment = deepcopy(inputs[1])
    equipment["units"][0]["declarations"] = _facts(training_time=90)
    report = resolve_starting_army(inputs[0], equipment, *inputs[2:])
    assert report["summary"]["full_manpower_requirement"] is None
    assert report["summary"]["full_equipment_requirements"] == {"rifles": 100}


def test_generated_logistics_inputs_are_preserved_without_assuming_empty_reserves():
    report = resolve_starting_army(
        *_inputs(country="starting_train_buffer = 2 starting_truck_buffer = .8 set_convoys = 100")
    )
    assert [(row["field"], row["value"]) for row in report["logistics_declarations"]] == [
        ("starting_train_buffer", 2),
        ("starting_truck_buffer", 0.8),
        ("set_convoys", 100),
    ]
    assert all(row["resolved_inventory"] is None for row in report["logistics_declarations"])
    assert report["stockpile_totals"] is None
    assert len(report["unhandled_army_effects"]) == 3


def test_conditional_logistics_declaration_is_relevant_to_unknown_inventory():
    report = resolve_starting_army(
        *_inputs(country="if = { limit = { unknown = yes } set_convoys = 100 }")
    )
    assert len(report["blockers"]) == 1
    assert report["logistics_declarations"] == []


def test_conditional_units_are_selected_or_reported_without_inventing_divisions():
    inputs = _inputs()
    original = inputs[3]["LAND"]
    document = parse_script(
        "units = { if = { limit = { is_tutorial = no } "
        'division = { division_template = "Infantry" } } '
        'if = { limit = { unknown = yes } division = { division_template = "Infantry" } } }',
        source=original.source,
    )
    profile = deepcopy(inputs[0])
    profile["oob_candidates"][0]["source"]["sha256"] = document.sha256
    report = resolve_starting_army(
        profile, inputs[1], inputs[2], {"LAND": document}, inputs[4], tutorial=False
    )
    assert len(report["divisions"]) == 1
    assert len(report["blockers"]) == 1
    assert report["unhandled_army_effects"] == []
