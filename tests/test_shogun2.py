"""Original economic formulas and legality checks versus exact model solving."""

import copy
import itertools
from dataclasses import replace

import pytest

from games.tw.shogun2.effects import parse, unavailable_reason, unique_key
from games.tw.shogun2.import_rules import province_records
from games.tw.shogun2.model import Economy, Province, Scenario, load_data


@pytest.fixture
def data():
    return load_data()


def scenario(clan="oda", *ids):
    return Scenario(
        clan,
        tuple(Province(key) for key in ids or ("jap_sado", "jap_settsu", "jap_owari")),
    )


def basic_layout(economy):
    layout = {}
    for key, (_, province) in economy.provinces.items():
        choices = [
            "sho_castle_1_fort",
            "sho_farming_4_consolidation",
            "sho_infrastructure_0_trails",
        ]
        if province["has_port"]:
            choices.append("sho_port_0_coastal_village")
        if province["specialty"]:
            choices.append(
                next(k for k in economy.candidates[key] if k.startswith("sho_region_specialty_"))
            )
        layout[key] = choices
    return layout


def replace_family(layout, province, prefix, new):
    layout[province] = [key for key in layout[province] if not key.startswith(prefix)] + [new]


def test_all_provinces_have_soil_port_and_specialty(data):
    catalog, rules = data
    assert len(rules["provinces"]) == 65
    assert rules["provinces"].keys() == catalog["regions"].keys()
    assert rules["provinces"]["jap_sado"]["specialty"] == "gold_mining"
    assert rules["provinces"]["jap_owari"]["farm_multiplier"] == 3
    assert rules["provinces"]["jap_settsu"]["specialty"] == "intellectual_centre"
    assert all(isinstance(p["has_port"], bool) for p in rules["provinces"].values())
    assert len(rules["sources"]) == 4
    assert all(len(source["sha256"]) == 64 for source in rules["sources"])


def test_province_import_rejects_unknown_identity_or_soil():
    names = {"jap_kozuke": {"id": "jap_kozuke", "name": "Kozuke"}}
    html = (
        '<li id="Kozuka" class="horses playble"><h3>Kozuka '
        "Province</h3><p>Clan: Hojo</p><p>Port: No</p><p>Fertility: "
        "Average</p><p>Speciality/Resource: Horses</p></li>"
    )
    record = province_records(html, names)["jap_kozuke"]
    assert record["farm_multiplier"] == 1.5 and not record["has_port"]
    with pytest.raises(ValueError, match="Unmatched province"):
        province_records(html.replace("Kozuka Province", "Invented Province"), names)
    with pytest.raises(ValueError, match="Incomplete province"):
        province_records(html.replace("Average", "Undefined"), names)


def test_tax_points_and_farm_bonus_against_hand_calculation(data):
    catalog, rules = data
    economy = Economy(
        Scenario("chosokabe", (Province("jap_owari", town_wealth=1000, administration=0.8),)),
        catalog,
        rules,
    )
    layout = basic_layout(economy)
    layout["jap_owari"].append("sho_stealth_4_mizu_shobai")
    report = economy.evaluate(layout)
    province = report["provinces"]["jap_owari"]
    # 950 * 3 * (1 + .10 + .02), and 30 + 8 + 25 tax points.
    assert province["farm_wealth"] == 3192
    assert province["effective_tax_percent"] == 63
    assert report["domestic_tax_income"] == pytest.approx((1000 + 3192) * 0.63 * 0.8)
    assert report["farm_bonus_percent"] == 12


def test_food_is_shared_and_arts_food_counted_once(data):
    economy = Economy(scenario(), *data)
    layout = basic_layout(economy)
    # Sado needs imports: farm4 - fortress3 - market2 = -1.
    replace_family(layout, "jap_sado", "sho_castle_", "sho_castle_3_fortress")
    layout["jap_sado"].append("sho_crafts_3_merchant_guild")
    report = economy.evaluate(layout)
    assert report["provinces"]["jap_sado"]["local_food_balance"] == -1
    assert report["faction_arts_food"] == 1
    assert report["food_surplus"] == 6  # -1 + 3 + 3, plus one faction food.
    assert all(
        p["growth_components"]["shared_food_surplus"] == 6 for p in report["provinces"].values()
    )
    for key in layout:
        replace_family(layout, key, "sho_farming_", "sho_farming_1_rice_paddies")
    with pytest.raises(ValueError, match="food deficit"):
        economy.evaluate(layout)


def test_slots_uniques_and_local_order_enforced(data):
    economy = Economy(scenario(), *data)
    layout = basic_layout(economy)
    layout["jap_owari"] += ["sho_crafts_1_market", "sho_stealth_3_criminal_syndicate"]
    with pytest.raises(ValueError, match="too few town slots"):
        economy.evaluate(layout)
    replace_family(layout, "jap_owari", "sho_castle_", "sho_castle_2_stronghold")
    economy.evaluate(layout)
    for key in ("jap_sado", "jap_settsu"):
        layout[key].append("sho_crafts_4_kanabukama")
    with pytest.raises(ValueError, match="Unique building duplicated"):
        economy.evaluate(layout)
    strict = replace(scenario(), provinces=(Province("jap_owari", minimum_order=100),))
    assert Economy(strict, *data).optimize()["solver"]["status"] == "INFEASIBLE"


