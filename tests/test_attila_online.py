"""Offline tests for source decoding, identities, provenance and culture variants."""

import csv
import json

import pytest

from games.tw.attila.catalogue import technology_available
from games.tw.attila.tools.audit_data import audit
from games.tw.attila.tools.import_online import (
    DATA,
    economic_observations,
    import_data,
    parse_payload,
    records_from_payload,
)


def page(technology="Tech A", build="123"):
    payload = {
        "icons": ["/game/attila/ui/buildings/icons/test_icon.webp"],
        "fx": [["Needs technology: " + technology, -1, 1]],
        "chains": [
            ["test_chain", "Test", [["Test Building", 0, 1, 1200, 3, 100, [0], [], 0]]]
        ],
        "landmarks": [],
    }
    tree = ["$", "component", None, payload]
    push = json.dumps([1, "1:" + json.dumps(tree) + "\n"])
    return f"<div>Steam build <!-- -->{build}</div><script>self.__next_f.push({push})</script>"


def test_decode_and_resolve_identity_without_executing_scripts():
    payload = parse_payload(page())
    records, unresolved = records_from_payload(
        payload, {("test_icon", "test building"): {"att_test"}}
    )
    assert not unresolved
    assert records["att_test"]["construction_cost"] == 1200
    assert records["att_test"]["construction_turns"] == 3
    assert records["att_test"]["upkeep"] == 100
    records, unresolved = records_from_payload(
        payload, {("test_icon", "test building"): {"att_one", "att_two"}}
    )
    assert not records
    assert unresolved[0]["reason"] == "ambiguous"
    with pytest.raises(ValueError, match="Source format changed"):
        parse_payload('<script>alert("not a data payload")</script>')


def test_offline_import_preserves_culture_specific_requirements(tmp_path):
    cache, data = tmp_path / "cache", tmp_path / "data"
    cache.mkdir()
    data.mkdir()
    with (data / "building_culture_variants_table.tsv").open("w") as f:
        csv.writer(f, delimiter="\t").writerow(
            ["att_test", "", "", "", "Test Building", "", "", "", "", "test_icon"]
        )
    for culture, tech in (("eastern-roman", "Tech A"), ("western-roman", "Tech B")):
        (cache / f"{culture}.html").write_text(page(tech))
    output = tmp_path / "output.json"
    report = import_data(
        cache,
        output,
        offline=True,
        cultures=("eastern-roman", "western-roman"),
        data_dir=data,
    )
    assert not report["conflicts"]
    assert report["game_build"] == "123"
    assert report["buildings"]["att_test"]["requirements_by_culture"] == {
        "eastern-roman": [["Tech A"]],
        "western-roman": [["Tech B"]],
    }

    class Candidate:
        name = "att_test"
        metadata = report["buildings"]["att_test"]

    assert technology_available(Candidate(), "eastern-roman", {"Tech A"})
    assert not technology_available(Candidate(), "western-roman", {"Tech A"})
    assert technology_available(Candidate(), "western-roman", None)
    prior = output.read_bytes()
    (cache / "western-roman.html").write_text(page("Tech B", build="456"))
    with pytest.raises(ValueError, match="different game builds"):
        import_data(
            cache,
            output,
            offline=True,
            cultures=("eastern-roman", "western-roman"),
            data_dir=data,
        )
    assert output.read_bytes() == prior


def test_observations_preserve_percentages_and_reach():
    facts = economic_observations(
        [
            "Wealth: +20% from industrial buildings (province to each region)",
            "Tax rate: +4%",
            "Public order: +2",
            "Food consumption: -30",
        ]
    )
    assert facts == [
        {
            "kind": "wealth_percent",
            "category": "industry",
            "reach": "province",
            "value": 20,
        },
        {"kind": "tax_percent", "category": None, "reach": "province", "value": 4},
        {"kind": "public_order", "category": None, "reach": "province", "value": 2},
        {"kind": "food_consumption", "category": None, "reach": "region", "value": 30},
    ]


def test_checked_in_data_has_provenance_and_no_eastern_roman_disagreements():
    source = json.loads((DATA / "online_buildings.json").read_text())
    assert len(source["buildings"]) == 566
    assert len(source["sources"]) == 11
    assert all(len(record["sha256"]) == 64 for record in source["sources"])
    assert not source["conflicts"]
    report = audit()
    assert report["online_numeric_matches"] > 6000
    assert not [
        record
        for record in report["online_numeric_differences"]
        if record["culture"] == "eastern-roman"
    ]
    assert len(report["effects"]) == report["effect_scope_pairs"]
