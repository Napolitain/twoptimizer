"""Objective units, priorities and proof status survive shared application boundaries."""

import csv
import json
from dataclasses import replace

import pytest

from tests.support.ui import result as legacy_result
from twoptimizer.export import export_session
from twoptimizer.models import CaseResult, EngineResult, ObjectiveSummary, SolverSummary
from twoptimizer.presentation import objective_summary, primary_metric
from twoptimizer.requests import default_config
from twoptimizer.runner import _decode_result
from twoptimizer.service import solve_case
from twoptimizer.session import RunSession


def objective(**changes):
    fields = {
        "identifier": "capacity",
        "label": "Civilian capacity",
        "unit": "capacity units",
        "sense": "maximize",
        "value": 10,
        "bound": 10,
        "status": "OPTIMAL",
    }
    return ObjectiveSummary.from_dict(fields | changes)


def secondary(**changes):
    return objective(
        **(
            {
                "identifier": "early_spending",
                "label": "Early military spending",
                "unit": "spending units",
                "sense": "minimize",
                "value": 100,
                "bound": 80,
                "status": "FEASIBLE",
            }
            | changes
        )
    )


def case(*objectives, status="FEASIBLE"):
    payload = legacy_result()
    payload["timings"] = {}
    original = CaseResult.from_dict(payload)
    return replace(
        original,
        solver=SolverSummary("cp-sat", status, 0, 100, 80),
        income=None,
        buildings=[],
        objectives=objectives,
        source_files={"model": "same-source"},
    )


def test_total_war_default_json_and_worker_roundtrip_are_unchanged():
    payload = legacy_result()
    payload["timings"] = {}
    parsed = CaseResult.from_dict(payload)
    assert parsed.objectives == () and "objectives" not in parsed.to_dict()
    assert parsed.to_dict() == payload == _decode_result(payload)
    assert primary_metric(payload)["value"] == payload["income"]
    assert primary_metric(payload)["label"] == "Income"


def test_ordered_objectives_roundtrip_without_faking_income_or_buildings():
    result = case(objective(), secondary())
    payload = json.loads(json.dumps(result.to_dict(), allow_nan=False))
    assert _decode_result(payload) == payload
    assert CaseResult.from_dict(payload) == result
    assert payload["income"] is None and payload["buildings"] == []
    assert [item["identifier"] for item in payload["objectives"]] == [
        "capacity",
        "early_spending",
    ]
    records = [objective()]
    engine = replace(EngineResult({}, None, [], {}), objectives=records)
    records.append(secondary())
    assert engine.objectives == (objective(),)


@pytest.mark.parametrize(
    "changes",
    [
        {"identifier": ""},
        {"label": " "},
        {"unit": 3},
        {"sense": "weighted"},
        {"sense": []},
        {"value": float("nan")},
        {"value": True},
        {"bound": float("inf")},
        {"bound": "10"},
        {"bound": 9},
        {"sense": "minimize", "bound": 11},
        {"status": ""},
    ],
)
def test_malformed_or_inconsistent_objective_metadata_is_rejected(changes):
    with pytest.raises(ValueError):
        objective(**changes)


def test_duplicate_ids_and_unordered_objectives_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        case(objective(), objective(label="Different presentation"))
    with pytest.raises(ValueError, match="ordered sequence"):
        replace(EngineResult({}, None, [], {}), objectives={objective()})
    payload = case(objective()).to_dict()
    payload["objectives"] = {"capacity": objective().to_dict()}
    with pytest.raises(RuntimeError, match="invalid result"):
        _decode_result(payload)


def test_optimal_case_cannot_hide_an_unfinished_secondary_stage():
    with pytest.raises(ValueError, match="every objective"):
        case(objective(), secondary(), status="OPTIMAL")
    with pytest.raises(ValueError, match="earlier priorities"):
        case(objective(status="FEASIBLE", bound=12), secondary(bound=100, status="OPTIMAL"))
    with pytest.raises(ValueError, match="matching bound"):
        objective(value=10, bound=12, status="OPTIMAL")


def test_optional_status_inherits_solver_status_without_inventing_a_proof():
    result = case(objective(status=None, bound=12))
    payload = result.to_dict()
    assert "status" not in payload["objectives"][0]
    assert primary_metric(payload)["status"] == "FEASIBLE"
    with pytest.raises(ValueError, match="matching bound"):
        replace(result, solver=replace(result.solver, status="OPTIMAL"))


@pytest.mark.parametrize("status", ["OPTIMAL", "FEASIBLE", "UNKNOWN"])
def test_infeasible_case_rejects_existing_objective_values_at_worker_boundary(status):
    payload = case(objective(status=status)).to_dict()
    payload["solver"]["status"] = "INFEASIBLE"
    with pytest.raises(RuntimeError, match="invalid result"):
        _decode_result(payload)


