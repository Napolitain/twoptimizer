"""Saved scenarios retain typed regional modifiers and their original model."""

import hashlib
import json
from dataclasses import replace

import pytest

from games.tw.rome2.catalog import CATALOG
from games.tw.rome2.model import Economy
from games.tw.rome2.provenance import model_fingerprint
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
    # Generate a current report; historical reports deliberately retain their
    # original source hashes. Empty ordinary slots keep this replay test small.
    scenario = province_scenario("Italia", "rom_rome")
    scenario = replace(
        scenario,
        sites=tuple(replace(site, slots=0) for site in scenario.sites),
        external_food=1000,
        order_offset=1000,
    )
    case = Economy(scenario).optimize(workers=1)
    assert case["solver"]["status"] == "OPTIMAL" and case["scenario"]["modifiers"]
    report = {
        "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        "model_sha256": model_fingerprint(),
        "cases": [case],
    }
    path = tmp_path / "named-province.json"
    path.write_text(json.dumps(report))
    assert verify([path])["verified_feasible_layouts"] == 1
    for field in ("catalog_sha256", "model_sha256"):
        path.write_text(json.dumps({**report, field: "0" * 64}))
        with pytest.raises(ValueError, match="Stale data/model snapshot"):
            verify([path])
