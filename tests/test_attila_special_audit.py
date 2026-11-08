import json

from games.tw.attila.tools.audit_specials import DATA, audit


def test_special_inventory_is_current_and_preserves_unknown_availability():
    report = audit()
    assert report == json.loads((DATA / "special_building_audit.json").read_text())
    assert report["purpose"] == "audit_only_not_solver_input"
    assert report["summary"]["local_candidates"] == 34
    for building in report["buildings"].values():
        assert set(building["raw_availability_fields"].values()) == {None}


def test_special_inventory_separates_global_effects_from_capital_restrictions():
    palace = audit()["buildings"]["att_bld_roman_east_civic_governor_5_legendary"]
    assert palace["raw_availability_fields"]["only_in_capital"] is None
    assert palace["raw_availability_fields"]["faction_unique"] is None
    assert palace["modeled_site_rule"]["kind"] == "no_verified_special_site_rule"
    order = next(e for e in palace["effects"] if e["effect"] == "att_effect_public_order_politics")
    assert (order["raw_scope"], order["reach"], order["value"]) == (
        "faction_to_province_own",
        "faction",
        1,
    )


def test_incomplete_metadata_is_not_assumed_free_or_enabled():
    report = audit()
    dam = report["buildings"]["att_bld_eos_marib_dam"]
    assert dam["income_metadata"] is None
    assert dam["income_metadata_status"] == "missing_excluded_by_default"
    assert dam["modeled_site_rule"]["region"] == "att_reg_arabia_felix_zafar"
    sources = json.loads((DATA / "special_building_sources.json").read_text())
    wonders = sources["external_buildings"]
    assert report["summary"]["external_candidates_missing_locally"] == []
    assert set(report["summary"]["external_candidates_missing_income_metadata"]) == set(wonders)
    assert len(wonders) == 5
    for wonder in wonders.values():
        assert wonder["upkeep"] is None
        assert wonder["availability_status"] == "not_verified"
        assert sources["sources"][wonder["source"]]["sha256"]
