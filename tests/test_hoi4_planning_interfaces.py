"""Planning-file inspection delegates validation and never implies solvability."""

import json
from hashlib import sha256

import pytest

from games.hoi4.planning.contracts import PlanningContract
from twoptimizer.__main__ import main
from twoptimizer.hoi4_planning import inspect_planning_file


@pytest.fixture
def planning_input():
    return {
        "schema_version": 1,
        "ruleset": {
            "game_version": "1.19.4",
            "checksum": "0bdb",
            "dlc_profile": "all_gameplay",
        },
        "country_tag": "FRA",
        "horizon": {
            "calendar": "hoi4_no_leap",
            "start": "1936.1.1.12",
            "deadline": "1936.1.3.12",
        },
        "division_templates": [
            {
                "template_id": "explicit_infantry",
                "battalions": [{"unit_id": "infantry", "row": 0, "column": 0}],
                "support": [],
            }
        ],
        "equipment_targets": [
            {
                "equipment_id": "infantry_equipment_1",
                "quantity": 100,
                "deadline": "1936.1.2.12",
                "accounting": "reserve",
            }
        ],
        "division_targets": [
            {"template_id": "explicit_infantry", "count": 2, "deadline": "1936.1.3.12"}
        ],
        "decisions": [
            {
                "at": "1936.1.1.12",
                "kind": "research",
                "identifier": "supplied_technology",
                "phase": "started",
            },
            {
                "at": "1936.1.2.12",
                "kind": "law",
                "identifier": "supplied_law",
                "phase": "enacted",
            },
        ],
    }


def test_plan_check_reports_structural_scope_and_preserves_input(planning_input, tmp_path, capsys):
    path, output = tmp_path / "input.json", tmp_path / "review.json"
    original = json.dumps(planning_input).encode()
    path.write_bytes(original)
    assert main(["hoi4", "plan-check", str(path), "--output", str(output)]) == 0
    text = capsys.readouterr().out
    assert "Structurally valid input only" in text
    assert "Feasibility has not been checked" in text
    assert "not a runnable gameplay model" in text
    assert "Country: FRA" in text and "48 hours" in text
    assert "100 x infantry_equipment_1 (accounting: reserve)" in text
    assert "2 x explicit_infantry" in text and "fully equipped and trained" in text
    assert "research supplied_technology started" in text and "law supplied_law enacted" in text
    report = json.loads(output.read_text())
    assert report["contract"] == PlanningContract.from_json(original.decode()).to_dict()
    assert report["source"]["sha256"] == sha256(original).hexdigest()
    assert report["structurally_valid"] is True
    assert report["scenario_ready"] is report["feasibility_checked"] is False
    assert path.read_bytes() == original
    assert main(["hoi4", "plan-check", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report


def test_plan_check_does_not_invent_targets_or_decisions(planning_input, tmp_path):
    for field in ("division_templates", "equipment_targets", "division_targets", "decisions"):
        planning_input[field] = []
    path = tmp_path / "input.json"
    path.write_text(json.dumps(planning_input))
    report = inspect_planning_file(path)
    assert report["summary"] == {
        "country_tag": "FRA",
        "hours": 48,
        "division_templates": 0,
        "equipment_targets": 0,
        "division_targets": 0,
        "supplied_decisions": 0,
    }


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("extra_field", True, "unknown=['extra_field']"),
        ("country_tag", "fra", "uppercase game tag"),
        ("schema_version", True, "nonnegative whole number"),
        ("decisions", [{"at": "1936.1.1.12"}], "missing="),
        ("equipment_targets", [{"equipment_id": "infantry"}], "missing="),
        (
            "division_targets",
            [{"template_id": "missing", "count": 1, "deadline": "1936.1.2.0"}],
            "undeclared template",
        ),
    ],
)
def test_plan_check_surfaces_contract_rejections(
    planning_input, tmp_path, capsys, field, replacement, message
):
    planning_input[field] = replacement
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(planning_input))
    assert main(["hoi4", "plan-check", str(path)]) == 2
    captured = capsys.readouterr()
    assert message in captured.err
    assert not captured.out


@pytest.mark.parametrize("payload", [b'{"country_tag":"FRA","country_tag":"GER"}', b"{", b"\xff"])
def test_plan_check_rejects_duplicate_fields_malformed_json_and_encoding(tmp_path, capsys, payload):
    path = tmp_path / "invalid.json"
    path.write_bytes(payload)
    assert main(["hoi4", "plan-check", str(path)]) == 2
    assert "Cannot review HoI4 planning input" in capsys.readouterr().err


def test_plan_check_file_failures_and_same_path_output(planning_input, tmp_path, capsys):
    path = tmp_path / "input.json"
    assert main(["hoi4", "plan-check", str(path)]) == 2
    assert "Cannot review HoI4 planning input" in capsys.readouterr().err
    original = json.dumps(planning_input)
    path.write_text(original)
    assert main(["hoi4", "plan-check", str(path), "--output", str(path)]) == 2
    assert "must differ from the input path" in capsys.readouterr().err
    assert path.read_text() == original
    assert main(["hoi4", "plan-check", str(path), "--output", str(tmp_path)]) == 2
    assert "Cannot save HoI4 planning report" in capsys.readouterr().err


def test_plan_check_help_describes_scope(capsys):
    assert main(["--help"]) == 0
    assert "hoi4 plan-check" in capsys.readouterr().out
    with pytest.raises(SystemExit) as result:
        main(["hoi4", "plan-check", "--help"])
    assert result.value.code == 0
    assert "--output" in capsys.readouterr().out
