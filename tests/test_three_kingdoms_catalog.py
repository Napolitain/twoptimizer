"""Economic data regressions for the pinned historical reference."""

import pytest

from games.tw.immutable import thaw
from games.tw.three_kingdoms import catalog
from games.tw.three_kingdoms.audit_reference import audit_reference
from games.tw.three_kingdoms.catalog import building_effects, load_data
from games.tw.three_kingdoms.import_effects import EffectMappings
from games.tw.three_kingdoms.source import PIN, SourceArchive


@pytest.fixture(scope="module")
def reference():
    return load_data()


def _economic(effects):
    return {
        (e["metric"], e["category"], e["scope"], e["value"])
        for e in effects
        if e["metric"] != "unmodeled"
    }


def test_reference_is_historical_and_immutable(reference):
    assert reference["source_revision"] == PIN
    assert "1.2.0" in reference["ruleset"]
    assert len(reference["buildings"]) == 424
    assert len(reference["factions"]) == 15
    assert len(reference["reforms"]) == 143
    with pytest.raises(TypeError):
        reference["buildings"]["3k_city_5"]["upkeep"] = 999
    assert reference["coverage"]["source_building_levels"] == 439
    assert reference["coverage"]["undated_honga_catalog_buildings"] == 583
    assert all(PIN in source["url"] for source in reference["sources"])


def test_city_replacement_group_does_not_double_count_food_or_slots(reference):
    city = reference["buildings"]["3k_city_5"]
    han = building_effects(city, reference["factions"]["3k_main_faction_cao_cao"])
    yellow = building_effects(city, reference["factions"]["3k_main_faction_yellow_turban_anding"])
    assert ("food", "distribution", "region", -6) in _economic(han)
    assert ("slots", "", "province", 4) in _economic(han)
    assert sum(e["value"] for e in han if e["metric"] == "food") == -6
    assert ("wealth", "peasantry", "region", 25) in _economic(han)
    assert not any(e["metric"] == "wealth" for e in yellow)


def test_recovered_mint_and_silk_effects_preserve_cross_province_scopes(reference):
    faction = reference["factions"]["3k_main_faction_cao_cao"]
    mint = _economic(
        building_effects(reference["buildings"]["3k_district_artisan_minting_5"], faction)
    )
    assert ("wealth", "industry", "region", 300) in mint
    assert ("corruption_percent", "", "province", -15) in mint
    assert ("corruption_percent", "", "adjacent_provinces", -15) in mint
    silk = _economic(building_effects(reference["buildings"]["3k_resource_water_silk_5"], faction))
    assert ("wealth", "silk", "region", 250) in silk
    assert ("wealth_percent", "silk", "faction", 65) in silk


def test_faction_eligibility_uses_explicit_availability_sets(reference):
    cao = reference["factions"]["3k_main_faction_cao_cao"]
    liu = reference["factions"]["3k_main_faction_liu_bei"]
    special = "3k_resource_wood_farms_grain_agricultural_garrison"
    assert special in cao["chains"] and special not in liu["chains"]
    # The common chain remains available as well as Cao Cao's extra chain.
    assert "3k_resource_wood_farms_grain" in cao["chains"]
    assert "3k_resource_wood_farms_grain" in liu["chains"]
    assert all(not key.startswith("ep_") for key in reference["buildings"])


def test_original_ruler_bonuses_come_from_careers(reference):
    ma = reference["factions"]["3k_main_faction_ma_teng"]
    yuan = reference["factions"]["3k_main_faction_yuan_shu"]
    assert "career_historical_ma_teng" in ma["leader_career"]
    assert ("wealth_percent", "silk", "faction", 100) in _economic(ma["leader_effects"])
    assert ("wealth_percent", "spice", "faction", 100) in _economic(ma["leader_effects"])
    assert ("wealth_percent", "industry", "faction", 25) in _economic(yuan["leader_effects"])
    assert ("wealth_percent", "commerce", "faction", 25) in _economic(yuan["leader_effects"])


