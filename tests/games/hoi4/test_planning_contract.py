"""Planning inputs are immutable, explicit and structurally checked without physics."""

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from games.hoi4.planning import CampaignDate, HourlyHorizon
from games.hoi4.planning.contracts import (
    DatedDecision,
    DecisionKind,
    DecisionPhase,
    DivisionDeadline,
    DivisionTemplate,
    EquipmentAccounting,
    EquipmentDeadline,
    PlanningContract,
    RulesetTarget,
    UnitPlacement,
)


@pytest.fixture
def contract():
    start = CampaignDate(1936, 1, 1)
    deadline = start.add_hours(48)
    return PlanningContract(
        ruleset=RulesetTarget("1.19.4", "0bdb", "all_gameplay"),
        country_tag="TST",
        horizon=HourlyHorizon(start, deadline),
        division_templates=(
            DivisionTemplate("test_infantry", (UnitPlacement("infantry", 0, 0),)),
            DivisionTemplate("external", source_template_id="source_template"),
        ),
        equipment_targets=(
            EquipmentDeadline("infantry_equipment", 0, start, EquipmentAccounting.RESERVE),
            EquipmentDeadline("infantry_equipment", 100, deadline, EquipmentAccounting.RESERVE),
        ),
        division_targets=(DivisionDeadline("test_infantry", 1, deadline),),
        decisions=(
            DatedDecision(start, DecisionKind.RESEARCH, "tech", DecisionPhase.STARTED),
            DatedDecision(deadline, DecisionKind.RESEARCH, "tech", DecisionPhase.COMPLETED),
            DatedDecision(start, DecisionKind.LAW, "law", DecisionPhase.ENACTED),
        ),
    )


