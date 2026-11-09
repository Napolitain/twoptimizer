"""Release-note corrections change only uniquely identified, guarded source fields."""

from copy import deepcopy

import pytest

from games.hoi4.data_pipeline.patch_overlay import apply_patch_overlays, load_patch_overlays
from games.hoi4.data_pipeline.public_import import load_reference_equipment


def _unit(payload, identifier="anti_air"):
    return next(row for row in payload["units"] if row["id"] == identifier)


def _need(payload, identifier="anti_air"):
    return _unit(payload, identifier)["need"][0]["declarations"][0]


def _equipment_cost(payload, identifier):
    record = next(row for row in payload["equipment"] if row["id"] == identifier)
    return next(row["value"] for row in record["declarations"] if row["field"] == "build_cost_ic")


def test_bundled_patch_notes_correct_verified_old_fields_without_rewriting_raw_data():
    raw = load_reference_equipment()
    original = deepcopy(raw)
    patched, report = apply_patch_overlays(raw)
    assert raw == original
    assert _need(raw)["value"] == 20
    assert _need(patched)["value"] == 24
    assert _need(patched, "field_guns")["value"] == 6
    assert _need(patched, "rocket_battery")["value"] == 6
    assert _equipment_cost(patched, "gw_armored_car_equipment") == 3
    assert _equipment_cost(patched, "armored_car_equipment") == 4.5
    assert _equipment_cost(patched, "armored_car_equipment_2") == 6
    assert _equipment_cost(patched, "armored_car_at_equipment") == 7.5
    assert report["counts"]["applied"] == 7
    assert report["full_version_validated"] is report["runnable_scenario_established"] is False
    assert _unit(patched)["source"] == _unit(raw)["source"]
    evidence = _need(patched)["patch_overlay"]
    assert evidence["observed_value"] == 20
    assert evidence["new_value"] == 24
    assert evidence["target_field_supported"] is True
    assert evidence["release_source"]["announcement_id"] == "712286322480383531"
    assert evidence["target"]["checksum"] == "0bdb"
    assert load_reference_equipment() == original


def test_module_stat_and_experience_corrections_are_guarded_independently():
    payload = {
        "modules": [
            {
                "id": "easy_maintenance",
                "source": {"path": "common/units/equipment/modules/00_tank_modules.txt"},
                "declarations": [{"field": "xp_cost", "value": 30}],
                "add_stats": [{"declarations": [{"field": "reliability", "value": 0.1}]}],
                "multiply_stats": [{"declarations": [{"field": "build_cost_ic", "value": -0.075}]}],
            }
        ]
    }
    patched, report = apply_patch_overlays(payload)
    module = patched["modules"][0]
    assert module["declarations"][0]["value"] == 20
    assert module["add_stats"][0]["declarations"][0]["value"] == 0.075
    assert module["multiply_stats"][0]["declarations"][0]["value"] == -0.05
    assert report["counts"] == {"missing_record": 7, "applied": 3}
    assert payload["modules"][0]["declarations"][0]["value"] == 30


def test_reapplying_is_idempotent_and_preserves_original_correction_evidence():
    patched, _ = apply_patch_overlays(load_reference_equipment())
    again, report = apply_patch_overlays(patched)
    assert again == patched
    assert report["counts"]["already_target_value"] == 7
    assert _need(again)["patch_overlay"]["observed_value"] == 20


@pytest.mark.parametrize("value", [True, None, "20", "@equipment_need"])
def test_nonnumeric_values_never_match_the_expected_numeric_value(value):
    raw = load_reference_equipment()
    _need(raw)["value"] = value
    patched, report = apply_patch_overlays(raw)
    assert _need(patched)["value"] == value
    finding = report["fields"][0]
    assert finding["status"] == "nonnumeric_field"
    assert finding["target_field_supported"] is False
    assert finding in report["unresolved"]


def test_conflicting_values_remain_visible_but_are_not_target_supported():
    raw = load_reference_equipment()
    _need(raw)["value"] = 18
    patched, report = apply_patch_overlays(raw)
    assert _need(patched)["value"] == 18
    assert _need(patched)["patch_overlay"]["target_field_supported"] is False
    assert report["fields"][0]["status"] == "value_mismatch"
    assert report["fields"][0]["target_field_supported"] is False


def test_a_changed_previously_patched_value_cannot_retain_a_supported_field_stamp():
    patched, _ = apply_patch_overlays(load_reference_equipment())
    _need(patched)["value"] = 19
    reviewed, report = apply_patch_overlays(patched)
    assert _need(reviewed)["value"] == 19
    assert _need(reviewed)["patch_overlay"]["target_field_supported"] is False
    assert report["fields"][0]["status"] == "value_mismatch"


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ("missing_record", "missing_record"),
        ("duplicate_record", "ambiguous_record"),
        ("changed_source", "source_path_mismatch"),
        ("missing_field", "missing_field"),
        ("duplicate_field", "ambiguous_field"),
        ("duplicate_block", "ambiguous_field"),
    ],
)
def test_no_override_when_record_or_field_identity_is_ambiguous(change, status):
    raw = load_reference_equipment()
    record = _unit(raw)
    if change == "missing_record":
        raw["units"].remove(record)
    elif change == "duplicate_record":
        raw["units"].append(deepcopy(record))
    elif change == "changed_source":
        record["source"]["path"] = "modded/anti_air.txt"
    elif change == "missing_field":
        record["need"].clear()
    elif change == "duplicate_field":
        record["need"][0]["declarations"].append(deepcopy(_need(raw)))
    elif change == "duplicate_block":
        record["need"].append(deepcopy(record["need"][0]))
    original = deepcopy(raw["units"])
    manifest = load_patch_overlays()
    manifest["corrections"] = manifest["corrections"][:1]
    patched, report = apply_patch_overlays(raw, manifest)
    assert patched["units"] == original
    assert report["fields"][0]["status"] == status
    assert report["fields"][0]["target_field_supported"] is False


def test_current_value_is_retained_with_specific_patch_note_evidence():
    raw = load_reference_equipment()
    _need(raw)["value"] = 24
    patched, report = apply_patch_overlays(raw)
    assert _need(patched)["value"] == 24
    assert report["fields"][0]["status"] == "already_target_value"
    assert _need(patched)["patch_overlay"]["observed_value"] == 24
    assert report["full_version_validated"] is False


def test_loaded_patch_manifest_is_caller_owned_and_has_pinned_identifier_mapping():
    manifest = load_patch_overlays()
    assert manifest["identifier_evidence"]["revision"] == "e249d22284449ece5416b41e68c4d73f2b79e3cc"
    assert manifest["sources"]["1.19.4"]["announcement_id"] == "684142629662760620"
    manifest["corrections"].clear()
    assert len(load_patch_overlays()["corrections"]) == 10
