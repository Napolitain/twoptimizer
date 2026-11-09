"""Economic inheritance follows source archetypes, never convenient defaults."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from games.hoi4.data_pipeline.equipment_resolution import (
    resolve_equipment_catalog,
    resolve_equipment_variant,
)
from games.hoi4.data_pipeline.equipment_sources import read_equipment_resolution_inputs


def _definition(identifier, *, resources=None, **fields):
    return {
        "id": identifier,
        "line": 1,
        "source": {"path": f"{identifier}.txt", "sha256": "a" * 64},
        "declarations": [
            {"field": field, "value": value, "line": index}
            for index, (field, value) in enumerate(fields.items(), 2)
        ],
        "resources": []
        if resources is None
        else [
            {
                "line": 10,
                "declarations": [
                    {"field": key, "value": value, "line": 11} for key, value in resources.items()
                ],
                "unresolved_statements": [],
            }
        ],
        "unresolved_statements": [],
    }


def _index(payload):
    return {row["id"]: row for row in resolve_equipment_catalog(payload)["equipment"]}


def test_archetype_inheritance_does_not_use_predecessor_values():
    payload = {
        "equipment": [
            _definition("family", build_cost_ic=4, resources={"steel": 2}),
            _definition("older", archetype="family", build_cost_ic=99, resources={"steel": 9}),
            _definition("current", archetype="family", parent="older"),
        ]
    }
    before = deepcopy(payload)
    current = _index(payload)["current"]
    assert current["base_cost_ic"] == 4
    assert current["base_resources"] == {"steel": 2}
    assert current["status"] == "resolved_base"
    assert current["archetype_id"] == "family"
    assert current["predecessor_id"] == "older"
    assert current["field_sources"]["base_cost_ic"][0]["equipment"] == "family"
    assert payload == before
    current["base_resources"]["steel"] = 100
    assert _index(payload)["current"]["base_resources"] == {"steel": 2}


def test_no_resources_or_archetype_never_become_zero_defaults():
    payload = {
        "equipment": [_definition("older", build_cost_ic=5), _definition("child", parent="older")]
    }
    result = _index(payload)
    assert result["older"]["status"] == "partial"
    assert result["older"]["base_resources"] is None
    assert result["child"]["base_cost_ic"] is None
    assert result["child"]["base_resources"] is None
    assert (
        _index({"equipment": [_definition("empty", build_cost_ic=0, resources={})]})["empty"][
            "base_resources"
        ]
        == {}
    )


def test_partial_resource_overrides_remain_unknown_but_complete_maps_resolve():
    payload = {
        "equipment": [
            _definition("family", build_cost_ic=4, resources={"steel": 2, "tungsten": 1}),
            _definition("partial", archetype="family", resources={"steel": 3}),
            _definition("complete", archetype="family", resources={"steel": 3, "tungsten": 0}),
        ]
    }
    result = _index(payload)
    assert result["partial"]["base_cost_ic"] == 4
    assert result["partial"]["base_resources"] is None
    assert result["partial"]["unknowns"][0]["reason"] == "partial_resource_override_unverified"
    assert result["complete"]["base_resources"] == {"steel": 3, "tungsten": 0}


@pytest.mark.parametrize("value", [True, -1, float("inf"), "@cost"])
def test_invalid_costs_and_ambiguous_definitions_fail_explicitly(value):
    record = _definition("item", build_cost_ic=value, resources={})
    row = _index({"equipment": [record]})["item"]
    assert row["base_cost_ic"] is None
    assert row["unknowns"][0]["reason"] == "ambiguous_or_invalid_number"
    row = _index({"equipment": [record, record]})["item"]
    assert row["status"] == "unresolved"
    assert row["unknowns"][0]["reason"] == "ambiguous_equipment"


def test_archetype_cycles_terminate_and_do_not_hide_missing_values():
    result = _index(
        {"equipment": [_definition("a", archetype="b"), _definition("b", archetype="a")]}
    )
    assert result["a"]["status"] == result["b"]["status"] == "unresolved"
    assert any(row["reason"] == "archetype_cycle" for row in result["a"]["unknowns"])


def test_duplicate_generation_preserves_original_stats_and_explicit_only_archetype():
    duplicate = {
        **_definition("derived", archetype="base"),
        "duplication_details_available": True,
        "for_each": [],
    }
    only = {
        **_definition("arch_only", archetype="base", only_duplicate_archetype=True),
        "duplication_details_available": True,
    }
    payload = {
        "equipment": [
            _definition("base", build_cost_ic=2, resources={"steel": 1}),
            _definition("base_0", archetype="base", build_cost_ic=3),
            _definition("base_1", archetype="base", parent="base_0", build_cost_ic=4),
        ],
        "duplicate_archetypes": [duplicate, only],
    }
    rows = _index(payload)
    assert rows["derived_1"]["base_cost_ic"] == 4
    assert rows["derived_1"]["base_resources"] == {"steel": 1}
    assert (
        rows["derived_1"]["field_sources"]["base_resources"][-1]["source"]["path"] == "derived.txt"
    )
    assert "arch_only" in rows and "arch_only_0" not in rows
    duplicate["for_each"] = [
        {"declarations": [], "unresolved_statements": [{"field": "build_cost_ic"}]}
    ]
    rows = _index(payload)
    assert rows["derived_0"]["base_cost_ic"] is None
    assert rows["derived"]["base_cost_ic"] == 2


def test_overlay_evidence_and_technology_unlocks_survive_resolution():
    record = _definition("item", build_cost_ic=3, resources={"steel": 1})
    record["declarations"][0]["patch_overlay"] = {"target_field_supported": True, "id": "verified"}
    payload = {
        "equipment": [record],
        "technology_unlocks": [
            {"technology": "tech", "equipment": ["item"], "source": {"path": "tech.txt"}}
        ],
    }
    result = _index(payload)["item"]
    assert result["field_sources"]["base_cost_ic"][0]["patch_overlay"]["id"] == "verified"
    assert result["unlocked_by"][0]["technology"] == "tech"
    assert result["eligibility_evaluated"] is False


def test_source_reader_preserves_repeated_module_blocks_and_hashes(tmp_path):
    root = tmp_path / "common"
    equipment = root / "units" / "equipment"
    (equipment / "modules").mkdir(parents=True)
    (root / "technologies").mkdir()
    payload = (
        b"\xef\xbb\xbfequipments = { base = { build_cost_ic = 2 resources = { steel = 1 } "
        b"module_slots = {} } base_1 = { archetype = base } }"
    )
    (equipment / "base.txt").write_bytes(payload)
    (equipment / "modules" / "module.txt").write_text(
        'equipment_modules = { limit = { has_dlc = "Test" } module = { '
        "multiply_stats = { build_cost_ic = .1 } multiply_stats = { build_cost_ic = -.05 } } }"
    )
    (root / "technologies" / "tech.txt").write_text(
        "technologies = { tech = { enable_equipments = { base_1 } } }"
    )
    imported = read_equipment_resolution_inputs(tmp_path)
    assert len(imported["modules"]) == 1
    assert len(imported["modules"][0]["multiply_stats"]) == 2
    assert imported["modules"][0]["conditions"]
    assert imported["equipment"][0]["source"]["sha256"] == sha256(payload).hexdigest()
    assert len(imported["input_sources"]) == 3
    row = _index(imported)["base_1"]
    assert row["requires_variant"] is True
    assert row["unlocked_by"][0]["technology"] == "tech"
    with pytest.raises(ValueError, match="source root"):
        read_equipment_resolution_inputs(tmp_path / "missing")


def test_bundled_basic_equipment_resolves_actual_source_requirements():
    payload = json.loads(Path("games/hoi4/data/public_reference/equipment.json").read_text())
    rows = _index(payload)
    expected = {
        "infantry_equipment_0": (0.43, {"steel": 2}),
        "infantry_equipment_1": (0.5, {"steel": 2}),
        "support_equipment_1": (4, {"aluminium": 1, "steel": 2}),
        "artillery_equipment_1": (3.5, {"tungsten": 1, "steel": 2}),
    }
    for identifier, (cost, resources) in expected.items():
        assert rows[identifier]["status"] == "resolved_base"
        assert rows[identifier]["base_cost_ic"] == cost
        assert rows[identifier]["base_resources"] == resources
        assert rows[identifier]["requires_variant"] is False


def test_named_variants_never_substitute_chassis_cost_for_unknown_designer_cost():
    payload = {"equipment": [_definition("rifle", build_cost_ic=0.5, resources={"steel": 2})]}
    catalog = resolve_equipment_catalog(payload)
    cosmetic = resolve_equipment_variant(catalog, {"type": "rifle", "name": "Named rifle"})
    assert cosmetic["variant_cost_ic"] == 0.5
    variant = {
        "type": "rifle",
        "name": "Designed",
        "modules": [{"declarations": [{"field": "slot", "value": "module", "line": 1}]}],
    }
    module = {
        "id": "module",
        "multiply_stats": [
            {
                "declarations": [
                    {"field": "build_cost_ic", "value": -0.05, "patch_overlay": {"id": "patch"}}
                ]
            }
        ],
    }
    resolved = resolve_equipment_variant(catalog, variant, module_records=[module])
    assert resolved["variant_cost_ic"] is None
    assert resolved["base"]["base_cost_ic"] == 0.5
    assert (
        resolved["modules"][0]["definitions"][0]["multiply_stats"][0]["declarations"][0][
            "patch_overlay"
        ]["id"]
        == "patch"
    )
    assert resolved["unknowns"][0]["reason"] == "designer_aggregation_not_validated"
    assert resolve_equipment_variant(catalog, {"type": "missing"})["status"] == "unresolved_variant"


@pytest.fixture
def upgrade_inputs(tmp_path):
    directory = tmp_path / "common" / "units" / "equipment"
    (directory / "upgrades").mkdir(parents=True)
    (directory / "base.txt").write_text(
        "equipments = { base = { build_cost_ic = 2 resources = { steel = 1 } } }"
    )
    # Shape and values follow the pinned land_upgrades source. Threshold 10
    # replaces the threshold-5 map; it does not add a second steel requirement.
    (directory / "upgrades" / "land.txt").write_text(
        "upgrades = { armor = { max_level = 20 "
        "add_stats = { build_cost_ic = .2 } "
        "resource_cost_thresholds = { 5 = { steel = 1 } 10 = { steel = 1 } } } }"
    )
    return read_equipment_resolution_inputs(tmp_path)


def _resolve_upgrade(inputs, level):
    return resolve_equipment_variant(
        resolve_equipment_catalog(inputs),
        {
            "type": "base",
            "upgrades": [{"declarations": [{"field": "armor", "value": level, "line": 1}]}],
        },
        upgrade_records=inputs["upgrades"],
    )


@pytest.mark.parametrize(
    "level,threshold", [(0, None), (4, None), (5, 5), (9, 5), (10, 10), (20, 10)]
)
def test_upgrade_resource_thresholds_replace_instead_of_accumulating(
    upgrade_inputs, level, threshold
):
    result = _resolve_upgrade(upgrade_inputs, level)
    upgrade = result["upgrades"][0]
    assert upgrade["definitions"][0]["add_stats"][0]["declarations"][0]["value"] == 0.2
    effects = upgrade["selected_effects"]
    assert effects["level"] == level
    assert effects["status"] == "selected_inputs"
    if threshold is None:
        assert effects["selected_resource_threshold"] is None
    else:
        selected = effects["selected_resource_threshold"]
        assert selected["level"] == threshold
        assert selected["resources"] == {"steel": 1}
        assert selected["field_sources"][0]["source"]["path"].endswith("upgrades/land.txt")
        assert selected["field_sources"][0]["source"]["sha256"]
    assert result["variant_cost_ic"] is None
    assert result["variant_resources"] is None
    assert effects["aggregation_applied"] is False


@pytest.mark.parametrize("level", [-1, 1.5, True, "@value", 21])
def test_invalid_upgrade_level_cannot_select_resources(upgrade_inputs, level):
    result = _resolve_upgrade(upgrade_inputs, level)
    effects = result["upgrades"][0]["selected_effects"]
    assert effects["status"] == "unresolved_inputs"
    assert effects["selected_resource_threshold"] is None
    assert result["unknowns"][0]["reason"] in {
        "invalid_upgrade_level",
        "upgrade_level_exceeds_maximum",
    }


def test_ambiguous_upgrade_resource_thresholds_are_not_arbitrarily_selected(upgrade_inputs):
    thresholds = upgrade_inputs["upgrades"][0]["resource_cost_thresholds"][0]["thresholds"]
    thresholds.append(deepcopy(thresholds[0]))
    result = _resolve_upgrade(upgrade_inputs, 10)
    assert result["upgrades"][0]["selected_effects"]["selected_resource_threshold"] is None
    assert result["unknowns"][0]["reason"] == "invalid_or_duplicate_resource_threshold"
