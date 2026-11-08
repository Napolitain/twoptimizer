"""Initial economic modifiers preserve provenance, scope and unknown quantities."""

import json
from typing import cast

import pytest

from games.hoi4.data_pipeline.modifier_resolution import (
    build_modifier_catalog,
    load_modifier_catalog,
    resolve_country_modifiers,
)
from games.hoi4.data_pipeline.selection import SelectionContext
from games.hoi4.data_pipeline.syntax import parse_script
from games.hoi4.planning.time import CampaignDate


@pytest.fixture
def context():
    return SelectionContext(CampaignDate(1936, 1, 1, 12), frozenset({"DLC"}), frozenset({"DLC"}))


def resolve(context, history="", *, ideas="", technologies="", dynamics=""):
    catalog = build_modifier_catalog(
        [parse_script(f"ideas = {{ {ideas} }}", source="common/ideas/test.txt")],
        [
            parse_script(
                f"technologies = {{ {technologies} }}", source="common/technologies/test.txt"
            )
        ],
        [parse_script(dynamics, source="common/dynamic_modifiers/test.txt")],
    )
    return resolve_country_modifiers(
        parse_script(history, source="history/countries/FRA.txt"), context, catalog, tag="FRA"
    )


def test_france_spirits_and_default_trade_law_preserve_distinct_manpower_factors(context):
    # Numeric observations: pinned france.txt lines 18, 73, 1254; _economic.txt 108, 1341.
    ideas = """
      economy = { law = yes civilian_economy = {
        default = yes modifier = { consumer_goods_expected_value = .35
          production_speed_industrial_complex_factor = -.3 }
      } }
      trade_laws = { law = yes export_focus = { default = yes modifier = {
        industrial_capacity_factory = .1 production_speed_buildings_factor = .1 min_export = .5
      } } }
      mobilization_laws = { law = yes
        volunteer_only = { default = yes modifier = { conscription = .015 } }
        limited_conscription = { modifier = { conscription = .025 } }
        unavailable_default = { default = yes allowed = { always = no }
          modifier = { conscription = .99 } }
      }
      country = {
        FRA_inefficient_economy_2 = { allowed = { original_tag = FRA always = no }
          modifier = { industrial_capacity_factory = -.2 } }
        FRA_full_employment = { allowed = { always = no }
          modifier = { conscription_factor = -.25 } }
        FRA_victors_of_wwi = { modifier = { conscription = -.003 } }
      }
    """
    report = resolve(
        context,
        "add_ideas = { limited_conscription FRA_inefficient_economy_2 "
        "FRA_full_employment FRA_victors_of_wwi }",
        ideas=ideas,
    )
    values = report["additive_modifiers"]
    assert values["industrial_capacity_factory"] == pytest.approx(-0.1)
    assert values["consumer_goods_expected_value"] == 0.35
    assert values["conscription"] == pytest.approx(0.022)
    assert values["conscription_factor"] == -0.25
    assert values["production_speed_industrial_complex_factor"] == -0.3
    assert values["production_speed_buildings_factor"] == 0.1
    assert report["selected_country_modifiers_complete"]
    assert not report["effective_country_economy_resolved"] and not report["scenario_ready"]
    assert "volunteer_only" not in {row["id"] for row in report["active_ideas"]}
    assert report["contributions"][0]["source"]["sha256"]


def test_consumer_goods_factors_multiply_individually_with_additive_base(context):
    report = resolve(
        context,
        "add_ideas = { a b }",
        ideas="""
      country = {
        a = { modifier = { consumer_goods_factor = .5 consumer_goods_expected_value = .3 } }
        b = { modifier = { consumer_goods_factor = -.5 consumer_goods_expected_value = .05 } }
      }
    """,
    )
    assert report["multiplicative_modifiers"] == {"consumer_goods_factor": [0.5, -0.5]}
    assert report["consumer_goods_factor_product"] == 0.75
    assert report["additive_modifiers"]["consumer_goods_expected_value"] == pytest.approx(0.35)
    assert "consumer_goods_factor" not in report["additive_modifiers"]


