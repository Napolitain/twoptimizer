"""Source quantities aggregate without guessing missing facts or effective rules."""

from copy import deepcopy

import pytest

from games.hoi4.data_pipeline.public_import import (
    load_reference_country,
    load_reference_equipment,
)
from games.hoi4.data_pipeline.template_requirements import summarize_template_requirements


def unit(identifier="infantry", *, manpower=1000, training=90, need=None):
    need = {"infantry_equipment": 100} if need is None else need
    return {
        "id": identifier,
        "source": {"path": f"common/units/{identifier}.txt", "sha256": "source-hash"},
        "line": 2,
        "declarations": [
            {"field": "manpower", "value": manpower, "line": 3},
            {"field": "training_time", "value": training, "line": 4},
        ],
        "need": [
            {
                "line": 5,
                "declarations": [
                    {"field": key, "value": value, "line": 6} for key, value in need.items()
                ],
                "unresolved_statements": [],
            }
        ],
        "unresolved_statements": [{"field": "forest", "line": 9}],
    }


def template(*regiments, support=()):
    return {
        "name": "Source template",
        "line": 12,
        "regiments": [{"unit": key, "line": index + 14} for index, key in enumerate(regiments)],
        "support": [{"unit": key, "line": index + 20} for index, key in enumerate(support)],
        "unresolved_statements": [],
    }


def summarize(*definitions, composition=None):
    return summarize_template_requirements(
        composition or template("infantry"), {"units": list(definitions)}
    )


def test_regiments_and_support_sum_equipment_and_manpower_but_take_max_training():
    infantry = unit()
    artillery = unit("artillery", manpower=300, training=120, need={"artillery_equipment": 12})
    summary = summarize(
        infantry, artillery, composition=template("infantry", "infantry", support=("artillery",))
    )
    assert summary["unit_counts"] == {"infantry": 2, "artillery": 1}
    assert summary["base_equipment"] == {"infantry_equipment": 200, "artillery_equipment": 12}
    assert summary["base_manpower"] == 2300 and summary["base_training_days"] == 120
    assert summary["base_requirements_complete"] and not summary["unknowns"]
    assert not summary["effective_requirements_resolved"]
    assert "eligibility" in summary["semantics"] and "substitutions" in summary["semantics"]
    assert summary["aggregation_rule_evidence"].endswith("#training.duration")


@pytest.mark.parametrize(
    "definitions, reason", [([], "missing_unit"), ([unit(), unit()], "ambiguous_unit")]
)
def test_missing_or_ambiguous_units_cannot_be_counted_as_zero(definitions, reason):
    summary = summarize(*definitions)
    assert not summary["base_requirements_complete"]
    assert all(
        summary[field] is None
        for field in ("base_equipment", "base_manpower", "base_training_days")
    )
    assert summary["unknowns"] == [{"unit": "infantry", "field": "unit", "reason": reason}]
    assert len(summary["units"][0]["definitions"]) == len(definitions)


@pytest.mark.parametrize("value", ["@amount", "100", True, -1, float("nan"), float("inf")])
def test_nonliteral_or_invalid_manpower_does_not_erase_other_known_requirements(value):
    summary = summarize(unit(manpower=value))
    assert summary["base_manpower"] is None
    assert summary["base_equipment"] == {"infantry_equipment": 100}
    assert summary["base_training_days"] == 90
    assert summary["unknowns"][0]["reason"] == "nonliteral_or_invalid_number"


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unresolved"])
def test_incomplete_training_declarations_leave_duration_unknown(kind):
    record = unit()
    if kind == "missing":
        record["declarations"].pop()
    elif kind == "duplicate":
        record["declarations"].append({"field": "training_time", "value": 90, "line": 10})
    else:
        record["unresolved_statements"].append({"field": "training_time", "line": 10})
    summary = summarize(record)
    assert summary["base_training_days"] is None
    assert summary["base_manpower"] == 1000
    assert summary["unknowns"][0]["field"] == "training_time"


