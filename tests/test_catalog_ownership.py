"""Catalog and scenario ownership at public engine boundaries."""

import copy
import json
import operator
import os
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from games.tw.attila.model import SnapshotOptions, compile_scenario, load_attila
from games.tw.attila.scenario import Scenario as AttilaScenario
from games.tw.immutable import FrozenMap, freeze, read_catalog, thaw
from games.tw.models.model_attila import AttilaFactions, AttilaReligion
from games.tw.rome2.catalog import load_data as rome_catalog
from games.tw.rome2.model import Economy as RomeEconomy
from games.tw.rome2.scenario import Scenario as RomeScenario
from games.tw.rome2.scenario import ScenarioModifier, Site
from games.tw.shogun2.catalog import load_data as shogun_catalog
from games.tw.shogun2.model import Economy as ShogunEconomy
from games.tw.shogun2.scenario import Province
from games.tw.shogun2.scenario import Scenario as ShogunScenario
from twoptimizer.catalog import choices


def set_item(target: Any, key: Any, value: Any) -> None:
    operator.setitem(target, key, value)


def set_attribute(target: Any, name: str, value: Any) -> None:
    setattr(target, name, value)


def test_recursive_freezing_detaches_input_and_owns_json_exports():
    source = {"nested": [{"amount": 3}], "tags": ["original"]}
    owned = freeze(source)
    source["nested"][0]["amount"] = 99
    source["tags"].append("changed")
    assert thaw(owned) == {"nested": [{"amount": 3}], "tags": ["original"]}
    with pytest.raises(TypeError):
        set_item(owned, "nested", [])
    with pytest.raises(TypeError):
        set_item(owned["nested"][0], "amount", 5)
    with pytest.raises(TypeError):
        set_item(owned["tags"], 0, "changed")
    exported = thaw(owned)
    exported["nested"][0]["amount"] = 7
    assert owned["nested"][0]["amount"] == 3
    assert copy.deepcopy(owned) is owned
    assert freeze(owned) is owned
    assert len(owned) == 2


def test_frozen_mapping_construction_also_freezes_values_and_attributes():
    nested = {"values": [1, 2]}
    owned = FrozenMap(nested)
    nested["values"].append(3)
    assert tuple(owned["values"]) == (1, 2)
    with pytest.raises(TypeError, match=r"^Catalog mappings are immutable$"):
        set_attribute(owned, "values", {})
    with pytest.raises(TypeError, match=r"^Catalog mappings are immutable$"):
        delattr(owned, "values")


def test_file_catalog_cache_refreshes_on_source_revision(tmp_path):
    source = tmp_path / "catalog.json"
    source.write_text('{"name":"first"}')
    first = read_catalog(source)
    assert read_catalog(source) is first
    stamp = source.stat().st_mtime_ns
    source.write_text('{"name":"other"}')
    os.utime(source, ns=(stamp + 1_000_000, stamp + 1_000_000))
    second = read_catalog(source)
    assert second["name"] == "other" and first["name"] == "first"
    assert second is not first


@pytest.mark.parametrize("payload", ["[]", "null", "12"])
def test_non_object_catalogs_fail_at_the_load_boundary(tmp_path, payload):
    source = tmp_path / "bad.json"
    source.write_text(payload)
    with pytest.raises(ValueError, match=r"^A catalog must contain a JSON object$"):
        read_catalog(source)


