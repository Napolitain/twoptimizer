"""Source syntax and provenance must survive ingestion without game assumptions."""

import json
from hashlib import sha256
from pathlib import Path

import pytest

from games.hoi4.data_pipeline import (
    Atom,
    Block,
    ScriptSyntaxError,
    SourceContext,
    TaggedBlock,
    inspect_document,
    inventory_sources,
    parse_bytes,
    parse_file,
    parse_script,
    syntax_record,
)
from games.hoi4.data_pipeline.__main__ import main
from games.hoi4.data_pipeline.syntax import recover_complete_children
from games.hoi4.parsers.base_parser import ParseError
from games.hoi4.parsers.focus_parser import FocusParser


def _block(parent: Block, name: str) -> Block:
    (value,) = parent.assignments(name)
    assert isinstance(value, Block)
    return value


def test_ordered_syntax_retains_scopes_duplicates_and_block_forms():
    source = """focus_tree = {
        focus = { id = first prerequisite = { focus = a focus = b } }
        focus = { id = second prerequisite = { focus = first } }
        conditional = { if = { limit = { factories > 10 } add = 1 } }
        values = { first "second" 3 }
        mixed = { 1 key = value }
        empty = {}
    }"""
    document = parse_script(source)
    tree = _block(document.root, "focus_tree")
    focuses = tree.assignments("focus")
    assert len(focuses) == 2
    assert isinstance(focuses[0], Block)
    prerequisites = _block(focuses[0], "prerequisite")
    assert [
        entry.value.literal() for entry in prerequisites.entries if isinstance(entry.value, Atom)
    ] == ["a", "b"]
    assert _block(tree, "values").form == "list"
    assert _block(tree, "mixed").form == "mixed"
    assert _block(tree, "empty").form == "empty"
    limit = _block(_block(_block(tree, "conditional"), "if"), "limit")
    assert limit.entries[0].operator == ">"
    assert limit.assignments("factories") == ()
    assert document.fragment(prerequisites) == "{ focus = a focus = b }"


def test_exact_source_hash_positions_and_quoted_comments():
    payload = b'\xef\xbb\xbf# heading\r\nname = "a#b \\"quoted\\"" # ignored\r\nnext = yes\r\n'
    document = parse_bytes(payload, source="source.txt")
    assert document.sha256 == sha256(payload).hexdigest()
    assert document.text.encode("utf-8") == payload
    name, following = document.root.entries
    assert document.position(name.span.start) == (2, 1)
    assert document.position(following.span.start) == (3, 1)
    assert isinstance(name.value, Atom)
    assert name.value.literal() == 'a#b "quoted"'
    assert document.fragment(name) == 'name = "a#b \\"quoted\\""'
    assert document.position(len(document.text)) == (4, 1)
    with pytest.raises(ValueError, match="outside"):
        document.position(-1)
    with pytest.raises(ValueError, match="outside"):
        document.position(len(document.text) + 1)


@pytest.mark.parametrize(
    "operator", ["=", "!=", "<=", ">=", "==", "?=", "+=", "-=", "*=", "/=", "<", ">"]
)
def test_comparison_and_assignment_operators_remain_distinct(operator):
    (entry,) = parse_script(f"key{operator}value").root.entries
    assert entry.operator == operator
    assert isinstance(entry.value, Atom)
    assert entry.value.literal() == "value"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("yes", True),
        ("no", False),
        ("1", 1),
        ("-2", -2),
        (".25", 0.25),
        ("1e-2", 0.01),
        ('"yes"', "yes"),
        ("1936.1.1", "1936.1.1"),
        ("@cost", "@cost"),
        ("1e999", "1e999"),
    ],
)
def test_literal_decoding_leaves_dates_variables_and_nonfinite_numbers_as_text(source, expected):
    (value,) = parse_script(f"value = {source}").root.assignments("value")
    assert isinstance(value, Atom)
    assert value.literal() == expected
    json.dumps(value.literal(), allow_nan=False)


