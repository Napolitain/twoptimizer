"""Exact optimization versus exhaustive layouts and hand-calculated economics."""

import copy
import itertools
from dataclasses import replace

import pytest

from games.tw.rome2.catalog import load_data
from games.tw.rome2.effects import CATEGORIES, fact_effect, raw_effect
from games.tw.rome2.import_data import entity, named_regions
from games.tw.rome2.model import Economy
from games.tw.rome2.scenario import Scenario, Site
from tests.support.rome2 import effect


def tiny_scenario(**kwargs):
    return Scenario(
        "rom_rome",
        (Site("capital", major=True, slots=1), Site("town", slots=1)),
        external_food=4,
        minimum_order=-10,
        **kwargs,
    )


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip", "scip-nonlinear", "portfolio"])
def test_all_exact_solvers_match_exhaustive_original_economics(tiny, algorithm):
    economy = Economy(tiny_scenario(), tiny)
    best = 0
    for first, second, party in itertools.product(
        [None, "rome_religious_alpha_4", "rome_religious_beta_4"],
        [None, "rome_religious_alpha_4", "rome_religious_beta_4"],
        economy.parties,
    ):
        layout = {
            "capital": ["rome_city_4"] + ([first] if first else []),
            "town": ["rome_town_4"] + ([second] if second else []),
        }
        best = max(best, economy.evaluate(layout, party)["domestic_tax_income"])
    report = economy.optimize(algorithm, seconds=5)
    assert report["solver"]["status"] == "OPTIMAL"
    assert report["domestic_tax_income"] == pytest.approx(best)
    assert report["solver"]["bound"] == pytest.approx(best)


def test_hand_calculated_category_modifiers_tax_and_corruption(tiny):
    scenario = replace(tiny_scenario(party=0), corruption_points=5)
    economy = Economy(scenario, tiny)
    report = economy.evaluate(
        {"capital": ["rome_city_4", "rome_religious_alpha_4"], "town": ["rome_town_4"]},
        0,
    )
    # All-source +10 and industry +20 both apply to 150 province wealth.
    assert report["modified_wealth"] == 150 * 1.3
    assert report["domestic_tax_income"] == pytest.approx(195 * 1.05)
    assert report["food_surplus"] == 3
    assert report["tax_modifier_percent_net"] == 5


def test_minor_settlement_bonus_does_not_apply_to_capital(tiny):
    tiny["factions"]["rom_rome"]["traits"]["parties"][0]["facts"] = [
        "Village Confederation: +20% wealth from minor settlements"
    ]
    economy = Economy(tiny_scenario(party=0), tiny)
    report = economy.evaluate({"capital": ["rome_city_4"], "town": ["rome_town_4"]}, 0)
    assert report["modified_wealth"] == 150 * 1.1 + 50 * 0.2
    for algorithm in ("cp-sat", "cbc", "scip"):
        result = Economy(
            replace(
                tiny_scenario(party=0),
                sites=(Site("capital", major=True, slots=0), Site("town", slots=0)),
            ),
            tiny,
        ).optimize(algorithm)
        assert result["domestic_tax_income"] == report["domestic_tax_income"]


def test_food_recipient_scopes_count_regions_and_exclude_unowned_neighbors(tiny):
    core = tiny["buildings"]["rome_city_4"]
    core["effects"] += [
        effect(
            "rom_building_food_farming_grain_local_province",
            4,
            "regions_in_this_province",
        ),
        effect(
            "rom_building_food_farming_grain",
            40,
            "in_all_your_regions_in_adjacent_provinces",
        ),
    ]
    economy = Economy(replace(tiny_scenario(party=0), external_food=0), tiny)
    result = economy.evaluate({"capital": ["rome_city_4"], "town": ["rome_town_4"]}, 0)
    assert result["food_surplus"] == 8
    assert economy.optimize()["food_surplus"] >= 4


def test_rome_squalor_is_provincial_order_not_attila_sanitation(tiny):
    scenario = replace(tiny_scenario(party=0), minimum_order=0)
    economy = Economy(scenario, tiny)
    bad = {"capital": ["rome_city_4", "rome_religious_beta_4"], "town": ["rome_town_4"]}
    with pytest.raises(ValueError, match="public order"):
        economy.evaluate(bad, 0)
    bad["town"].append("rome_religious_alpha_4")
    assert economy.evaluate(bad, 0)["public_order"] == 0
    assert raw_effect("rom_building_public_order_happiness_sanitation", 3).kind == "order"


def test_political_profiles_are_not_stacked_and_dominance_is_safe(tiny):
    economy = Economy(tiny_scenario(), tiny)
    assert economy.pruned_parties == [2]
    assert set(economy.parties) == {0, 1}
    report = economy.optimize()
    assert report["party_index"] in (0, 1)
    assert (
        report["party_facts"]
        == tiny["factions"]["rom_rome"]["traits"]["parties"][report["party_index"]]["facts"]
    )