def test_history_hooks_and_technology_metadata_do_not_apply_as_initial_modifiers(context):
    report = resolve(
        context,
        "add_ideas = a set_technology = { tools = 1 popup = no }",
        ideas="""
      country = { a = { modifier = { industrial_capacity_factory = .1 }
        on_add = { add_ideas = absent } on_remove = { add_ideas = absent }
        available = { unknown = yes } picture = absent_picture
      } }
    """,
        technologies="""
      tools = { production_factory_max_efficiency_factor = .1
        research_cost = 9 path = { research_cost_coeff = .5 }
        on_research_complete = { add_ideas = absent }
        ai_will_do = { modifier = { industrial_capacity_factory = 99 } }
      }
    """,
    )
    assert report["additive_modifiers"] == {
        "industrial_capacity_factory": 0.1,
        "production_factory_max_efficiency_factor": 0.1,
    }
    assert not report["blockers"]


@pytest.mark.parametrize(
    "guard, included",
    [
        ("always = yes", True),
        ("always = no", False),
        ('has_dlc = "DLC"', True),
        ("tag = FRA", True),
        ("original_tag = GER", False),
        ("NOT = { tag = GER always = no }", True),
        ("OR = { tag = GER tag = FRA }", True),
    ],
)
def test_do_effect_controls_spirit_without_removing_it(context, guard, included):
    report = resolve(
        context,
        "add_ideas = a",
        ideas=f"country = {{ a = {{ do_effect = {{ {guard} }} "
        "modifier = { industrial_capacity_factory = .2 } } }",
    )
    assert ("industrial_capacity_factory" in report["additive_modifiers"]) is included
    assert report["active_ideas"] == [{"id": "a", "origin": "history"}]
    assert not report["blockers"]


def test_unknown_do_effect_never_becomes_zero_bonus_or_true(context):
    report = resolve(
        context,
        "add_ideas = a",
        ideas="country = { a = { do_effect = { has_war = yes } "
        "modifier = { industrial_capacity_factory = .2 } } }",
    )
    assert report["additive_modifiers"] == {}
    assert report["blocked_fields"] == ["industrial_capacity_factory"]
    assert report["blockers"][0]["code"] == "unknown_modifier_guard"


def test_unknown_portrait_branch_does_not_block_known_economic_effects(context):
    report = resolve(
        context,
        "if = { limit = { unknown = yes } set_portrait = portrait } add_ideas = a",
        ideas="country = { a = { modifier = { conscription = .01 } } }",
    )
    assert report["additive_modifiers"] == {"conscription": 0.01}
    assert report["selected_country_modifiers_complete"]
    assert len(report["other_history_branch_diagnostics"]) == 1


def test_ideas_are_deduplicated_and_remove_operations_execute_in_order(context):
    report = resolve(
        context,
        "add_ideas = { a a b } remove_ideas = b add_ideas = a",
        ideas="country = { a = { modifier = { conscription = .01 } } "
        "b = { modifier = { conscription = .2 } } }",
    )
    assert report["additive_modifiers"] == {"conscription": 0.01}
    assert report["active_ideas"] == [{"id": "a", "origin": "history"}]


def test_selected_dlc_and_date_histories_change_only_applicable_technology(context):
    history = """
      if = { limit = { has_dlc = "DLC" } set_technology = { a = 1 } }
      else = { set_technology = { absent = 1 } }
      1936.1.1.12 = { set_technology = { absent = 1 } }
      1936.1.1 = { set_technology = { b = 1 a = 0 } }
    """
    report = resolve(
        context,
        history,
        technologies="a = { industrial_capacity_factory = .1 } "
        "b = { industrial_capacity_factory = .2 }",
    )
    assert report["researched_technologies"] == ["b"]
    assert report["additive_modifiers"] == {"industrial_capacity_factory": 0.2}