def test_expressions_tags_and_unknown_escape_sequences_are_preserved():
    source = r'cost = @[ @base * [2 + 3] ] color = rgb { 1 2 3 } path = "a\q"'
    document = parse_script(source)
    cost, color, path = (entry.value for entry in document.root.entries)
    assert isinstance(cost, Atom)
    assert cost.kind == "expression"
    assert cost.literal() == "@[ @base * [2 + 3] ]"
    assert isinstance(color, TaggedBlock)
    assert color.tag.literal() == "rgb"
    assert color.block.form == "list"
    assert isinstance(path, Atom)
    assert path.literal() == r"a\q"
    record = syntax_record(color)
    assert record["kind"] == "tagged"
    assert len(record["block"]["entries"]) == 3
    assert json.loads(json.dumps(syntax_record(document.root)))["kind"] == "object"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("a = {", "Unclosed block"),
        ("}", "Unexpected closing brace"),
        ('a = "unterminated', "Unterminated quoted string"),
        ("a = @[ x", "Unterminated script expression"),
        ("a =", "Expected a scalar value"),
        ("= 1", "Expected a scalar value"),
    ],
)
def test_malformed_syntax_fails_with_source_position(source, message):
    with pytest.raises(ScriptSyntaxError, match=message) as caught:
        parse_script(source, source="broken.txt")
    assert caught.value.source == "broken.txt"
    assert caught.value.line == 1
    assert caught.value.column >= 1
    assert "broken.txt:1:" in str(caught.value)


def test_nesting_limit_fails_explicitly():
    with pytest.raises(ScriptSyntaxError, match="nesting exceeds"):
        parse_script("a={" * 201 + "}" * 201)


def test_recovery_keeps_only_complete_children_and_original_offsets():
    source = 'prefix = 1\ncontainer = { complete = { id = "a}" } broken = { id = b'
    offset = source.index("{")
    recovered = recover_complete_children(source, offset, source="incomplete.txt")
    assert recovered.complete is False
    assert [entry.name for entry in recovered.entries] == ["complete"]
    (entry,) = recovered.entries
    assert source[entry.span.start : entry.span.end] == 'complete = { id = "a}" }'
    assert recovered.error is not None
    assert recovered.error.source == "incomplete.txt"
    assert recovered.error.offset == source.index("{ id = b")
    with pytest.raises(ValueError, match="opening brace"):
        recover_complete_children(source, 0)


def test_recovery_distinguishes_missing_parent_brace_from_complete_parent():
    source = "container = { first = { value = 1 } second = {} # trailing comment"
    offset = source.index("{")
    recovered = recover_complete_children(source, offset)
    assert recovered.complete is False
    assert recovered.error is not None
    assert recovered.error.offset == offset
    assert len(recovered.entries) == 2
    closed = recover_complete_children(source + "\n}", offset)
    assert closed.complete is True
    assert closed.error is None
    assert closed.entries == recovered.entries


def test_inventory_reports_facts_unknown_fields_and_prerequisite_groups():
    document = parse_script("""focus_tree = { id = tree
        focus = { id = target cost = @cost
            prerequisite = { focus = a focus = b }
            prerequisite = { focus = c }
            available = { always = yes }
            completion_reward = { add_ideas = industry }
        }
        focus = { id = target }
    }""")
    report = inspect_document(document, "national_focus")
    assert report["status"] == "parsed"
    assert report["semantic_execution"] == "not_implemented"
    first, second = report["records"]
    assert first["id"] == second["id"] == "target"
    assert first["group"] == "tree"
    assert [fact["field"] for fact in first["facts"]] == ["id", "cost"]
    assert first["facts"][1]["syntax"]["text"] == "@cost"
    assert len(first["prerequisite_groups"]) == 2
    assert len(first["prerequisite_groups"][0]["syntax"]["entries"]) == 2
    assert {item["field"] for item in first["unhandled_fields"]} == {
        "prerequisite",
        "available",
        "completion_reward",
    }
    assert report["duplicate_record_ids"] == [
        {"kind": "focus", "group": "tree", "id": "target", "occurrences": 2}
    ]
    assert [fact["field"] for fact in second["facts"]] == ["id"]


