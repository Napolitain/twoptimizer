"""Replay small raw tables through joins and economic normalization offline."""

from xml.etree import ElementTree as ET

import pytest

from games.tw.three_kingdoms.catalog import building_effects
from games.tw.three_kingdoms.import_effects import EffectMappings, building_variants
from games.tw.three_kingdoms.import_reference import _factions, _requirements
from games.tw.three_kingdoms.source import SourceArchive


@pytest.fixture
def archive(tmp_path):
    source = SourceArchive(tmp_path, offline=True)

    def write(name, rows):
        root = ET.Element("dataroot")
        ET.SubElement(root, "edit_uuid").text = "fixture"
        for record in rows:
            row = ET.SubElement(root, name)
            for key, value in record.items():
                ET.SubElement(row, key).text = str(value)
        (source.cache / f"{name}.xml").write_bytes(ET.tostring(root))

    for name in (
        "effect_bonus_value_region_gdp_type_junctions",
        "effect_bonus_value_basic_junction",
        "effect_bonus_value_pooled_resource_factor_junctions",
    ):
        write(name, [])
    return source, write


def test_economic_junctions_preserve_hidden_local_and_neighbor_effects(archive):
    source, write = archive
    write(
        "effect_bonus_value_basic_junction",
        [
            {"effect": "visible_corruption", "bonus_value_id": "admin_cost_mod"},
            {"effect": "hidden_corruption", "bonus_value_id": "admin_cost_mod"},
            {
                "effect": "order",
                "bonus_value_id": "province_public_order_happiness_building_factor",
            },
            {"effect": "army", "bonus_value_id": "army_morale"},
        ],
    )
    write(
        "effect_bonus_value_pooled_resource_factor_junctions",
        [
            {
                "effect": "distribution",
                "bonus_value_id": "base_amount",
                "resource_factor": "3k_main_pooled_factor_junction_food_distribution",
            },
            {
                "effect": "farm_modifier",
                "bonus_value_id": "percentage_multiplier_mod",
                "resource_factor": "3k_main_pooled_factor_junction_food_local_farming",
            },
            {"effect": "supply", "bonus_value_id": "base_amount", "resource_factor": "supplies"},
        ],
    )
    mappings = EffectMappings(source)
    local = mappings.normalize("hidden_corruption", "province_to_province_own_unseen", "-15")[0]
    adjacent = mappings.normalize("visible_corruption", "building_to_province_own_adjacent", "-15")[
        0
    ]
    assert local["metric"] == adjacent["metric"] == "corruption_percent"
    assert local["scope"] == "province" and adjacent["scope"] == "adjacent_provinces"
    food = mappings.normalize("distribution", "region_to_region_own_unseen", "-34")[0]
    assert (food["metric"], food["category"], food["value"]) == ("food", "distribution", -34)
    assert mappings.normalize("army", "unknown", "10")[0]["metric"] == "unmodeled"
    assert len(source.records) == 3


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("building_to_province_enemy_adjacent", "enemy_adjacent_provinces"),
        ("region_to_region_own_factionwide_silk", "faction"),
        ("faction_to_region_own_unseen", "faction"),
        ("faction_to_province_own_unseen", "faction"),
        ("province_to_region_own", "province"),
        ("region_to_region_own_provincewide_unseen", "province"),
        ("building_to_building_own", "region"),
    ],
)
def test_scope_aliases_do_not_lose_ownership_or_extent(archive, raw, expected):
    source, _ = archive
    normalized = EffectMappings(source).normalize("unknown", raw, "1")[0]
    assert normalized["scope"] == expected
    assert normalized["raw_scope"] == raw


def test_building_campaign_variants_select_highest_matching_complete_group(archive):
    source, write = archive
    write(
        "building_effects_junction",
        [
            {
                "campaign_group": "base",
                "effect": "food",
                "effect_scope": "building_to_building_own",
                "value": -4,
            },
            {
                "campaign_group": "han",
                "effect": "food",
                "effect_scope": "building_to_building_own",
                "value": -6,
            },
            {
                "campaign_group": "later",
                "effect": "food",
                "effect_scope": "building_to_building_own",
                "value": -50,
            },
        ],
    )
    write(
        "campaign_group_members",
        [
            {"id": "a", "group": "base", "priority": 0},
            {"id": "b", "group": "han", "priority": 1},
            {"id": "c", "group": "later", "priority": 2},
        ],
    )
    write(
        "campaign_group_member_criteria_building_levels",
        [{"member": member, "building_level": "city"} for member in "abc"],
    )
    write("campaign_group_member_criteria_factions", [])
    write("campaign_group_member_criteria_subcultures", [{"member": "b", "subculture": "han"}])
    write("campaign_group_member_criteria_campaigns", [{"member": "c", "campaign": "later"}])
    variants = building_variants(source, EffectMappings(source))
    building = {"id": "city", "effect_variants": variants["city"]}
    faction = {"id": "cao", "subculture": "han"}
    assert [e["value"] for e in building_effects(building, faction)] == [-6]
    assert [e["value"] for e in building_effects(building, faction, "later")] == [-50]


def test_resource_requirement_operators_survive_the_join(archive):
    source, write = archive
    write(
        "faction_resources_requirement_set_to_resources_junctions",
        [
            {"set_id": "both", "faction_resource_id": "iron"},
            {"set_id": "both", "faction_resource_id": "artisans"},
            {"set_id": "either", "faction_resource_id": "silk"},
            {"set_id": "either", "faction_resource_id": "spice"},
        ],
    )
    write(
        "faction_resources_requirement_sets",
        [
            {"set_id": "both", "operator_key": "AND"},
            {"set_id": "either", "operator_key": "OR"},
        ],
    )
    write(
        "faction_resources_building_levels_requirements_junctions",
        [
            {"building_level_record": "forge", "set_id": "both"},
            {"building_level_record": "market", "set_id": "either"},
        ],
    )
    assert _requirements(source) == {
        "forge": {"operator": "AND", "resources": ["iron", "artisans"]},
        "market": {"operator": "OR", "resources": ["silk", "spice"]},
    }


def test_faction_chain_union_respects_campaign_and_subculture(archive):
    source, write = archive
    write(
        "building_chain_availability_sets",
        [
            {"id": "common", "building_chain": "farm"},
            {"id": "han", "building_chain": "palace"},
            {"id": "cao", "building_chain": "garrison"},
            {"id": "later", "building_chain": "inapplicable"},
        ],
    )
    base = {"campaign": "", "culture": "", "faction": "", "sub_culture": ""}
    write(
        "building_chain_availabilities",
        [
            {**base, "set_id": "common"},
            {**base, "set_id": "han", "sub_culture": "han"},
            {**base, "set_id": "cao", "faction": "3k_main_faction_cao_cao"},
            {**base, "set_id": "later", "campaign": "8p_start_pos"},
        ],
    )
    write("cultures_subcultures", [{"subculture": "han", "culture": "chinese"}])
    faction = {
        "key": "3k_main_faction_cao_cao",
        "category": "playable",
        "subculture": "han",
        "screen_adjective": "Cao Cao",
        "screen_name": "Wei",
    }
    write("factions", [faction, {**faction, "key": "3k_main_faction_cao_separatists"}])
    result = _factions(source)
    assert tuple(result) == ("3k_main_faction_cao_cao",)
    assert result["3k_main_faction_cao_cao"]["chains"] == ["farm", "garrison", "palace"]