@pytest.mark.parametrize(
    "kind", ["missing", "declarations", "blocks", "duplicate", "unresolved", "scalar", "id"]
)
def test_incomplete_equipment_requirements_remain_unknown(kind):
    record = unit()
    block = record["need"][0]
    if kind == "missing":
        record["need"] = []
    elif kind == "declarations":
        del block["declarations"]
    elif kind == "blocks":
        record["need"].append(deepcopy(block))
    elif kind == "duplicate":
        block["declarations"].append(deepcopy(block["declarations"][0]))
    elif kind == "unresolved":
        block["unresolved_statements"].append({"field": "infantry_equipment", "line": 7})
    else:
        block["declarations"][0]["value" if kind == "scalar" else "field"] = "@unknown"
    summary = summarize(record)
    assert summary["base_equipment"] is None
    assert summary["base_manpower"] == 1000 and summary["base_training_days"] == 90
    assert summary["unknowns"][0]["field"] == "need"


def test_one_unknown_contributor_invalidates_aggregate_but_retains_individual_evidence():
    summary = summarize(unit(), composition=template("infantry", support=("missing",)))
    assert summary["base_equipment"] is None and summary["base_manpower"] is None
    assert summary["units"][0]["base_equipment"] == {"infantry_equipment": 100}
    assert summary["units"][1]["base_equipment"] is None


@pytest.mark.parametrize("kind", ["empty", "missing_group", "conditional", "nonliteral"])
def test_unknown_composition_is_not_a_zero_cost_template(kind):
    composition = template("infantry")
    if kind == "empty":
        composition["regiments"] = []
    elif kind == "missing_group":
        composition.pop("support")
    elif kind == "conditional":
        composition["unresolved_statements"] = [{"field": "if", "line": 30}]
    else:
        composition["regiments"][0]["unit"] = "@unit"
    summary = summarize(unit(), composition=composition)
    assert all(
        summary[field] is None
        for field in ("base_equipment", "base_manpower", "base_training_days")
    )
    assert summary["unknowns"] and not summary["base_requirements_complete"]


def test_explicit_zero_declarations_are_distinct_from_missing_fields():
    summary = summarize(unit(manpower=0, training=0, need={}))
    assert summary["base_equipment"] == {}
    assert summary["base_manpower"] == summary["base_training_days"] == 0
    assert summary["base_requirements_complete"]


def test_summary_is_caller_owned_including_sources_declarations_and_composition():
    record, composition = unit(), template("infantry")
    original = deepcopy((record, composition))
    summary = summarize(record, composition=composition)
    definition = summary["units"][0]["definitions"][0]
    assert definition["source"]["path"] == "common/units/infantry.txt"
    assert definition["need"][0]["declarations"][0]["line"] == 6
    definition["source"]["sha256"] = "changed"
    definition["declarations"][0]["value"] = 1
    summary["units"][0]["occurrences"][0]["line"] = 99
    summary["template"]["regiments"][0]["unit"] = "changed"
    assert (record, composition) == original
    assert summarize(record, composition=composition)["base_manpower"] == 1000


def test_bundled_french_template_uses_100_rifles_per_infantry_battalion():
    country = load_reference_country("FRA")
    oob = next(
        row for row in country["oob_candidates"] if row["source"]["path"].endswith("FRA_1936.txt")
    )
    composition = next(row for row in oob["templates"] if row["name"] == "Division d'Infanterie")
    summary = summarize_template_requirements(composition, load_reference_equipment())
    assert summary["unit_counts"] == {"infantry": 9, "artillery": 1, "engineer": 1}
    assert summary["base_equipment"] == {
        "infantry_equipment": 910,
        "artillery_equipment": 12,
        "support_equipment": 30,
    }
    assert summary["base_manpower"] == 9600 and summary["base_training_days"] == 120
    assert summary["base_requirements_complete"] and summary["source_revision"]
