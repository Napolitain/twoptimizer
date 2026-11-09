"""Exact source facts and explicit eligibility reasons are stable API behavior."""

import pytest

from games.tw.shogun2.domain import parse_building
from games.tw.shogun2.effects import Effect, parse, unavailable_reason, unique_key
from games.tw.shogun2.records import Location, PublicRecord


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cost: 1200", Effect("construction_cost", 1200)),
        ("Provides food: 3", Effect("food", 3)),
        ("Consumes food: 2", Effect("food", -2)),
        ("+20 to wealth from farms in this province", Effect("wealth", 20, "farms")),
        ("+5% bonus to clan-wide tax rate", Effect("tax_percent", 5)),
        ("+4 happiness for the Buddhist population", Effect("religious_order", 4)),
        ("Increase to trade income (tariffs only) by +10%", Effect("tariff_percent", 10)),
    ],
)
def test_exact_source_effects_keep_integer_coefficients(text, expected):
    effect = parse(text)
    assert effect == expected
    assert effect is not None
    assert isinstance(effect.value, int)


def test_clan_facts_are_additive_and_optional():
    base: PublicRecord = {
        "id": "sho_farming_1_test",
        "name": "Test",
        "facts": ["+20 to wealth from farms in this province", "Unsupported military fact"],
    }
    assert parse_building(base).value("wealth", "farms") == 20
    assert parse_building(base).value("wealth", "commerce") == 0
    assert parse_building(base).value("wealth") == 20
    base["clan_facts"] = ["+5 to wealth from farms in this province"]
    assert parse_building(base).value("wealth", "farms") == 25


@pytest.mark.parametrize(
    ("key", "religion", "contact", "clan", "expected"),
    [
        ("sho_port_2_nanban_port", "buddhist", False, None, "nanban_contact_or_religion"),
        ("sho_port_2_nanban_port", "ikko", True, None, "nanban_contact_or_religion"),
        (
            "sho_port_2_nanban_quarter",
            "buddhist",
            True,
            None,
            "nanban_quarter_requires_christianity",
        ),
        ("sho_port_2_nanban_quarter", "christian", True, None, None),
        ("sho_region_specialty_gold_1", "buddhist", True, None, "different_province_specialty"),
        ("sho_christian_1_chapel", "buddhist", True, None, "different_state_religion"),
        ("sho_ikko_1_temple", "buddhist", True, None, "different_state_religion"),
        ("sho_christian_1_chapel", "christian", True, "otomo", None),
        ("sho_christian_2_church", "christian", True, "otomo", "different_clan_christian_branch"),
        ("sho_christian_2_hospital", "christian", True, "otomo", None),
        ("sho_christian_2_hospital", "christian", True, "oda", "different_clan_christian_branch"),
        (
            "sho_portuguese_1_land",
            "christian",
            True,
            None,
            "one_off_land_sale_not_recurring_tax_wealth",
        ),
    ],
)
def test_eligibility_reason_boundaries(key, religion, contact, clan, expected):
    province: Location = {"has_port": True, "specialty": None}
    assert (
        unavailable_reason(
            parse_building({"id": key, "name": key, "facts": []}),
            province,
            religion,
            nanban_contact=contact,
            clan=clan,
        )
        == expected
    )


def test_nanban_contact_defaults_to_available_and_chain_is_faction_unique():
    building: PublicRecord = {"id": "sho_port_2_nanban_port", "name": "Nanban", "facts": []}
    assert (
        unavailable_reason(
            parse_building(building), {"has_port": True, "specialty": None}, "buddhist"
        )
        is None
    )
    assert unique_key(building) == "nanban_chain"
    assert unique_key({"id": "sho_port_2_trading_port"}) is None
    assert unique_key({"id": "sho_christian_4_jesuit_college"}) is None
