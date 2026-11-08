"""Saved scenarios retain typed regional modifiers and their original model."""

import json
from pathlib import Path

import pytest

from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, ScenarioModifier
from games.tw.rome2.verify import verify
from games.tw.rome2.world import province_scenario


def test_named_scenario_json_roundtrip_preserves_modifiers_and_model():
    scenario = province_scenario("Italia", "rom_rome")
    raw = json.loads(json.dumps(scenario.to_dict()))
    restored = Scenario.from_dict(raw)
    assert restored.modifiers
    assert all(isinstance(row, ScenarioModifier) for row in restored.modifiers)
    assert restored.to_dict() == raw
    assert Economy(restored).fingerprint() == Economy(scenario).fingerprint()


def test_saved_scenario_rejects_unknown_modifier_fields():
    raw = province_scenario("Italia", "rom_rome").to_dict()
    raw["modifiers"][0]["unknown_modifier_field"] = 1
    with pytest.raises(ValueError, match="Unknown scenario modifier fields"):
        Scenario.from_dict(raw)


def test_named_province_report_replays_after_json_deserialization(tmp_path):
    report = json.loads(Path("reports/rome2-province-comparison.json").read_text())
    report["cases"] = [next(case for case in report["cases"] if case["scenario"]["modifiers"])]
    path = tmp_path / "named-province.json"
    path.write_text(json.dumps(report))
    assert verify([path])["verified_feasible_layouts"] == 1
