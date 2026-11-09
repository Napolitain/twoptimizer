"""Catalog boundary rejects malformed source shapes and owns parsed game records."""

from dataclasses import FrozenInstanceError, replace

import pytest

from games.tw.immutable import thaw
from games.tw.three_kingdoms.catalog import building_effects, load_data, selected_effects
from games.tw.three_kingdoms.model import Economy
from games.tw.three_kingdoms.parsing import parse_catalog
from games.tw.three_kingdoms.scenario import Commandery, Scenario
from tests.support.ownership import set_attribute, set_item


@pytest.fixture(scope="module")
def source():
    return load_data()


def test_domain_catalog_is_detached_immutable_and_reused_by_local_models(source):
    raw = thaw(source)
    parsed = parse_catalog(raw)
    city = parsed.buildings["3k_city_5"]
    raw["buildings"][city.id]["upkeep"] = 99999
    raw["buildings"][city.id]["effect_variants"][0]["effects"].clear()
    assert city.upkeep != 99999
    assert city.effect_variants[0].effects
    with pytest.raises(FrozenInstanceError):
        set_attribute(city, "upkeep", 1)
    with pytest.raises(TypeError):
        set_item(parsed.buildings, city.id, city)
    with pytest.raises(TypeError):
        set_item(parsed.rules.city_levels, 5, parsed.rules.city_levels[4])
    scenario = Scenario("3k_main_faction_cao_cao", (Commandery("3k_main_province_yingchuan"),))
    first = Economy(scenario, parsed)
    second = Economy(replace(scenario, all_reforms=True), first.data)
    assert first.data is second.data is parsed


def test_parsed_effect_variants_preserve_all_source_selections(source):
    catalog = parse_catalog(source)
    for faction in catalog.factions.values():
        for building in catalog.buildings.values():
            if building.chain not in faction.chains:
                continue
            raw = building_effects(source["buildings"][building.id], source["factions"][faction.id])
            chosen = selected_effects(building, faction)
            assert [(e.metric, e.value, e.category, e.scope) for e in chosen] == [
                (e["metric"], e["value"], e["category"], e["scope"]) for e in raw
            ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("level", True, "must be an integer"),
        ("upkeep", 1.5, "must be an integer"),
        ("name", 3, "must be text"),
        ("faction_unique", 1, "must be a boolean"),
        ("provided_resources", "tea", "must be a sequence"),
        ("provided_resources", [1], "must contain text"),
        ("id", "different", "Catalog key disagrees"),
        ("required_resources", [], "must be an object"),
        ("required_resources", {"operator": "XOR", "resources": []}, "Unsupported"),
        ("provided_resources", ["invented_resource"], "Unknown resource"),
    ],
)
def test_invalid_building_shapes_fail_at_boundary(source, field, value, message):
    raw = thaw(source)
    raw["buildings"]["3k_city_5"][field] = value
    with pytest.raises(ValueError, match=message):
        parse_catalog(raw)


def test_missing_required_field_and_unknown_commandery_fail_at_boundary(source):
    raw = thaw(source)
    del raw["buildings"]["3k_city_5"]["upkeep"]
    with pytest.raises(ValueError, match=r"Missing.*upkeep"):
        parse_catalog(raw)
    raw = thaw(source)
    next(iter(raw["regions"].values()))["commandery"] = "missing"
    with pytest.raises(ValueError, match="Unknown commandery"):
        parse_catalog(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("population_unit", 0),
        ("population_bands", []),
        (
            "population_bands",
            [{"minimum": 1, "maximum": 0, "public_order": 0, "peasantry_percent": 0}],
        ),
        ("city_levels", {"5": {"slots": -1}}),
    ],
)
def test_invalid_rule_domains_fail_before_compilation(source, field, value):
    raw = thaw(source)
    raw["rules"][field] = value
    with pytest.raises(ValueError):
        parse_catalog(raw)


def test_unknown_effect_scope_fails_at_boundary(source):
    raw = thaw(source)
    raw["buildings"]["3k_city_5"]["effect_variants"][0]["effects"][0]["scope"] = "world"
    with pytest.raises(ValueError, match=r"Unsupported.*scope"):
        parse_catalog(raw)


@pytest.mark.parametrize("change", ["extra", "missing_optional", "nested_metadata"])
def test_tied_variants_keep_complete_source_comparison_identity(source, change):
    raw = thaw(source)
    city = raw["buildings"]["3k_city_5"]
    first = city["effect_variants"][0]
    # Both groups apply to the same faction/campaign and have the same rank.
    first["factions"] = first["subcultures"] = first["campaigns"] = []
    duplicate = thaw(first)
    left, right = first["effects"][0], duplicate["effects"][0]
    if change == "extra":
        right["source_note"] = "Different source row"
    elif change == "missing_optional":
        left.pop("raw_scope", None)
        right["raw_scope"] = ""
    else:
        left["source_note"] = {"nested": [1, {"row": "a"}]}
        right["source_note"] = {"nested": [1, {"row": "b"}]}
    city["effect_variants"] = [first, duplicate]
    faction = raw["factions"]["3k_main_faction_cao_cao"]
    with pytest.raises(ValueError, match="Ambiguous"):
        building_effects(city, faction)
    parsed = parse_catalog(raw)
    with pytest.raises(ValueError, match="Ambiguous"):
        selected_effects(parsed.buildings[city["id"]], parsed.factions[faction["id"]])


def test_source_signature_ignores_mapping_order_but_keeps_raw_sequence_types(source):
    raw = thaw(source)
    city = raw["buildings"]["3k_city_5"]
    first = city["effect_variants"][0]
    first["factions"] = first["subcultures"] = first["campaigns"] = []
    first["effects"][0]["source_note"] = {"a": [1], "b": 2}
    duplicate = thaw(first)
    duplicate["effects"][0]["source_note"] = {"b": 2, "a": [1]}
    city["effect_variants"] = [first, duplicate]
    faction = raw["factions"]["3k_main_faction_cao_cao"]
    assert building_effects(city, faction)
    duplicate["effects"][0]["source_note"]["a"] = (1,)
    with pytest.raises(ValueError, match="Ambiguous"):
        building_effects(city, faction)
    # The Economy boundary has always normalized caller-owned sequences when freezing input.
    parsed = parse_catalog(raw)
    assert selected_effects(parsed.buildings[city["id"]], parsed.factions[faction["id"]])


@pytest.mark.parametrize("alias", ["01", "+1", " 1", "1.0", "-1"])
def test_city_level_keys_cannot_alias_an_existing_level(source, alias):
    raw = thaw(source)
    raw["rules"]["city_levels"][alias] = {"slots": 999}
    with pytest.raises(ValueError):
        parse_catalog(raw)
