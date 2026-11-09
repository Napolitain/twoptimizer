"""Source-table support bonuses require explicit current political conditions."""

import pytest

from games.hoi4.data_pipeline.modifier_resolution import (
    build_modifier_catalog,
    resolve_support_profile,
)
from games.hoi4.data_pipeline.syntax import parse_script
from games.hoi4.planning.support import support_effects


def evaluate(stability=0.5, war_support=0.5, **overrides):
    inputs: dict = {
        "stability": stability,
        "war_support": war_support,
        "at_war": False,
        "stability_good": {"industrial_capacity_factory": 0.2, "consumer_goods_factor": -0.2},
        "stability_bad": {"industrial_capacity_factory": -0.5},
        "war_support_good": {"mobilization_speed": 0.3},
        "war_support_bad": {"mobilization_speed": -0.5},
        "war_stability_penalty_at_zero_support": -0.3,
    }
    inputs.update(overrides)
    return support_effects(**inputs)


@pytest.mark.parametrize(
    "stability, output, goods",
    [
        (0, -0.5, None),
        (0.25, -0.25, None),
        (0.5, 0, 0),
        (0.75, 0.1, -0.1),
        (1, 0.2, -0.2),
    ],
)
def test_stability_uses_both_endpoints_and_preserves_consumer_factor(stability, output, goods):
    result = evaluate(stability)
    assert dict(result.stability_modifiers)["industrial_capacity_factory"] == pytest.approx(output)
    assert dict(result.stability_modifiers).get("consumer_goods_factor") == goods


def test_stability_discards_subpercent_part_without_binary_float_boundary_loss():
    assert evaluate(0.816).stability_used == 0.81
    assert evaluate(0.816).stability_modifiers == evaluate(0.81).stability_modifiers
    assert evaluate(0.29).stability_used == 0.29
    assert evaluate(0.4999).stability_used == 0.49
    assert dict(evaluate(0.4999).stability_modifiers)[
        "industrial_capacity_factory"
    ] == pytest.approx(-0.01)


@pytest.mark.parametrize("support, bonus", [(0, -0.5), (0.5, 0), (1, 0.3)])
def test_war_support_documented_endpoints_and_neutral_point(support, bonus):
    modifiers = evaluate(war_support=support).war_support_modifiers
    assert modifiers is not None
    assert dict(modifiers)["mobilization_speed"] == pytest.approx(bonus)


def test_interior_war_support_scale_requires_explicit_profile_input():
    assert evaluate(war_support=0.75).war_support_modifiers is None
    explicit = evaluate(war_support=0.75, war_support_modifier_scale=0.5)
    assert explicit.war_support_modifiers == (("mobilization_speed", 0.15),)
    with pytest.raises(ValueError):
        evaluate(war_support=0.75, war_support_modifier_scale=1.2)


def test_wartime_stability_term_is_returned_separately_and_not_applied_twice():
    result = evaluate(0.75, 0.5, at_war=True)
    assert result.war_stability_modifier == -0.15
    assert result.stability_used == 0.75
    assert dict(result.stability_modifiers)["industrial_capacity_factory"] == 0.1
    assert evaluate(0.75, 0.5).war_stability_modifier == 0
    assert evaluate(0.75, 1, at_war=True).war_stability_modifier == 0


@pytest.mark.parametrize("value", [-0.01, 1.01, True, float("inf"), float("nan"), "50"])
def test_invalid_current_conditions_are_rejected(value):
    with pytest.raises(ValueError):
        evaluate(stability=value)
    with pytest.raises(ValueError):
        evaluate(war_support=value)


def test_bad_profile_coefficients_and_nonboolean_war_state_are_rejected():
    with pytest.raises(ValueError, match="explicit boolean"):
        evaluate(at_war=1)
    with pytest.raises(ValueError, match="finite"):
        evaluate(stability_good={"output": float("inf")})
    with pytest.raises(ValueError, match="finite"):
        evaluate(war_stability_penalty_at_zero_support=True)


def test_source_profile_extracts_all_tables_with_file_and_line_provenance():
    catalog = build_modifier_catalog(
        [],
        [],
        auxiliary_documents={
            "static_modifiers": [
                parse_script(
                    """
      stability_good_modifier = { industrial_capacity_factory = .2 consumer_goods_factor = -.2 }
      stability_bad_modifier = { industrial_capacity_factory = -.5 }
      war_support_good_modifier = { mobilization_speed = .3 army_core_attack_factor = .1 }
      war_support_bad_modifier = { mobilization_speed = -.5 }
      war_support_during_war = { stability_factor = -.3 }
    """,
                    source="common/modifiers/00_static_modifiers.txt",
                )
            ]
        },
    )
    result = resolve_support_profile(catalog)
    assert result["source_values_complete"]
    assert result["tables"]["war_support_good_modifier"] == {"mobilization_speed": 0.3}
    assert result["contributions"][0]["source"]["path"].endswith("00_static_modifiers.txt")
    assert result["contributions"][0]["line"] == 2


def test_missing_and_nonliteral_static_tables_do_not_produce_usable_defaults():
    catalog = build_modifier_catalog(
        [],
        [],
        auxiliary_documents={
            "static_modifiers": [
                parse_script("stability_good_modifier = { consumer_goods_factor = @unknown }")
            ]
        },
    )
    result = resolve_support_profile(catalog)
    assert not result["source_values_complete"]
    assert len(result["blockers"]) == 5