def test_duplicate_branch_occupancy_is_rejected(tiny):
    alternative = copy.deepcopy(tiny["buildings"]["rome_religious_alpha_4"])
    alternative.update(id="rome_religious_alpha_3", level=3)
    tiny["buildings"][alternative["id"]] = alternative
    economy = Economy(
        replace(
            tiny_scenario(party=0),
            sites=(Site("capital", major=True, slots=2), Site("town", slots=0)),
        ),
        tiny,
    )
    with pytest.raises(ValueError, match="Repeated branch"):
        economy.evaluate(
            {
                "capital": [
                    "rome_city_4",
                    "rome_religious_alpha_3",
                    "rome_religious_alpha_4",
                ],
                "town": ["rome_town_4"],
            },
            0,
        )


def test_imported_geography_and_faction_specific_temples():
    data = load_data()
    assert len(data["regions"]) == 173
    assert len(data["provinces"]) == 57
    assert len(data["factions"]) == 36
    assert not data["regions"]["rom_italia_latium"]["has_port"]
    assert data["regions"]["rom_italia_samnium"]["has_port"]
    for province in data["provinces"].values():
        assert sum(data["regions"][r]["major"] for r in province) == 1
    e = Economy(
        Scenario(
            "rom_carthage",
            (Site("capital", major=True), Site("town", resource="grain", port=True)),
        ),
        data,
    )
    assert "greek_religious_egypt_isis_4" not in e.candidates["town"]
    assert "greek_religious_punic_baal_hammon_4" in e.candidates["town"]
    assert "greek_grain_4" in e.candidates["town"]
    assert not any("3c_" in key for choices in e.candidates.values() for key in choices)
    assert not any("port" in key for key in e.candidates["capital"])


def test_money_facts_and_raw_effects_are_never_silently_lost():
    data = load_data()
    for building in data["buildings"].values():
        for row in building["effects"]:
            if any(term in row["id"] for term in ("gdp", "food", "tax_level", "public_order")):
                assert raw_effect(row["id"], row["value"]) is not None, row
    for faction in data["factions"].values():
        facts = list(faction["traits"]["culture_facts"]) + [
            t for p in faction["traits"]["parties"] if p["playable"] for t in p["facts"]
        ]
        for text in facts:
            if "wealth from" in text or "% tax rate" in text:
                assert fact_effect(text) is not None, text
    _assert_technology_money_facts(data)
    assert (
        raw_effect("rom_province_initiative_non_barbarian_taxes_mod_taxrate", 6).kind
        == "edict_conditional"
    )
    assert raw_effect("rom_building_slave_gpd_mod", 25).kind == "slaves_conditional"
    assert fact_effect("+20% wealth from all industrial buildings").targets == CATEGORIES[4:6]


def _assert_technology_money_facts(data):
    for tree in data["technologies"].values():
        for technology in tree.values():
            for text in technology["facts"]:
                if any(t in text for t in ("wealth from", "tax rate", "public order")):
                    assert fact_effect(text) is not None, text


def test_changed_or_unsafe_source_structure_fails():
    with pytest.raises(ValueError):
        entity(
            "https://example.com/unexpected",
            "building",
            "https://r2encv2.totalwar.com/",
        )
    with pytest.raises(ValueError, match="payload changed"):
        named_regions("<script>malicious()</script>")
    assert (
        named_regions(
            'var settlement_info={"rom_test":"<p>Settlement Name: '
            "Town</p><p>Belongs to Province: Province</p><p>Provincial Capital: "
            'Town</p>"};'
        )["rom_test"]["name"]
        == "Town"
    )


def test_invalid_scenarios_and_infeasibility(tiny):
    with pytest.raises(ValueError):
        Economy(Scenario("rom_rome", (Site("town"),)), tiny)
    with pytest.raises(ValueError):
        Economy(replace(tiny_scenario(), corruption_points=101), tiny)
    with pytest.raises(ValueError):
        Economy(
            replace(
                tiny_scenario(),
                sites=(Site("capital", major=True), Site("town", resource="unknown")),
            ),
            tiny,
        )
    impossible = replace(tiny_scenario(), external_food=-100)
    assert Economy(impossible, tiny).optimize()["solver"]["status"] == "INFEASIBLE"


