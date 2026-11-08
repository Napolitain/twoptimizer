"""Review the canonical hourly input contract without executing game mechanics."""

from hashlib import sha256
from pathlib import Path

from games.hoi4.planning.contracts import PlanningContract
from twoptimizer.errors import ApplicationError

PLAN_REVIEW_SCOPE = (
    "Structurally valid input only. Feasibility has not been checked; this is not a runnable "
    "gameplay model. Equipment and template IDs, schedule legality and effects are unresolved."
)


def inspect_planning_file(path: Path | str) -> dict:
    """Delegate every input rule to PlanningContract; preserve supplied choices exactly."""
    path = Path(path)
    try:
        raw = path.read_bytes()
        contract = PlanningContract.from_json(raw.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise ApplicationError(
            f"Cannot review HoI4 planning input {path}: {error}", code="planning_input"
        ) from error
    return {
        "schema_version": 1,
        "game": "hoi4",
        "kind": "planning_input_review",
        "structurally_valid": True,
        "feasibility_checked": False,
        "scenario_ready": False,
        "scope": PLAN_REVIEW_SCOPE,
        "source": {"path": str(path), "sha256": sha256(raw).hexdigest()},
        "summary": {
            "country_tag": contract.country_tag,
            "hours": contract.horizon.hours,
            "division_templates": len(contract.division_templates),
            "equipment_targets": len(contract.equipment_targets),
            "division_targets": len(contract.division_targets),
            "supplied_decisions": len(contract.decisions),
        },
        "contract": contract.to_dict(),
    }


def format_planning_review(report: dict) -> str:
    contract, summary = report["contract"], report["summary"]
    ruleset, horizon = contract["ruleset"], contract["horizon"]
    lines = [
        "HOI4 PLANNING INPUT REVIEW",
        report["scope"],
        f"Country: {contract['country_tag']}",
        f"Requested ruleset: {ruleset['game_version']} / {ruleset['checksum']} / "
        f"{ruleset['dlc_profile']}",
        f"Horizon: {horizon['start']} → {horizon['deadline']} · "
        f"{summary['hours']} hours · {horizon['calendar']}",
        f"Input: {report['source']['path']}\nSHA-256 {report['source']['sha256']}",
        "",
        f"Equipment targets ({summary['equipment_targets']}):",
        *(
            f"  {target['deadline']}: {target['quantity']} x {target['equipment_id']} "
            f"(accounting: {target['accounting']})"
            for target in contract["equipment_targets"]
        ),
        f"Division targets ({summary['division_targets']}; fully equipped and trained):",
        *(
            f"  {target['deadline']}: {target['count']} x {target['template_id']}"
            for target in contract["division_targets"]
        ),
        f"Declared templates: {summary['division_templates']}",
        f"Supplied research/focus/law schedule ({summary['supplied_decisions']} decisions):",
        *(
            f"  {decision['at']}: {decision['kind']} {decision['identifier']} {decision['phase']}"
            for decision in contract["decisions"]
        ),
    ]
    return "\n".join(lines)
