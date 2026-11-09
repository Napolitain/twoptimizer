"""History inspection selects only branches proven by explicit context."""

import json

import pytest

from games.hoi4.data_pipeline.selection import (
    SelectionContext,
    Truth,
    all_gameplay_context,
    evaluate_guard,
    select_history,
)
from games.hoi4.data_pipeline.syntax import Atom, parse_script
from games.hoi4.planning.time import CampaignDate


@pytest.fixture
def context():
    return SelectionContext(
        CampaignDate(1936, 1, 1, 12), frozenset({"Enabled", "Disabled"}), frozenset({"Enabled"})
    )


@pytest.mark.parametrize(
    ("guard", "expected"),
    [
        ('has_dlc = "Enabled"', Truth.TRUE),
        ('has_dlc = "Disabled"', Truth.FALSE),
        ('has_dlc = "Unknown"', Truth.UNKNOWN),
        ('has_dlc != "Enabled"', Truth.UNKNOWN),
        ('has_dlc = { value = "Enabled" }', Truth.UNKNOWN),
        ("always = yes", Truth.TRUE),
        ("always = no", Truth.FALSE),
        ("always = 1", Truth.UNKNOWN),
        ('always = "yes"', Truth.UNKNOWN),
        ('AND = { has_dlc = "Enabled" unknown = yes }', Truth.UNKNOWN),
        ('AND = { has_dlc = "Disabled" unknown = yes }', Truth.FALSE),
        ('OR = { has_dlc = "Enabled" unknown = yes }', Truth.TRUE),
        ('OR = { has_dlc = "Disabled" unknown = yes }', Truth.UNKNOWN),
        ('NOT = { has_dlc = "Enabled" has_dlc = "Disabled" }', Truth.FALSE),
        ('NOT = { has_dlc = "Disabled" always = no }', Truth.TRUE),
        ("NOT = { unknown = yes }", Truth.UNKNOWN),
        ("has_start_date < 1936.1.2", Truth.TRUE),
        ("date > 1936.1.1", Truth.TRUE),
        ("date > 1936.1.1.12", Truth.FALSE),
        ("date = 1936.1.1", Truth.UNKNOWN),
        ("date > 1936.2.29", Truth.UNKNOWN),
        ("date > { x = y }", Truth.UNKNOWN),
    ],
)
def test_tristate_guards(guard, expected, context):
    assert evaluate_guard(parse_script(guard).root, context) == expected


@pytest.mark.parametrize(
    "text",
    [
        (
            'if = { limit = { has_dlc = "Disabled" } wrong = 1 '
            'else_if = { limit = { has_dlc = "Enabled" } chosen = 2 } else = { wrong = 3 } }'
        ),
        (
            'if = { limit = { has_dlc = "Disabled" } wrong = 1 } '
            'else_if = { limit = { has_dlc = "Enabled" } chosen = 2 } else = { wrong = 3 }'
        ),
        'if = { limit = { has_dlc = "Disabled" } wrong = 1 } else = { chosen = 2 }',
        'IF = { LIMIT = { has_dlc = "Enabled" } chosen = 2 }',
    ],
)
def test_known_branch_preserves_source_statements(text, context):
    document = parse_script(text)
    selected = select_history(document, context)
    assert [entry.name for entry in selected.entries] == ["chosen"]
    assert document.fragment(selected.entries[0]) == "chosen = 2"
    assert selected.blockers == ()


def test_unknown_parent_does_not_select_known_child_or_else(context):
    selected = select_history(
        parse_script("""
        before = 1
        if = { limit = { unknown = yes } if = { limit = { always = yes } invented = 2 } }
        else = { invented = 3 }
        after = 4
    """),
        context,
    )
    assert [entry.name for entry in selected.entries] == ["before", "after"]
    assert selected.blockers[0].code == "unknown_or_invalid_guard"


def test_nested_if_owns_its_adjacent_else(context):
    selected = select_history(
        parse_script("""
      if = { limit = { always = yes }
        if = { limit = { always = no } wrong = 1 } else = { chosen = 2 }
      }
    """),
        context,
    )
    assert [entry.name for entry in selected.entries] == ["chosen"]
    assert not selected.blockers


@pytest.mark.parametrize(
    ("script", "code"),
    [
        (
            "if = { limit = { always = yes } chosen = 1 else = { wrong = 2 } } "
            "else = { wrong = 3 }",
            "mixed_alternative_placement",
        ),
        ("else = { wrong = 1 }", "orphan_alternative"),
        ("if = no", "invalid_if_block"),
        (
            "if = { limit = { always = no } } else = { wrong = 1 } "
            "else_if = { limit = { always = yes } wrong = 2 }",
            "alternative_after_else",
        ),
        ("if = { missing_limit = yes }", "unknown_or_invalid_guard"),
        ("if = { limit > { always = yes } }", "unknown_or_invalid_guard"),
        (
            "if = { limit = { always = no } } else = { limit = { always = yes } wrong = 1 }",
            "unknown_or_invalid_guard",
        ),
        ("1936.2.29 = { wrong = 1 }", "invalid_dated_history"),
        ("1936.1.1 = no", "invalid_dated_history"),
    ],
)
def test_ambiguous_or_invalid_control_flow_is_a_blocker(script, code, context):
    selected = select_history(parse_script(script), context)
    assert selected.entries == ()
    assert selected.blockers[0].code == code


def test_date_history_strict_boundary_and_duplicate_literals(context):
    selected = select_history(
        parse_script("""
      capital = 1
      1936.1.1 = { capital = 2 }
      1936.1.1.12 = { wrong = 3 }
      1939.1.1 = { wrong = 4 }
    """),
        context,
    )
    assert [entry.name for entry in selected.entries] == ["capital", "capital"]
    assert [
        entry.value.literal() for entry in selected.entries if isinstance(entry.value, Atom)
    ] == [1, 2]


def test_scope_effects_remain_unexecuted_candidates(context):
    document = parse_script("every_country = { if = { limit = { always = yes } effect = 1 } }")
    selected = select_history(document, context)
    assert selected.entries == document.root.entries
    assert selected.decisions == ()


def test_catalog_controls_all_gameplay_and_unknown_identifiers(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(
        json.dumps(
            {
                "dlcs": [
                    {"script_id": "Gameplay", "gameplay": True},
                    {"script_id": "Cosmetic", "gameplay": False},
                ]
            }
        )
    )
    context = all_gameplay_context(CampaignDate(1936, 1, 1), path)
    assert context.enabled_dlcs == frozenset({"Gameplay"})
    assert evaluate_guard(parse_script('has_dlc = "Uncatalogued"').root, context) == Truth.UNKNOWN


def test_invalid_context_and_logic_mode_fail(context):
    with pytest.raises(ValueError, match="CampaignDate"):
        SelectionContext(json.loads('"1936.1.1"'), frozenset(), frozenset())
    with pytest.raises(ValueError, match="frozensets"):
        SelectionContext(context.start, json.loads("[]"), frozenset())
    with pytest.raises(ValueError, match="catalogued"):
        SelectionContext(context.start, frozenset(), frozenset({"Unknown"}))
    with pytest.raises(ValueError, match="guard mode"):
        evaluate_guard(parse_script("").root, context, mode="guess")
