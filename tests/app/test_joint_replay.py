"""Stored joint reports replay local economics as well as realm totals."""

import copy
import hashlib
import json

import pytest

from games.tw.rome2 import verify as replay
from games.tw.rome2.catalog import CATALOG
from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario, joint_model_fingerprint
from games.tw.rome2.provenance import model_fingerprint
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import tiny_catalog


def test_joint_replay_checks_recipient_details_and_source_identity(tmp_path, monkeypatch):
    data = tiny_catalog()
    monkeypatch.setattr(replay, "load_data", lambda: data)
    scenario = HoldingScenario.from_provinces(
        tuple(
            Scenario(
                "rom_rome",
                (Site(name, major=True, slots=1),),
                name=name,
                external_food=3,
                order_offset=3,
            )
            for name in ("first", "second")
        ),
        (("first", "second"),),
    )
    case = HoldingEconomy(scenario, data).optimize("cp-sat", seconds=5, workers=1)
    assert case["solver"]["status"] == "OPTIMAL"
    payload: dict = {
        "catalog_sha256": hashlib.sha256(CATALOG.read_bytes()).hexdigest(),
        "model_sha256": model_fingerprint(),
        "joint_model_sha256": joint_model_fingerprint(),
        "cases": [case],
    }
    path = tmp_path / "joint.json"
    path.write_text(json.dumps(payload))
    assert replay.verify([path])["verified_feasible_layouts"] == 1
    assert replay.verify([path])["optimal_solver_results"] == 1

    wrong = copy.deepcopy(payload)
    wrong["cases"][0]["provinces"]["first"]["tax_modifier_percent_net"] += 1
    path.write_text(json.dumps(wrong))
    with pytest.raises(AssertionError, match="tax_modifier_percent_net"):
        replay.verify([path])
    wrong = copy.deepcopy(payload)
    del wrong["cases"][0]["provinces"]["first"]
    path.write_text(json.dumps(wrong))
    with pytest.raises(AssertionError, match="Stored provinces differ"):
        replay.verify([path])
    payload["joint_model_sha256"] = "stale"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="Stale joint model snapshot"):
        replay.verify([path])
    del payload["joint_model_sha256"]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="missing its model fingerprint"):
        replay.verify([path])