def test_yellow_turban_trait_is_separate_from_original_ruler(reference):
    for faction in reference["factions"].values():
        if faction["subculture"] == "3k_main_subculture_yellow_turban":
            assert ("corruption_percent", "", "faction", -10) in _economic(
                faction["faction_effects"]
            )
            assert not any(
                effect["metric"] == "corruption_percent" for effect in faction["leader_effects"]
            )
            assert faction["faction_trait_corroboration"]["url"].startswith(
                "https://steamcommunity.com/"
            )


def test_mixed_reference_revisions_are_rejected(monkeypatch):
    monkeypatch.setattr(
        catalog,
        "read_catalog",
        lambda path: {
            "source_revision": "wrong",
            "source_commit": PIN,
        },
    )
    with pytest.raises(ValueError, match="different source revisions"):
        catalog.load_data()


def test_historical_audit_separates_recovery_from_latest_game_completeness():
    report = audit_reference()
    assert report["historical_static_reference_available"]
    assert not report["latest_game_complete"]
    assert not report["installed_build_validated"]
    assert len(report["formerly_unpublished_building_effects_recovered"]) == 139
    assert not report["modeled_effects_with_unresolved_scope"]
    assert report["resolved_faction_building_pairs"] == 3690
    assert all(PIN in row["url"] for row in report["source_files"])


def test_reform_scopes_and_food_factors_are_not_silently_dropped(reference):
    effects = [
        e
        for reform in reference["reforms"].values()
        for e in reform["effects"]
        if e["metric"] != "unmodeled"
    ]
    assert all(e["scope"] == "faction" for e in effects)
    food = [e for e in effects if e["metric"] == "food_percent"]
    assert {e["category"] for e in food} == {"farming", "fishing"}


def test_ambiguous_or_missing_effect_variants_fail_closed(reference):
    original = reference["buildings"]["3k_district_artisan_minting_5"]
    faction = reference["factions"]["3k_main_faction_cao_cao"]
    missing = thaw(original)
    missing["effect_variants"] = []
    with pytest.raises(ValueError, match="No source effect group"):
        building_effects(missing, faction)
    ambiguous = thaw(original)
    duplicate = thaw(ambiguous["effect_variants"][0])
    duplicate["effects"][0]["value"] += 10
    ambiguous["effect_variants"].append(duplicate)
    with pytest.raises(ValueError, match="Ambiguous source effect groups"):
        building_effects(ambiguous, faction)


def test_normalizer_uses_junctions_not_effect_id_spelling(tmp_path, monkeypatch):
    archive = SourceArchive(tmp_path, offline=True)
    tables = {
        "effect_bonus_value_region_gdp_type_junctions": [
            {
                "effect": "custom_trait",
                "bonus_value_id": "region_gdp_mod",
                "region_gdp_type": "silk",
            },
            {
                "effect": "custom_trait",
                "bonus_value_id": "region_gdp_mod",
                "region_gdp_type": "spice",
            },
        ],
        "effect_bonus_value_basic_junction": [],
        "effect_bonus_value_pooled_resource_factor_junctions": [
            {
                "effect": "farm_bonus",
                "bonus_value_id": "percentage_multiplier_mod",
                "resource_factor": "3k_main_pooled_factor_junction_food_local_farming",
            },
        ],
    }
    monkeypatch.setattr(archive, "table", lambda name: tables[name])
    mappings = EffectMappings(archive)
    result = mappings.normalize("custom_trait", "faction_to_region_own_unseen", "12.5")
    assert _economic(result) == {
        ("wealth_percent", "silk", "faction", 12.5),
        ("wealth_percent", "spice", "faction", 12.5),
    }
    assert _economic(mappings.normalize("farm_bonus", "province_to_region_own", "20")) == {
        ("food_percent", "farming", "province", 20)
    }
    unknown = mappings.normalize("unknown_food_bonus", "strange_scope", "50")
    assert unknown[0]["metric"] == "unmodeled"
    assert unknown[0]["scope"] == "unmodeled"