def test_inventory_preserves_provenance_errors_and_missing_coverage(tmp_path):
    buildings = tmp_path / "common" / "buildings"
    buildings.mkdir(parents=True)
    payload = b"\xef\xbb\xbfbuildings = { factory = { base_cost = 7200 modifier = { bonus = 1 } } }"
    (buildings / "valid.txt").write_bytes(payload)
    (buildings / "broken.txt").write_text("buildings = {")
    (buildings / "invalid.txt").write_bytes(b"\xff")
    (tmp_path / "notes.md").write_text("Not Clausewitz syntax")
    context = SourceContext(origin_url="https://example.com/source", revision="pinned")
    report = inventory_sources(tmp_path, context=context)
    assert report == inventory_sources(tmp_path, context=context)
    assert report["source_context"] == {
        "origin_url": "https://example.com/source",
        "revision": "pinned",
        "game_build": None,
        "retrieved_at_utc": None,
    }
    assert report["coverage"]["statuses"] == {
        "syntax_error": 1,
        "encoding_error": 1,
        "parsed": 1,
        "unsupported_format": 1,
    }
    assert report["coverage"]["records"] == {"building": 1}
    assert report["coverage"]["executed_effects"] == 0
    assert "countries" in report["coverage"]["missing_categories"]
    valid = next(source for source in report["sources"] if source["status"] == "parsed")
    assert valid["sha256"] == sha256(payload).hexdigest()
    assert valid["utf8_bom"] is True
    assert valid["records"][0]["unhandled_fields"][0]["field"] == "modifier"
    assert "not evaluated" in report["semantics"]
    before = report["source_set_sha256"]
    (buildings / "valid.txt").write_bytes(payload + b"\n")
    assert inventory_sources(tmp_path)["source_set_sha256"] != before


def test_empty_inventory_and_unknown_schema_are_not_complete_data(tmp_path):
    report = inventory_sources(tmp_path)
    assert report["coverage"]["files"] == 0
    assert report["coverage"]["missing_categories"]
    assert (
        inspect_document(parse_script("unknown = { a = 1 }"), "unknown")["fact_schema"] == "unknown"
    )
    with pytest.raises(ValueError, match="existing directory"):
        inventory_sources(tmp_path / "missing")


def test_inventory_command_writes_report_even_when_source_syntax_fails(tmp_path, capsys):
    source = tmp_path / "source"
    source.mkdir()
    path = source / "sample.txt"
    path.write_text("incomplete = {")
    output = tmp_path / "inventory.json"
    assert main([str(source), "--output", str(output), "--revision", "pinned"]) == 1
    report = json.loads(output.read_text())
    assert report["coverage"]["statuses"] == {"syntax_error": 1}
    assert report["source_context"]["revision"] == "pinned"
    path.write_text("complete = {}")
    assert main([str(source)]) == 0
    assert json.loads(capsys.readouterr().out)["coverage"]["statuses"] == {"parsed": 1}
    with pytest.raises(SystemExit) as caught:
        main([str(tmp_path / "missing")])
    assert caught.value.code == 2
    assert "Source inventory failed:" in capsys.readouterr().err


def test_bundled_buildings_are_read_as_source_facts():
    path = Path("games/hoi4/data/buildings/00_buildings.txt")
    report = inspect_document(parse_file(path), "buildings")
    buildings = {record["id"]: record for record in report["records"]}
    for name, cost in (("arms_factory", "7200"), ("industrial_complex", "10800")):
        costs = [
            fact["syntax"]["text"]
            for fact in buildings[name]["facts"]
            if fact["field"] == "base_cost"
        ]
        assert costs == [cost]


def test_legacy_focus_view_keeps_distinct_focus_ids_and_original_groups(tmp_path):
    path = tmp_path / "focus.txt"
    payload = b"""\xef\xbb\xbffocus_tree = { id = first country = { modifier = { tag = FRA } }
        focus = { id = a cost = 5 search_filters = { FOCUS_FILTER_INDUSTRY } }
        focus = { id = b prerequisite = { focus = a focus = x }
            prerequisite = { focus = y } completion_reward = { add = 1 } }
    }
    focus_tree = { id = second focus = { id = c } }
    """
    path.write_bytes(payload)
    parser = FocusParser()
    trees = parser.parse_file(path)
    assert set(trees) == {"first", "second"}
    assert set(trees["first"].focuses) == {"a", "b"}
    assert set(trees["second"].focuses) == {"c"}
    assert trees["first"].focuses["b"].prerequisites == ["a", "x", "y"]
    assert trees["first"].focuses["a"].cost == 5
    assert trees["first"].focuses["a"].search_filters[0].value == "FOCUS_FILTER_INDUSTRY"
    document = parser.documents[str(path)]
    assert document.sha256 == sha256(payload).hexdigest()
    groups = inspect_document(document, "national_focus")["records"][1]["prerequisite_groups"]
    assert len(groups) == 2
    path.write_bytes(b"\xff")
    with pytest.raises(ParseError, match="Error parsing"):
        parser.parse_file(path)
