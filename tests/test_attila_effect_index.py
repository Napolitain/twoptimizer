"""Recipient indexing retains scoped behavior and per-model snapshot ownership."""

import pytest

from games.tw.attila.economy import Economy
from games.tw.region import Region
from tests.support.attila import building, province


@pytest.mark.parametrize(
    "scope",
    [
        "building_to_building_own",
        "building_to_region_own",
        "province_to_region_own",
        "faction_to_region_own",
        "province_to_regions_own_in_adjacent_province",
        "force_to_force_own",
        "province_to_province_own_adjacent_food",
    ],
)
def test_index_recipients_match_direct_scope_evaluation(context, scope):
    regions = [Region(str(i), context=context) for i in range(4)]
    source = building(regions[0], "bonus", ("economy_gdp_mod_industry", scope, 25))
    provinces = [
        province("home", *regions[:2]),
        province("next", regions[2]),
        province("far", regions[3]),
    ]
    economy = Economy(provinces, adjacency={"home": ["next", "next"]})
    record = economy.effect_index.by_kind["wealth_percent"][0]
    indexed = set(economy.effect_index.recipients(record))
    expected = {r.name for r in regions if economy.applies(source, r, record.scope, record.effect)}
    assert indexed == expected
    for region in regions:
        assert economy.field(region, "wealth_percent", "industry") == (
            {(source.get_name(),): 25} if region.name in expected else {}
        )


def test_fresh_economy_reads_mutations_without_changing_existing_snapshot(context):
    region = Region("local", context=context)
    factory = building(region, "factory", ("economy_gdp_industry", "building_to_building_own", 100))
    provinces = [province("home", region)]
    first = Economy(provinces)
    factory.raw_effects["att_effect_economy_gdp_industry", "building_to_building_own"] = 200
    second = Economy(provinces)
    assert first.evaluate(first.wealth(region), {factory.get_name()}) == 100
    assert second.evaluate(second.wealth(region), {factory.get_name()}) == 200
    assert first.effect_index is not second.effect_index


@pytest.mark.parametrize("supplied", [False, True])
def test_conditional_fertility_recipients_are_explicit_and_deduplicated(context, supplied):
    regions = [Region(str(i), context=context) for i in range(2)]
    effect = "att_effect_food_production_fertility_neighbouring"
    source = building(
        regions[0],
        "fields",
        (effect.removeprefix("att_effect_"), "region_to_province_own_factionwide", 1),
    )
    scenario = {"conditional_targets": {effect: {"home": ["next", "next"]}}} if supplied else {}
    economy = Economy(
        [province("home", regions[0]), province("next", regions[1])], scenario=scenario
    )
    record = economy.effect_index.by_kind["conditional_fertility_food"][0]
    assert economy.effect_index.recipients(record) == (("1",) if supplied else ())
    assert economy.field(regions[1], "conditional_fertility_food") == (
        {(source.get_name(),): 1} if supplied else {}
    )


@pytest.mark.parametrize("mapping", [{}, {"home": ["next"]}, {"next": ["home"]}])
def test_conditional_public_order_uses_only_the_producers_declared_recipients(context, mapping):
    regions = [Region(str(i), context=context) for i in range(2)]
    source = building(
        regions[0],
        "order",
        ("public_order_base_neighbouring", "province_to_province_own_adjacent_food", 3),
    )
    economy = Economy(
        [province("home", regions[0]), province("next", regions[1])],
        scenario={"conditional_targets": {"att_effect_public_order_base_neighbouring": mapping}},
    )
    assert economy.field(regions[0], "public_order") == {}
    assert economy.field(regions[1], "public_order") == (
        {(source.get_name(),): 3} if "home" in mapping else {}
    )


@pytest.mark.parametrize("adjacency", [{}, {"next": ["home"]}])
def test_absent_outgoing_adjacency_has_no_recipient(context, adjacency):
    regions = [Region(str(i), context=context) for i in range(2)]
    building(
        regions[0],
        "market",
        ("economy_gdp_mod_industry", "province_to_regions_own_in_adjacent_province", 25),
    )
    economy = Economy(
        [province("home", regions[0]), province("next", regions[1])], adjacency=adjacency
    )
    assert all(economy.field(region, "wealth_percent", "industry") == {} for region in regions)