def test_religion_site_port_and_nanban_restrictions(data):
    catalog, rules = data
    province = {**rules["provinces"]["jap_owari"], "has_port": False}
    assert (
        unavailable_reason(catalog["buildings"]["sho_port_2_trading_port"], province, "buddhist")
        == "no_port_location"
    )
    economy = Economy(scenario("otomo"), *data)
    assert "sho_buddhist_4_legendary_temple" not in economy.candidates["jap_sado"]
    assert "sho_christian_4_cathedral" not in economy.candidates["jap_sado"]
    assert "sho_christian_4_jesuit_college" in economy.candidates["jap_sado"]
    assert unique_key(catalog["buildings"]["sho_christian_4_jesuit_college"]) is None
    converted = Economy(replace(scenario(), religion="christian"), *data)
    assert "sho_christian_4_cathedral" in converted.candidates["jap_sado"]
    assert "sho_christian_4_jesuit_college" not in converted.candidates["jap_sado"]
    assert "sho_region_specialty_gold_mining_3_mining_complex" in economy.candidates["jap_sado"]
    assert (
        "sho_region_specialty_gold_mining_3_mining_complex" not in economy.candidates["jap_owari"]
    )
    assert not any(
        "nanban" in key or "portuguese" in key
        for choices in economy.candidates.values()
        for key in choices
    )
    contact = Economy(replace(scenario(), nanban_contact=True), *data)
    assert "sho_port_3_nanban_trade_port" in contact.candidates["jap_sado"]
    assert "sho_port_4_nanban_quarter" not in contact.candidates["jap_sado"]
    christian = Economy(replace(scenario("otomo"), nanban_contact=True), *data)
    assert "sho_port_4_nanban_quarter" in christian.candidates["jap_sado"]
    ikko = Economy(replace(scenario("ikko_ikki"), nanban_contact=True), *data)
    assert not any("nanban" in key or "buddhist" in key for key in ikko.candidates["jap_sado"])


def test_unresearched_arts_do_not_unlock_advanced_buildings(data):
    economy = Economy(replace(scenario(), all_arts=False), *data)
    assert economy.arts["food"] == 0
    assert "sho_crafts_4_kanabukama" not in economy.candidates["jap_sado"]
    assert "sho_castle_1_fort" in economy.candidates["jap_sado"]
    assert "sho_farming_1_rice_paddies" in economy.candidates["jap_sado"]


@pytest.mark.parametrize("algorithm", ["cp-sat", "cbc", "scip"])
def test_exact_solvers_match_exhaustive_original_formulas(data, algorithm):
    catalog, rules = copy.deepcopy(data)
    ids = [
        "sho_castle_1_fort",
        "sho_castle_2_stronghold",
        "sho_farming_1_rice_paddies",
        "sho_farming_4_consolidation",
        "sho_crafts_1_market",
        "sho_crafts_4_kanabukama",
        "sho_stealth_3_criminal_syndicate",
        "sho_stealth_4_mizu_shobai",
        "sho_buddhist_4_legendary_temple",
    ]
    catalog["buildings"] = {key: catalog["buildings"][key] for key in ids}
    rules["provinces"]["jap_owari"].update(has_port=False, specialty=None)
    economy = Economy(
        Scenario("chosokabe", (Province("jap_owari", town_wealth=1234, administration=0.8),)),
        catalog,
        rules,
    )
    best = 0
    count = 0
    for castle, farm, market, stealth, temple in itertools.product(
        ids[:2], ids[2:4], [None, *ids[4:6]], [None, *ids[6:8]], [None, ids[8]]
    ):
        layout = {"jap_owari": [key for key in (castle, farm, market, stealth, temple) if key]}
        try:
            report = economy.evaluate(layout)
        except ValueError:
            continue
        count += 1
        best = max(best, report["domestic_tax_income"])
    assert count > 10
    result = economy.optimize(algorithm)
    assert result["solver"]["status"] == "OPTIMAL"
    assert result["domestic_tax_income"] == pytest.approx(best)
    assert result["solver"]["bound"] == pytest.approx(best)


@pytest.mark.parametrize(
    "clan,expected",
    [
        (
            "chosokabe",
            (1064 + 4400) * 0.88 + (1596 + 1350) * 0.48 + (3192 + 1350) * 0.38,
        ),
        ("oda", (969 + 4400) * 0.88 + (1453.5 + 1350) * 0.48 + (2907 + 1350) * 0.38),
        ("otomo", (969 + 4400) * 0.63 + (1453.5 + 1350) * 0.48 + (2907 + 1350) * 0.38),
        (
            "ikko_ikki",
            (969 + 4400) * 0.63 + (1453.5 + 1350) * 0.48 + (2907 + 1350) * 0.38,
        ),
    ],
)
def test_full_three_province_solution_is_proved_and_re_evaluated(data, clan, expected):
    report = Economy(scenario(clan), *data).optimize()
    assert report["solver"]["status"] == "OPTIMAL"
    assert report["domestic_tax_income"] == pytest.approx(expected)
    assert report["food_surplus"] >= 0


def test_monetary_food_and_order_facts_are_classified(data):
    catalog, _ = data
    for section in ("buildings", "technologies"):
        for record in catalog[section].values():
            for text in record["facts"] + record.get("clan_facts", []):
                if any(
                    term in text
                    for term in (
                        "wealth",
                        "food:",
                        "tax rate",
                        "happiness",
                        "repression",
                        "town growth",
                        "economic growth",
                        "tariffs only",
                    )
                ):
                    assert parse(text) is not None or record["id"] == "sho_portuguese_land_sold", (
                        record["id"],
                        text,
                    )


@pytest.mark.parametrize(
    "province",
    [
        Province("jap_sado", town_wealth=-1),
        Province("jap_sado", administration=2),
        Province("jap_sado", farm_multiplier=4),
        Province("jap_sado", town_wealth=float("nan")),
    ],
)
def test_invalid_scenario_numbers_fail(province, data):
    with pytest.raises((ValueError, OverflowError)):
        Economy(Scenario("oda", (province,)), *data)