def test_dynamic_modifier_distinguishes_documented_unset_defaults_from_history_values(context):
    report = resolve(
        context,
        """
      set_variable = { mefo = .1 } set_variable = { alias = mefo }
      add_dynamic_modifier = { modifier = economic }
      multiply_variable = { mefo = 2 }
      add_to_variable = { alias = .2 }
    """,
        dynamics="economic = { enable = { always = yes } consumer_goods_factor = mefo "
        "production_speed_buildings_factor = alias industrial_capacity_factory = absent }",
    )
    assert report["multiplicative_modifiers"]["consumer_goods_factor"] == [0.2]
    assert report["additive_modifiers"]["production_speed_buildings_factor"] == pytest.approx(0.3)
    assert report["additive_modifiers"]["industrial_capacity_factory"] == 0
    assert report["blocked_fields"] == []
    assert report["contributions"][-1]["value_origin"] == "unset_variable_default"
    assert report["contributions"][0]["variable"] == "mefo"


@pytest.mark.parametrize(
    "operation, expected",
    [
        ("subtract_from_variable", 6),
        ("multiply_variable", 16),
        ("divide_variable", 4),
        ("add_to_variable", 10),
    ],
)
def test_literal_variable_arithmetic(operation, expected, context):
    report = resolve(
        context,
        f"set_variable = {{ amount = 8 }} {operation} = {{ amount = 2 }} "
        "add_dynamic_modifier = { modifier = a }",
        dynamics="a = { consumer_goods_expected_value = amount }",
    )
    assert report["additive_modifiers"] == {"consumer_goods_expected_value": expected}


@pytest.mark.parametrize(
    "history", ["divide_variable = { amount = 0 }", "multiply_variable = { amount = @unknown }"]
)
def test_invalid_variable_result_does_not_become_zero(context, history):
    report = resolve(
        context,
        "set_variable = { amount = .2 } " + history + "add_dynamic_modifier = { modifier = a }",
        dynamics="a = { consumer_goods_expected_value = amount }",
    )
    assert report["additive_modifiers"] == {}
    assert report["blocked_fields"] == ["consumer_goods_expected_value"]


def test_scoped_equipment_bonus_is_not_added_as_a_global_build_cost(context):
    report = resolve(
        context,
        "add_ideas = a set_technology = { b = 1 }",
        ideas="""
      country = { a = { equipment_bonus = { infantry_equipment = { build_cost_ic = -.2 } }
        modifier = { industrial_capacity_factory = .1 } } }
    """,
        technologies="b = { infantry = { manpower = -.1 } industrial_capacity_factory = .2 }",
    )
    assert report["additive_modifiers"] == {"industrial_capacity_factory": pytest.approx(0.3)}
    assert report["blocked_fields"] == ["build_cost_ic", "manpower"]
    assert len(report["blockers"]) == 2


@pytest.mark.parametrize("value", ["@unresolved", '".1"', "yes", "{ amount = .1 }"])
def test_nonliteral_economic_modifier_is_preserved_as_unknown(context, value):
    report = resolve(
        context,
        "add_ideas = a",
        ideas=f"country = {{ a = {{ modifier = {{ industrial_capacity_factory = {value} " + "} } }",
    )
    assert report["additive_modifiers"] == {}
    assert report["blocked_fields"] == ["industrial_capacity_factory"]


def test_duplicate_definitions_and_duplicate_numeric_fields_are_not_summed(context):
    report = resolve(
        context,
        "add_ideas = { a b }",
        ideas="country = { a = {} a = {} "
        "b = { modifier = { conscription = .01 conscription = .02 } } }",
    )
    assert report["additive_modifiers"] == {}
    assert {row["code"] for row in report["blockers"]} == {
        "ambiguous_definition",
        "ambiguous_economic_declaration",
    }


def test_missing_idea_and_technology_definitions_block_completeness(context):
    report = resolve(context, "add_ideas = absent set_technology = { absent = 1 }")
    assert len(report["blockers"]) == 2
    assert all(row["code"] == "missing_definition" for row in report["blockers"])
    assert not report["selected_country_modifiers_complete"]


def test_default_law_ambiguity_and_unknown_eligibility_are_explicit(context):
    report = resolve(
        context,
        ideas="economy = { law = yes a = { default = yes } "
        "b = { default = yes } c = { default = yes allowed = { unknown = yes } } }",
    )
    assert report["active_ideas"] == []
    assert {row["code"] for row in report["blockers"]} == {
        "ambiguous_default_law",
        "unknown_default_eligibility",
    }