def test_contract_round_trip_preserves_canonical_dates_and_explicit_inputs(contract):
    payload = contract.to_json()
    assert PlanningContract.from_json(payload) == contract
    assert PlanningContract.from_dict(contract.to_dict()).to_json() == payload
    assert payload == json.dumps(
        contract.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert contract.horizon.hours == 48
    assert contract.to_dict()["equipment_targets"][0]["deadline"] == "1936.01.01.00"
    assert contract.equipment_targets[1].accounting == EquipmentAccounting.RESERVE


def test_contract_has_no_implicit_scenario_or_deadlines(contract):
    empty = PlanningContract(contract.ruleset, "TST", contract.horizon)
    assert empty.equipment_targets == empty.division_targets == empty.decisions == ()
    assert not hasattr(empty, "initial_state")


def test_contract_freezes_caller_collections_and_returns_defensive_serialization(contract):
    templates = list(contract.division_templates)
    copied = replace(contract, division_templates=templates)
    templates.clear()
    assert copied == contract and isinstance(copied.division_templates, tuple)
    exported = copied.to_dict()
    exported["division_templates"][0]["battalions"][0]["unit_id"] = "changed"
    assert copied.division_templates[0].battalions[0].unit_id == "infantry"
    for instance, attribute in (
        (copied, "country_tag"),
        (copied.division_templates[0], "template_id"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(instance, attribute, "changed")


@pytest.mark.parametrize("value", [True, False, 1.5, "1", -1, None])
def test_counts_and_positions_reject_implicit_coercion(contract, value):
    with pytest.raises(ValueError, match="whole number"):
        EquipmentDeadline(
            "equipment", value, contract.horizon.deadline, EquipmentAccounting.RESERVE
        )
    with pytest.raises(ValueError, match="whole number"):
        DivisionDeadline("template", value, contract.horizon.deadline)
    with pytest.raises(ValueError, match="whole number"):
        UnitPlacement("unit", value, 0)
    with pytest.raises(ValueError, match="whole number"):
        UnitPlacement("unit", 0, value)


@pytest.mark.parametrize("value", [None, "", " x", "x ", "x\n", 123])
def test_references_require_explicit_nonempty_text(value):
    with pytest.raises(ValueError, match="nonempty text"):
        UnitPlacement(value, 0, 0)


def test_templates_use_composition_or_reference_and_do_not_invent_grid_limits():
    unit = UnitPlacement("unresolved_unit", 100, 100)
    template = replace(DivisionTemplate("composition", (unit,)), battalions=[unit], support=[unit])
    assert template.battalions == template.support == (unit,)
    external = DivisionTemplate("reference", source_template_id="unresolved_source")
    assert DivisionTemplate.from_dict(external.to_dict()) == external
    with pytest.raises(ValueError, match="exclusively"):
        DivisionTemplate("empty")
    with pytest.raises(ValueError, match="exclusively"):
        DivisionTemplate("both", (unit,), source_template_id="source")
    with pytest.raises(ValueError, match="Duplicate battalions positions"):
        DivisionTemplate("collision", (unit, UnitPlacement("other", 100, 100)))
    with pytest.raises(ValueError, match="Duplicate support positions"):
        DivisionTemplate("collision", support=(unit, unit))


@pytest.mark.parametrize("accounting", list(EquipmentAccounting))
def test_equipment_accounting_is_explicit_and_round_trips(contract, accounting):
    target = replace(contract.equipment_targets[0], accounting=accounting)
    assert EquipmentDeadline.from_dict(target.to_dict()).accounting == accounting
    values = target.to_dict()
    del values["accounting"]
    with pytest.raises(ValueError, match="missing"):
        EquipmentDeadline.from_dict(values)


@pytest.mark.parametrize("accounting", ["automatic", None, True, 1])
def test_invalid_accounting_is_not_guessed(contract, accounting):
    with pytest.raises(ValueError, match="EquipmentAccounting"):
        replace(contract.equipment_targets[0], accounting=accounting)


def test_multiple_target_dates_allow_start_and_final_boundaries_without_extra_hours(contract):
    assert contract.equipment_targets[0].deadline == contract.horizon.start
    assert contract.equipment_targets[1].deadline == contract.horizon.deadline
    assert contract.horizon.hours not in contract.horizon.offsets()
    zero = replace(
        contract,
        horizon=HourlyHorizon(contract.horizon.start, contract.horizon.start),
        equipment_targets=contract.equipment_targets[:1],
        division_targets=(),
        decisions=(),
    )
    assert zero.horizon.hours == 0 and len(zero.equipment_targets) == 1


@pytest.mark.parametrize("offset", [-1, 49])
def test_all_dated_inputs_must_be_within_contract_boundaries(contract, offset):
    outside = contract.horizon.start.add_hours(offset)
    with pytest.raises(ValueError, match="boundaries"):
        replace(
            contract, equipment_targets=(replace(contract.equipment_targets[0], deadline=outside),)
        )
    with pytest.raises(ValueError, match="boundaries"):
        replace(
            contract, division_targets=(replace(contract.division_targets[0], deadline=outside),)
        )
    with pytest.raises(ValueError, match="boundaries"):
        replace(contract, decisions=(replace(contract.decisions[0], at=outside),))


@pytest.mark.parametrize(
    "field", ["division_templates", "equipment_targets", "division_targets", "decisions"]
)
def test_duplicate_entities_at_the_same_deadline_are_rejected(contract, field):
    item = getattr(contract, field)[0]
    with pytest.raises(ValueError, match="Duplicate"):
        replace(contract, **{field: (item, item)})


def test_conflicting_accounting_for_same_equipment_and_date_is_rejected(contract):
    target = contract.equipment_targets[0]
    with pytest.raises(ValueError, match="Duplicate equipment deadlines"):
        replace(
            contract,
            equipment_targets=(
                target,
                replace(target, accounting=EquipmentAccounting.INCLUDING_ISSUED),
            ),
        )


def test_division_target_requires_declared_template(contract):
    with pytest.raises(ValueError, match="undeclared template"):
        replace(
            contract,
            division_targets=(replace(contract.division_targets[0], template_id="unknown"),),
        )


@pytest.mark.parametrize(
    ("kind", "phase"),
    [
        (DecisionKind.RESEARCH, DecisionPhase.ENACTED),
        (DecisionKind.FOCUS, DecisionPhase.ENACTED),
        (DecisionKind.LAW, DecisionPhase.STARTED),
        (DecisionKind.LAW, DecisionPhase.COMPLETED),
    ],
)
def test_decision_phase_cannot_silently_change_meaning(contract, kind, phase):
    with pytest.raises(ValueError, match="phase"):
        DatedDecision(contract.horizon.start, kind, "id", phase)


def test_explicit_phases_do_not_infer_duration_effects_or_simultaneous_order(contract):
    finish = DatedDecision(
        contract.horizon.start, DecisionKind.FOCUS, "focus", DecisionPhase.COMPLETED
    )
    same_hour = replace(contract, decisions=(finish, contract.decisions[0]))
    assert PlanningContract.from_json(same_hour.to_json()).decisions == same_hour.decisions
    values = finish.to_dict()
    del values["phase"]
    with pytest.raises(ValueError, match="missing"):
        DatedDecision.from_dict(values)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "ruleset",
        "country_tag",
        "horizon",
        "division_templates",
        "equipment_targets",
        "division_targets",
        "decisions",
    ],
)
def test_serialized_contract_requires_every_top_level_field(contract, field):
    values = contract.to_dict()
    del values[field]
    with pytest.raises(ValueError, match="missing"):
        PlanningContract.from_dict(values)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("ruleset",),
        ("horizon",),
        ("division_templates", 0),
        ("division_templates", 0, "battalions", 0),
        ("equipment_targets", 0),
        ("division_targets", 0),
        ("decisions", 0),
    ],
)
def test_unknown_fields_are_rejected_at_every_level(contract, path):
    values = contract.to_dict()
    target = values
    for key in path:
        target = target[key]
    target["unexpected"] = 1
    with pytest.raises(ValueError):
        PlanningContract.from_dict(values)


