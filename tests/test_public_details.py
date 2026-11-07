"""Public source gaps and conditional labels must survive parsing."""

import json
from dataclasses import asdict

import pytest

from games.tw.multigame.detail import detail_record
from games.tw.rome2.model import load_data
from games.tw.rome2.world import DATA, import_world


def test_no_effect_in_three_kingdoms_article_is_explicit():
    record = detail_record(
        '<h1>City</h1><div id="article_body"><h3>Effects</h3><blockquote>No Effect</blockquote></div><div id="detail"></div><table class="table_stat"><tr><td><p>Food Cost</p>8</td></tr></table>'
    )
    assert record["explicit_no_effect"]
    assert record["metadata"] == {"Food Cost": "8"}
    assert record["facts"] == []


def test_conditional_edict_and_unresolved_slots_are_retained():
    record = detail_record(
        '<h1>Temple</h1><div id="detail"><h3>Effects</h3>+2 food<br>Bread and Games Edict:<br>+10 public order<br>Building slots: %n<br><h3>Other</h3>+99 food</div>'
    )
    assert record["facts"] == [
        "+2 food",
        "Bread and Games Edict: +10 public order",
        "Bread and Games Edict: Building slots: %n",
    ]
    assert not record["explicit_no_effect"]


def test_missing_effect_section_is_not_zero():
    with pytest.raises(ValueError):
        detail_record('<div id="detail"></div>')


def test_world_join_is_complete_and_rejects_missing_or_unknown_resources():
    extract = json.loads((DATA / "world_source_extract.json").read_text())
    result = import_world(load_data(), extract)
    assert len(result["regions"]) == 173
    assert len(result["conflicts"]) == 3
    with pytest.raises(ValueError, match="Incomplete resource"):
        import_world(load_data(), {**extract, "rows": extract["rows"][:-1]})
    changed = json.loads(json.dumps(extract))
    changed["rows"][0]["text"] = (
        changed["rows"][0]["text"].split("|")[0] + "|unknown.png||"
    )
    with pytest.raises(ValueError, match="Unknown resource icon"):
        import_world(load_data(), changed)


def test_native_proof_without_cp_fingerprint_is_not_reused(monkeypatch, tmp_path):
    from games.tw.rome2 import benchmark

    calls = []

    class NativeResult:
        def __init__(self, scenario, data):
            self.scenario = scenario

        def fingerprint(self):
            return "identical-cp-model"

        def optimize(self, algorithm, seconds, workers, incumbent=None):
            calls.append(self.scenario.faction)
            return {
                "scenario": asdict(self.scenario),
                "solver": {
                    "algorithm": algorithm,
                    "status": "OPTIMAL",
                    "seconds": 0,
                    "objective": 1,
                    "bound": 1,
                },
                "domestic_net_income": 1,
                "sites": {},
            }

        def reuse_optimum(self, reference):
            pytest.fail("Native optimum had no portable CP proof/layout metadata")

    monkeypatch.setattr(benchmark, "Economy", NativeResult)
    result = benchmark.main(
        [
            "--faction",
            "rom_rome",
            "--faction",
            "rom_kush",
            "--layout",
            "coastal",
            "--output",
            str(tmp_path / "results"),
        ]
    )
    assert calls == ["rom_rome", "rom_kush"]
    assert len(result["cases"]) == 2