@pytest.mark.parametrize(
    "history, code",
    [
        ("if = { limit = { unknown = yes } add_ideas = a }", "unresolved_history_branch"),
        ("swap_ideas = { remove_idea = a add_idea = b }", "unsupported_economic_history_operation"),
        ("set_technology = { a = .5 }", "unresolved_technology_level"),
        ("set_technology = yes", "invalid_technology_operation"),
        ("add_ideas = { a = yes }", "invalid_idea_operation"),
        ("add_dynamic_modifier = { modifier = a days = 3 }", "scoped_or_timed_dynamic_modifier"),
        ("add_dynamic_modifier = yes", "invalid_dynamic_modifier_operation"),
    ],
)
def test_unsupported_history_is_not_silently_interpreted(context, history, code):
    report = resolve(context, history)
    assert code in {row["code"] for row in report["blockers"]}


def test_dynamic_removal_and_unknown_enable_are_blockers(context):
    report = resolve(
        context,
        "add_dynamic_modifier = { modifier = a } add_dynamic_modifier = { modifier = b }",
        dynamics="""
      a = { enable = { unknown = yes } industrial_capacity_factory = .1 }
      b = { remove_trigger = { unknown = yes } consumer_goods_factor = .1 }
    """,
    )
    assert {row["code"] for row in report["blockers"]} == {
        "unknown_modifier_guard",
        "unresolved_dynamic_removal_condition",
    }


def test_remove_dynamic_modifier_omits_contribution(context):
    report = resolve(
        context,
        "add_dynamic_modifier = { modifier = a } remove_dynamic_modifier = { modifier = a }",
        dynamics="a = { industrial_capacity_factory = .1 }",
    )
    assert not report["active_dynamic_modifiers"] and not report["contributions"]


def test_catalog_is_immutable_and_result_is_json_serializable(context):
    catalog = build_modifier_catalog([], [])
    with pytest.raises(TypeError):
        cast(dict, catalog.ideas)["x"] = ()
    report = resolve_country_modifiers(parse_script(""), context, catalog, tag="FRA")
    assert json.loads(json.dumps(report))["country"] == "FRA"


def test_loader_recovers_only_complete_children_and_records_original_hash(tmp_path, context):
    folder = tmp_path / "common/ideas"
    folder.mkdir(parents=True)
    # Mirrors the public SOV file's missing outer brace without fixing source text.
    source = "ideas = { country = { a = { modifier = { conscription = .01 } } }"
    (folder / "unclosed.txt").write_text(source)
    (folder / "invalid.txt").write_text("ideas = { country = { broken = {")
    catalog = load_modifier_catalog(tmp_path)
    report = resolve_country_modifiers(parse_script("add_ideas = a"), context, catalog, tag="FRA")
    assert report["additive_modifiers"] == {"conscription": 0.01}
    assert len(catalog.parse_diagnostics) == 2
    assert {row["path"] for row in catalog.input_sources} == {
        "common/ideas/unclosed.txt",
        "common/ideas/invalid.txt",
    }
    assert catalog.input_sources[1]["bytes"] == len(source.encode())


def test_catalog_fingerprints_include_technology_and_dynamic_sources(context):
    catalog = build_modifier_catalog(
        [],
        [parse_script("technologies = { a = {} }", source="tech")],
        [parse_script("b = {}", source="dynamic")],
    )
    assert [row["path"] for row in catalog.input_sources] == ["dynamic", "tech"]
    report = resolve_country_modifiers(
        parse_script("set_technology = { a = 1 }"), context, catalog, tag="FRA"
    )
    assert not report["blockers"]