def test_reuse_requires_identical_compiled_model_and_rechecks_economics(tiny):
    scenario = tiny_scenario()
    reference = Economy(scenario, tiny).optimize()
    reused = Economy(scenario, tiny).reuse_optimum(reference)
    assert reused["domestic_tax_income"] == reference["domestic_tax_income"]
    assert reused["solver"]["proof_reused_from"] == "rom_rome"
    with pytest.raises(ValueError, match="compiled model"):
        Economy(replace(scenario, tax_points=10), tiny).reuse_optimum(reference)


def test_food_reserves_is_food_and_edicts_remain_conditional(tiny):
    assert raw_effect("rom_building_food_reserves", 9).kind == "food"
    assert fact_effect("Bread and Games Edict: +10 public order") is None
    tiny["buildings"]["rome_city_4"]["effects"].append(effect("rom_building_food_reserves", 9))
    economy = Economy(replace(tiny_scenario(party=0), external_food=0), tiny)
    assert (
        economy.evaluate({"capital": ["rome_city_4"], "town": ["rome_town_4"]}, 0)["food_surplus"]
        == 9
    )


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip", "scip-nonlinear", "portfolio"])
def test_maintenance_is_deducted_once_after_tax(tiny, algorithm):
    tiny["buildings"]["rome_city_4"]["effects"].append(
        effect("dk_building_gdp_maintenance", -20, "this_faction")
    )
    report = Economy(tiny_scenario(party=0), tiny).optimize(algorithm, seconds=5)
    assert report["solver"]["status"] == "OPTIMAL"
    assert report["domestic_net_income"] == pytest.approx(report["domestic_tax_income"] - 20)
    assert report["solver"]["objective"] == pytest.approx(report["domestic_net_income"])


def test_validated_warm_start_and_corruption_floor(tiny):
    tiny["factions"]["rom_rome"]["traits"]["culture_facts"] = ["-20% corruption in your provinces"]
    scenario = replace(tiny_scenario(party=0), corruption_points=5)
    first = Economy(scenario, tiny).optimize()
    assert first["effective_corruption_points"] == 0
    second = Economy(scenario, tiny).optimize("scip-nonlinear", incumbent=first)
    assert second["domestic_net_income"] == first["domestic_net_income"]
    bad = copy.deepcopy(first)
    bad["domestic_net_income"] += 10
    with pytest.raises(ValueError, match="Warm start"):
        Economy(scenario, tiny).optimize("scip-nonlinear", incumbent=bad)


def test_real_provinces_join_resources_and_scoped_modifiers():
    from games.tw.rome2.world import province_scenario

    italy = province_scenario("Italia", "rom_rome")
    assert len(italy.sites) == 4
    assert {s.resource for s in italy.sites} == {None, "wine", "olive"}
    assert sum(s.port for s in italy.sites) == 2
    assert {r.name for r in italy.modifiers} == {"Roma", "Mount Vesuvius"}
    africa = province_scenario("Africa", "rom_saba")
    assert len(africa.sites) == 4 and sum(s.port for s in africa.sites) == 4
    economy = Economy(africa)
    assert not any("marib_dam" in key for options in economy.candidates.values() for key in options)
    assert not province_scenario("Italia", "rom_rome", world_bonuses=False).modifiers


def test_missing_public_research_is_explicitly_blocked():
    from games.tw.rome2.world import province_scenario

    with pytest.raises(ValueError, match="research tree is incomplete"):
        Economy(province_scenario("Italia", "rom_rome", all_technologies=True))
    # The legacy profile remains an explicit choice, never a silent fallback.
    Economy(
        province_scenario(
            "Italia", "rom_rome", all_technologies=True, technology_profile="archived"
        )
    )


def test_named_provinces_support_all_factions_and_short_resource_chains():
    from games.tw.rome2.world import province_scenario

    data = load_data()
    for province in ("Italia", "Africa", "Aegyptus", "Arabia Felix"):
        for faction in data["factions"]:
            economy = Economy(province_scenario(province, faction), data)
            if province == "Aegyptus" and faction == "rom_ardiaei":
                iron = "rom_aegyptos_ta_shemau"
                primaries = [
                    b
                    for key, b in economy.candidates[iron].items()
                    if economy.roles[(iron, key)] == "primary"
                ]
                assert primaries and {b["level"] for b in primaries} == {3}


def test_dlc_temples_missing_from_public_index_are_recovered():
    from games.tw.rome2.world import province_scenario

    economy = Economy(province_scenario("Italia", "rom_kush"))
    assert "dk_kush_religious_amani_4" in economy.candidates["rom_italia_latium"]
    assert any(
        row["id"] == "rom_building_gdp_mod_all"
        for row in economy.candidates["rom_italia_latium"]["dk_kush_religious_amani_4"]["effects"]
    )
    saba = Economy(province_scenario("Arabia Felix", "rom_saba"))
    assert "dk_saba_marib_dam_3" in saba.candidates["rom_arabia_felix_saba"]
