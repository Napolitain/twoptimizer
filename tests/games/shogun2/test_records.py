"""Shogun source interpretation is immutable and occurs before model construction."""

from dataclasses import FrozenInstanceError

import pytest

from games.tw.immutable import thaw
from games.tw.shogun2 import domain, effects
from games.tw.shogun2.catalog import load_data
from games.tw.shogun2.domain import parse_building, parse_catalog
from games.tw.shogun2.model import Economy
from games.tw.shogun2.scenario import Province, Scenario
from tests.support.ownership import set_attribute, set_item


def test_parsed_buildings_preserve_recognized_and_unsupported_source_facts():
    source, _ = load_data()
    catalog = parse_catalog(source)
    for key, raw in source["buildings"].items():
        facts = (*raw["facts"], *raw.get("clan_facts", ()))
        building = catalog.buildings[key]
        assert building.effects == tuple(e for text in facts if (e := effects.parse(text)))
        assert building.unsupported_facts == tuple(
            text for text in facts if not effects.parse(text)
        )
        assert building.unique == effects.unique_key(raw)
        assert building.family == effects.family(raw)
    assert catalog.buildings["sho_portuguese_land_sold"].family == "portuguese"


def test_parsed_catalog_owns_source_values_and_is_reused_without_parsing(monkeypatch):
    source, rules = load_data()
    custom = thaw(source)
    catalog = parse_catalog(custom)
    building = catalog.buildings["sho_farming_1_rice_paddies"]
    custom["buildings"][building.id]["facts"].clear()
    assert building.effects
    with pytest.raises(FrozenInstanceError):
        set_attribute(building, "level", 100)
    with pytest.raises(TypeError):
        set_item(catalog.buildings, building.id, building)

    def unexpected_parse(text):
        pytest.fail(f"Parsed an already interpreted source fact: {text}")

    monkeypatch.setattr(domain, "parse", unexpected_parse)
    scenario = Scenario("oda", (Province("jap_owari"),))
    first = Economy(scenario, catalog, rules)
    second = Economy(scenario, first.catalog, first.rules)
    assert first.catalog is second.catalog is catalog
    assert first.wealth("jap_owari", building) == second.wealth("jap_owari", building)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", 1),
        ("id", "other"),
        ("id", "sho_farming_unknown"),
        ("facts", "Provides food: 3"),
        ("facts", [3]),
        ("requires", [False]),
    ],
)
def test_bad_building_sources_fail_before_entering_economy(field, value):
    source, _ = load_data()
    raw = thaw(source["buildings"]["sho_farming_1_rice_paddies"])
    raw[field] = value
    with pytest.raises(ValueError):
        parse_building(raw)


def test_catalog_identity_and_missing_source_facts_are_validated():
    source, _ = load_data()
    raw = thaw(source)
    key = "sho_farming_1_rice_paddies"
    raw["buildings"][key]["id"] = "sho_farming_2_irrigation"
    with pytest.raises(ValueError, match="identifier"):
        parse_catalog(raw)
    raw["buildings"][key]["id"] = key
    del raw["buildings"][key]["facts"]
    with pytest.raises(ValueError, match="facts"):
        parse_catalog(raw)
