"""Source references are checked without inventing inheritance or DLC behavior."""

from copy import deepcopy

from games.hoi4.data_pipeline.dependencies import build_dependency_report, trace_equipment_field


def _definition(identifier, **declarations):
    return {
        "id": identifier,
        "source": {"path": "source.txt", "sha256": "a" * 64},
        "line": 1,
        "declarations": [
            {"field": field, "value": value, "line": index}
            for index, (field, value) in enumerate(declarations.items(), start=2)
        ],
    }


def test_parent_archetype_and_generated_archetype_relations_stay_distinct():
    data = {
        "equipment": [
            _definition("base", build_cost_ic=2),
            _definition("older", archetype="base", build_cost_ic=3),
            _definition("current", parent="older", archetype="generated"),
        ],
        "duplicate_archetypes": [_definition("generated", archetype="base")],
    }
    before = deepcopy(data)
    report = build_dependency_report(data, include_graph=True)
    assert report["reference_issues"] == []
    edges = report["graph"]["edges"]
    assert {(row["from"], row["relation"], row["to"]) for row in edges} == {
        ("equipment:older", "archetype", "equipment:base"),
        ("equipment:current", "parent", "equipment:older"),
        ("equipment:current", "archetype", "equipment:generated"),
        ("equipment:generated", "duplicates_archetype", "equipment:base"),
    }
    trace = trace_equipment_field(data, "current", "build_cost_ic")
    assert trace["selection"] == "not_evaluated"
    assert {row["declaration"]["value"] for row in trace["candidates"]} == {2, 3}
    assert trace["unresolved"] == []
    assert data == before
    assert report["runnable_scenario_established"] is False
    assert report["unevaluated_mechanics"]


def test_missing_ambiguous_and_nonliteral_references_do_not_fall_back():
    data = {
        "equipment": [
            _definition("base", build_cost_ic=2),
            _definition("base", build_cost_ic=3),
            _definition("child", parent="missing", archetype="base"),
            _definition("dynamic", archetype="@variable"),
        ]
    }
    report = build_dependency_report(data)
    assert report["counts"]["reference_issues"] == {
        "missing_reference": 1,
        "ambiguous_reference": 1,
        "nonliteral_reference": 1,
    }
    assert report["duplicate_definitions"][0]["node"] == "equipment:base"
    assert len(report["duplicate_definitions"][0]["occurrences"]) == 2
    assert "graph" not in report
    trace = trace_equipment_field(data, "child", "build_cost_ic")
    assert trace["candidates"] == []
    assert {item["reason"] for item in trace["unresolved"]} == {"missing", "ambiguous"}


def test_cycle_diagnostics_and_field_traversal_terminate():
    data = {
        "equipment": [
            _definition("first", parent="second", build_cost_ic=1),
            _definition("second", parent="first"),
        ]
    }
    report = build_dependency_report(data)
    assert report["cycles"] == [["equipment:first", "equipment:second", "equipment:first"]]
    assert report["counts"]["cycles"] == 1
    assert len(trace_equipment_field(data, "second", "build_cost_ic")["candidates"]) == 1


def test_unit_template_and_production_references_retain_their_source_context():
    unit = {
        **_definition("infantry", manpower=1000, training_time=90),
        "need": [{"declarations": [{"field": "rifles", "value": 100, "line": 10}]}],
    }
    data = {"equipment": [_definition("rifles")], "units": [unit]}
    country = {
        "tag": "FRA",
        "oob_candidates": [
            {
                "source": {"path": "history/units/FRA_1936.txt", "sha256": "b" * 64},
                "branch_selected": False,
                "parse_diagnostics": [{"status": "incomplete", "line": 40}],
                "templates": [
                    {
                        "name": "Division",
                        "line": 12,
                        "regiments": [
                            {"unit": "infantry", "line": 13},
                            {"unit": "unknown", "line": 14},
                        ],
                    }
                ],
                "production_lines": [
                    {
                        "line": 20,
                        "equipment_blocks": [
                            {"declarations": [{"field": "type", "value": "rifles", "line": 21}]}
                        ],
                    }
                ],
            }
        ],
    }
    report = build_dependency_report(data, [country], include_graph=True)
    (issue,) = report["reference_issues"]
    assert issue["status"] == "missing_reference"
    assert issue["to"] == "unit:unknown"
    assert issue["line"] == 14
    assert issue["source"]["sha256"] == "b" * 64
    assert report["source_diagnostics"] == [{"country": "FRA", "status": "incomplete", "line": 40}]
    assert report["counts"]["by_kind"] == {
        "equipment": 1,
        "units": 1,
        "template": 1,
        "production": 1,
    }
    needs = next(edge for edge in report["graph"]["edges"] if edge["relation"] == "needs_equipment")
    assert needs["declared_amount"] == 100
    assert country["oob_candidates"][0]["branch_selected"] is False


def test_empty_or_unknown_dependency_inputs_never_establish_a_scenario():
    report = build_dependency_report({})
    assert report["counts"]["nodes"] == 0
    assert report["reference_issues"] == []
    assert report["runnable_scenario_established"] is False
    assert trace_equipment_field({}, "unknown", "build_cost_ic")["unresolved"] == [
        {"node": "equipment:unknown", "reason": "missing"}
    ]