@pytest.mark.parametrize(
    "field", ["division_templates", "equipment_targets", "division_targets", "decisions"]
)
def test_unordered_or_untyped_collections_are_rejected(contract, field):
    with pytest.raises(ValueError, match="ordered lists"):
        replace(contract, **{field: set()})
    with pytest.raises(ValueError, match="records"):
        replace(contract, **{field: [object()]})


@pytest.mark.parametrize("value", [True, 0, 2, "1", 1.0])
def test_schema_version_must_be_supported_integer(contract, value):
    with pytest.raises(ValueError):
        replace(contract, schema_version=value)


@pytest.mark.parametrize("field", ["game_version", "checksum", "dlc_profile"])
def test_ruleset_selection_cannot_silently_drift(contract, field):
    with pytest.raises(ValueError, match="selected target"):
        replace(contract.ruleset, **{field: "unknown"})


@pytest.mark.parametrize("tag", ["France", "fra", "FR", "FRA\n", None, True])
def test_country_tag_syntax_is_explicit(contract, tag):
    with pytest.raises(ValueError, match="Country tag"):
        replace(contract, country_tag=tag)


@pytest.mark.parametrize(
    "payload",
    [
        '{"schema_version":1,"schema_version":1}',
        '{"ruleset":{"checksum":"0bdb","checksum":"0bdb"}}',
    ],
)
def test_duplicate_json_object_fields_are_rejected(payload):
    with pytest.raises(ValueError, match="Duplicate JSON field"):
        PlanningContract.from_json(payload)


@pytest.mark.parametrize("value", [None, [], "text", {1: "x", "x": "y"}])
def test_non_record_input_is_rejected_cleanly(value):
    with pytest.raises(ValueError):
        PlanningContract.from_dict(value)


@pytest.mark.parametrize("value", [b"{}", None, {}])
def test_json_input_must_be_text(value):
    with pytest.raises(ValueError, match="JSON must be text"):
        PlanningContract.from_json(value)