def test_invalid_json_is_not_cached(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('{"broken":')
    with pytest.raises(json.JSONDecodeError):
        read_catalog(source)
    source.write_text('{"valid":true}')
    assert read_catalog(source)["valid"] is True


@pytest.mark.parametrize("loader", [rome_catalog, lambda: shogun_catalog()[0]])
def test_imported_catalog_records_cannot_be_changed_between_runs(loader):
    data = loader()
    key = next(iter(data["buildings"]))
    building = data["buildings"][key]
    with pytest.raises(TypeError):
        set_item(data["buildings"], key, {})
    with pytest.raises(TypeError):
        set_item(building, "name", "corrupted")
    assert loader()["buildings"][key]["name"] == building["name"]


def test_rome_engine_detaches_custom_catalog_before_compiling(tiny):
    scenario = RomeScenario("rom_rome", (Site("capital", major=True), Site("town")))
    economy = RomeEconomy(scenario, tiny)
    before = economy.fingerprint()
    tiny["buildings"]["rome_city_4"]["effects"].clear()
    tiny["factions"]["rom_rome"]["traits"]["parties"].clear()
    assert economy.fingerprint() == before
    with pytest.raises(TypeError):
        set_item(economy.data["buildings"]["rome_city_4"], "level", 1)


def test_shogun_engine_does_not_retain_caller_owned_rules():
    catalog, rules = thaw(shogun_catalog())
    scenario = ShogunScenario("oda", (Province("jap_sado"),))
    economy = ShogunEconomy(scenario, catalog, rules)
    income = economy.optimize(workers=1)["domestic_tax_income"]
    rules["provinces"]["jap_sado"]["farm_multiplier"] = 999
    catalog["buildings"].clear()
    assert economy.optimize(workers=1)["domestic_tax_income"] == income


def test_typed_campaign_inputs_and_exports_are_independent():
    raw = {
        "regions": {"r": {"food": 4, "wealth_percent": {"industry": 20}}},
        "campaign": {"active_trade_routes": 2, "poor_fertility_regions": ["r"]},
        "targets": [{"metric": "growth", "scope": "faction", "value": 5}],
    }
    scenario = AttilaScenario(raw)
    raw["regions"]["r"]["food"] = 99
    assert scenario.regions["r"].food == 4
    assert scenario.campaign.active_trade_routes == 2
    assert scenario.targets[0].recipient == "faction"
    with pytest.raises(FrozenInstanceError):
        set_attribute(scenario.regions["r"], "food", 2)
    with pytest.raises(TypeError):
        set_item(scenario.regions["r"].wealth_percent, "industry", 100)
    exported = scenario.to_dict()
    exported["campaign"]["poor_fertility_regions"].clear()
    assert scenario.campaign.poor_fertility_regions == ("r",)
    assert "target" not in scenario.targets[0].to_dict()


def test_scenario_modifier_provenance_is_typed_and_detached():
    raw = {"kind": "wealth_percent", "value": 5, "targets": ["industry"], "name": "Source"}
    modifier = ScenarioModifier.from_dict(raw)
    raw["targets"].clear()
    assert modifier.targets == ("industry",) and modifier.name == "Source"
    assert modifier.to_dict()["targets"] == ["industry"]
    with pytest.raises(FrozenInstanceError):
        set_attribute(modifier, "value", 100)


@pytest.mark.parametrize(
    "modifier",
    [
        ScenarioModifier("unrecognized", 1),
        ScenarioModifier("wealth_percent", 1, ("not-a-category",)),
    ],
)
def test_invalid_typed_modifiers_are_rejected_before_building(tiny, modifier):
    scenario = RomeScenario("rom_rome", (Site("capital", major=True),), modifiers=(modifier,))
    with pytest.raises(ValueError, match="Unsupported explicit scenario modifier"):
        RomeEconomy(scenario, tiny)


def test_attila_catalog_templates_have_no_decision_state():
    parser = load_attila(
        AttilaFactions.ATT_FACT_EASTERN_ROMAN_EMPIRE, AttilaReligion.CHRIST_ORTHODOX
    )
    key = next(key for key, entry in parser.buildings["att"].items() if entry.metadata is not None)
    template = parser.buildings["att"][key]
    with pytest.raises(FrozenInstanceError):
        set_attribute(template, "name", "changed")
    with pytest.raises(TypeError):
        set_item(template.raw_effects, ("effect", "scope"), 99)
    assert template.metadata is not None
    with pytest.raises(TypeError):
        set_item(template.metadata["metadata"], "upkeep", 0)
    province = next(p for p in parser.provinces.values() if p.print_name == "Thracia")
    first = compile_scenario([province], SnapshotOptions(fertility=5))
    second = compile_scenario([province], SnapshotOptions(fertility=5))
    assert first.economy is not None and second.economy is not None
    first_building = first.economy.buildings[0]
    other = second.economy.by_id[first_building.name]
    assert first_building is not other and first_building.lp_variable is not other.lp_variable
    first_building.raw_effects.clear()
    assert other.raw_effects
    assert not hasattr(template, "lp_variable")


def test_cached_ui_choices_cannot_change_future_requests():
    original = choices("rome2")
    with pytest.raises(TypeError):
        set_item(original, "default_faction", "missing")
    with pytest.raises(TypeError):
        set_item(original["factions"], 0, ("Wrong", "missing"))
    assert choices("rome2")["default_faction"] == "rom_rome"


def test_file_catalog_cache_detects_size_changes_with_preserved_timestamp(tmp_path):
    source = tmp_path / "catalog.json"
    source.write_text('{"value":1}')
    first = read_catalog(source)
    stamp = source.stat()
    source.write_text('{"value":1234567}')
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert read_catalog(source)["value"] == 1234567
    assert first["value"] == 1


def test_repeated_native_and_linear_builds_have_independent_accumulators(tiny):
    scenario = RomeScenario("rom_rome", (Site("capital", major=True), Site("town")))
    economy = RomeEconomy(scenario, tiny)
    reports = [economy.optimize(algorithm, workers=1) for algorithm in ("cp-sat", "cbc", "cp-sat")]
    assert all(row["solver"]["status"] == "OPTIMAL" for row in reports)
    assert len({row["domestic_net_income"] for row in reports}) == 1
    assert reports[0]["proof_fingerprint"] == reports[2]["proof_fingerprint"]


def test_native_scip_constant_constraints_keep_boolean_semantics():
    from games.tw.rome2.backends import NativeSCIP

    backend = NativeSCIP()
    variable = backend.BoolVar("selected")
    backend.Add(True)
    backend.Add(variable == 1)
    backend.Maximize(variable)
    backend.model.optimize()
    assert str(backend.model.getStatus()) == "optimal"
    backend.model.freeTransform()
    backend.Add(False)
    backend.model.optimize()
    assert str(backend.model.getStatus()) == "infeasible"


def test_modifier_roundtrip_preserves_explicit_null_source_fields():
    record = {"kind": "wealth_percent", "value": 5, "targets": [], "interpretation": None}
    assert ScenarioModifier.from_dict(record).to_dict() == record
    with pytest.raises(ValueError, match="Unknown scenario modifier fields"):
        ScenarioModifier.from_dict({**record, "unrecognized": 1})