def test_infeasible_stage_cannot_coexist_with_feasibility_or_its_own_value():
    with pytest.raises(ValueError, match="infeasible objective"):
        objective(status="INFEASIBLE")
    failed = objective(status="INFEASIBLE", value=None, bound=None)
    for status in ("FEASIBLE", "OPTIMAL", "UNBOUNDED"):
        with pytest.raises(ValueError, match="infeasible case or stage"):
            case(failed, status=status)
    payload = case(failed, status="INFEASIBLE").to_dict()
    assert _decode_result(payload) == payload


@pytest.mark.parametrize("status", ["UNKNOWN", "ERROR", "ABNORMAL", "BACKEND_FAILURE"])
def test_failed_later_stage_preserves_proved_prefix_without_claiming_overall_feasibility(status):
    result = case(objective(), secondary(value=None, bound=None, status=status), status=status)
    payload = result.to_dict()
    assert _decode_result(payload) == payload
    assert payload["solver"]["status"] == status
    assert primary_metric(payload)["status"] == "OPTIMAL"
    session = RunSession()
    session.record(result)
    session.record(case(objective(value=11, bound=11)))


@pytest.mark.parametrize(
    ("sense", "value", "bound", "expected"),
    [("maximize", 10, 20, 50), ("minimize", 20, 10, 50), ("minimize", None, 0, None)],
)
def test_service_gap_uses_primary_objective_direction_and_units(
    monkeypatch, sense, value, bound, expected
):
    item = objective(sense=sense, value=value, bound=bound, status="UNKNOWN")

    def adapter(config, phase, session):
        return EngineResult(
            {"solver": SolverSummary("cp-sat", "UNKNOWN", 0, 999, 1000).to_dict()},
            None,
            [],
            {},
            (item,),
        )

    monkeypatch.setattr("twoptimizer.service.solve_shogun", adapter)
    result = solve_case(default_config("shogun2"))
    assert result.gap_percent == expected and result.objectives == (item,)
    assert result.income is None and result.buildings == []
    assert result.solver.bound == 1000  # Native last-stage telemetry remains intact.
    assert primary_metric(result.to_dict())["bound"] == bound


def test_presentation_and_export_keep_primary_proof_separate_from_case_status(tmp_path):
    result = case(objective(), secondary())
    payload = result.to_dict()
    summary = objective_summary(payload)
    assert "1. Civilian capacity: 10.000 capacity units · maximize · OPTIMAL" in summary
    assert "2. Early military spending: 100.000 spending units · minimize · FEASIBLE" in summary
    path, csv_path = export_session(tmp_path / "objectives", [payload])
    assert json.loads(path.read_text())["cases"][0] == payload
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["income"] == ""
    assert row["objective_value"] == row["objective_bound"] == row["bound"] == "10"
    assert row["objective_status"] == "OPTIMAL" and row["status"] == "FEASIBLE"
    assert row["objective_unit"] == "capacity units"
    assert json.loads(row["objectives"]) == payload["objectives"]


def test_mixed_exports_do_not_invent_objective_metadata_for_legacy_rows(tmp_path):
    first = legacy_result()
    _, path = export_session(tmp_path / "mixed", [first, case(objective()).to_dict()])
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["income"] == "4182.7" and rows[0]["objective_id"] == ""
    assert rows[1]["income"] == "" and rows[1]["objective_id"] == "capacity"


def test_session_checks_proved_prefix_without_comparing_unfinished_secondary():
    session = RunSession()
    first = case(objective(), secondary())
    session.record(first)
    changed_secondary = replace(
        first,
        request=replace(first.request, algorithm="highs", workers=2, seconds=5),
        objectives=(objective(), secondary(value=150, bound=90)),
    )
    session.record(changed_secondary)
    with pytest.raises(RuntimeError, match="proved optimum"):
        session.record(replace(changed_secondary, objectives=(objective(value=11, bound=11),)))


def test_session_checks_later_objectives_only_after_the_prefix_is_proved():
    session = RunSession()
    first = case(objective(), secondary(bound=100, status="OPTIMAL"), status="OPTIMAL")
    session.record(first)
    with pytest.raises(RuntimeError, match="proved optimum"):
        session.record(
            replace(
                first, objectives=(objective(), secondary(value=90, bound=90, status="OPTIMAL"))
            )
        )


@pytest.mark.parametrize(
    "changes",
    [{"identifier": "another_capacity"}, {"unit": "other units"}, {"sense": "minimize"}],
)
def test_session_does_not_compare_incompatible_objective_meanings(changes):
    session = RunSession()
    session.record(case(objective()))
    session.record(case(objective(value=11, bound=11, **changes)))


def test_session_does_not_compare_different_sources_or_scenarios():
    session = RunSession()
    first = case(objective())
    session.record(first)
    different = replace(first, objectives=(objective(value=11, bound=11),))
    session.record(replace(different, source_files={"model": "new-source"}))
    session.record(replace(different, request=replace(first.request, research="public")))


def test_session_does_not_turn_unproved_incumbents_into_optimum_checks():
    session = RunSession()
    session.record(case(objective(value=8, bound=12, status="FEASIBLE")))
    session.record(case(objective(value=9, bound=12, status="FEASIBLE")))
    session.record(case(objective()))