def test_advisor_idea_token_resolves_only_the_hired_recruited_character_trait(context):
    catalog = build_modifier_catalog(
        [],
        [],
        auxiliary_documents={
            "characters": [
                parse_script(
                    """characters = {
          person = { advisor = { idea_token = hired_person traits = { employed } } }
          other = { advisor = { idea_token = unused_person traits = { unused } } }
        }""",
                    source="common/characters/SOV.txt",
                )
            ],
            "traits": [
                parse_script(
                    """leader_traits = {
          employed = { stability_factor = -.05 enemy_operative_detection_chance = .1 }
          unused = { industrial_capacity_factory = .9 }
        }""",
                    source="common/country_leader/00_traits.txt",
                )
            ],
        },
    )
    history = parse_script(
        "recruit_character = person recruit_character = other add_ideas = hired_person"
    )
    report = resolve_country_modifiers(history, context, catalog, tag="SOV")
    assert report["additive_modifiers"] == {"stability_factor": -0.05}
    assert report["contributions"][0]["identifier"] == "employed"
    assert not report["blockers"]
    unresolved = resolve_country_modifiers(
        parse_script("add_ideas = hired_person"), context, catalog, tag="SOV"
    )
    assert unresolved["blockers"][0]["code"] == "advisor_character_not_recruited"


def test_unknown_variable_assignment_branch_is_not_an_unset_zero_default(context):
    report = resolve(
        context,
        "if = { limit = { unknown = yes } set_variable = { amount = .2 } } "
        "add_dynamic_modifier = { modifier = a }",
        dynamics="a = { consumer_goods_factor = amount }",
    )
    assert not report["contributions"]
    assert "consumer_goods_factor" in report["blocked_fields"]


@pytest.mark.parametrize(
    "assignment",
    [
        'set_variable = { amount = "text" }',
        "set_variable = { amount = { value = .1 } }",
        "set_variable = invalid",
    ],
)
def test_unknown_or_invalid_variable_writes_are_distinct_from_truly_unset_variables(
    context, assignment
):
    report = resolve(
        context,
        assignment + " add_dynamic_modifier = { modifier = a }",
        dynamics="a = { consumer_goods_factor = amount }",
    )
    assert not report["contributions"]
    assert report["blocked_fields"] == ["consumer_goods_factor"]


def test_government_guard_disproves_dynamic_removal_and_tooltip_only_scopes_do_not_block(context):
    report = resolve(
        context,
        "set_politics = { ruling_party = neutrality } "
        "add_dynamic_modifier = { modifier = shinto } "
        "add_dynamic_modifier = { modifier = tooltip }",
        dynamics="shinto = { remove_trigger = { has_government = communism } "
        "stability_factor = .05 } "
        "tooltip = { remove_trigger = {} custom_modifier_tooltip = text }",
    )
    assert report["additive_modifiers"] == {"stability_factor": 0.05}
    assert not report["blockers"]


def test_equipment_group_cost_bonuses_expand_nested_groups_but_stay_scoped(context):
    catalog = build_modifier_catalog(
        [
            parse_script("""ideas = { country = { army = {
      equipment_bonus = { combined = { build_cost_ic = .025 instant = yes } }
    } } }""")
        ],
        [],
        auxiliary_documents={
            "equipment_groups": [
                parse_script(
                    """
      infantry = { equipment_type = { infantry_equipment support_equipment } }
      combined = { equipment_type = { infantry artillery_equipment } }
    """,
                    source="common/equipment_groups/groups.txt",
                )
            ]
        },
    )
    result = resolve_country_modifiers(
        parse_script("add_ideas = army"), context, catalog, tag="JAP"
    )
    assert not result["blockers"] and not result["additive_modifiers"]
    row = result["scoped_modifiers"][0]
    assert row["selectors"] == ["artillery_equipment", "infantry_equipment", "support_equipment"]
    assert row["operation"] == "relative_cost_factor" and row["value"] == 0.025


def test_equipment_group_cycle_does_not_resolve_as_an_empty_free_bonus(context):
    catalog = build_modifier_catalog(
        [
            parse_script(
                "ideas = { country = { a = { equipment_bonus = { "
                "cycle = { build_cost_ic = -.1 instant = yes } } } } }"
            )
        ],
        [],
        auxiliary_documents={
            "equipment_groups": [parse_script("cycle = { equipment_type = { cycle } }")]
        },
    )
    result = resolve_country_modifiers(parse_script("add_ideas = a"), context, catalog, tag="JAP")
    assert not result["scoped_modifiers"]
    assert result["blockers"][0]["code"] == "unresolved_equipment_bonus_application"
