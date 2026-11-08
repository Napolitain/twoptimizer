"""Validated planning inputs, not an executable economic scenario.

The contract records the user's targets and dated decisions without inventing
production rates, effects, completion times, starting state or schedule legality.
Equipment accounting and decision phases must be explicit.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from games.hoi4.planning.time import CampaignDate, HourlyHorizon

SCHEMA_VERSION = 1
TARGET_VERSION = "1.19.4"
TARGET_CHECKSUM = "0bdb"
TARGET_DLC_PROFILE = "all_gameplay"


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or not value.isprintable():
        raise ValueError(
            f"{label} must be nonempty text without surrounding whitespace or controls"
        )
    return value


def _count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative whole number")
    return value


def _record(value, required, optional=()):
    if not isinstance(value, Mapping):
        raise ValueError("A planning record must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ValueError("Planning field names must be strings")
    missing, unknown = set(required) - value.keys(), value.keys() - set(required) - set(optional)
    if missing or unknown:
        raise ValueError(
            f"Invalid planning fields: missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    return value


def _sequence(value):
    if not isinstance(value, (tuple, list)):
        raise ValueError("Planning collections must be ordered lists")
    return value


def _records[T](value, record_type: type[T]) -> tuple[T, ...]:
    result = tuple(_sequence(value))
    if any(not isinstance(item, record_type) for item in result):
        raise ValueError(f"Expected {record_type.__name__} records")
    return result


def _unique(values, label):
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")


def _choice[T: StrEnum](value: object, kind: type[T]) -> T:
    if not isinstance(value, str):
        raise ValueError(f"Choose an explicit {kind.__name__}")
    try:
        return kind(value)
    except ValueError as error:
        raise ValueError(f"Unknown {kind.__name__}: {value}") from error


class EquipmentAccounting(StrEnum):
    RESERVE = "reserve"
    INCLUDING_ISSUED = "including_issued"


class DecisionKind(StrEnum):
    RESEARCH = "research"
    FOCUS = "focus"
    LAW = "law"


class DecisionPhase(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    ENACTED = "enacted"


@dataclass(frozen=True, slots=True)
class RulesetTarget:
    """The selected version target; this does not certify an imported dataset."""

    game_version: str
    checksum: str
    dlc_profile: str

    def __post_init__(self):
        actual = (self.game_version, self.checksum, self.dlc_profile)
        if actual != (TARGET_VERSION, TARGET_CHECKSUM, TARGET_DLC_PROFILE):
            raise ValueError("The selected target is HoI4 1.19.4 / 0bdb / all_gameplay DLC")

    def to_dict(self):
        return {name: getattr(self, name) for name in ("game_version", "checksum", "dlc_profile")}

    @classmethod
    def from_dict(cls, value):
        return cls(**_record(value, ("game_version", "checksum", "dlc_profile")))


@dataclass(frozen=True, slots=True)
class UnitPlacement:
    """A declared battalion/support position; game grid limits are not inferred."""

    unit_id: str
    row: int
    column: int

    def __post_init__(self):
        _name(self.unit_id, "Unit ID")
        _count(self.row, "Row")
        _count(self.column, "Column")

    def to_dict(self):
        return {"unit_id": self.unit_id, "row": self.row, "column": self.column}

    @classmethod
    def from_dict(cls, value):
        return cls(**_record(value, ("unit_id", "row", "column")))


@dataclass(frozen=True, slots=True)
class DivisionTemplate:
    """Explicit composition or an external template reference, never a fallback."""

    template_id: str
    battalions: tuple[UnitPlacement, ...] = ()
    support: tuple[UnitPlacement, ...] = ()
    source_template_id: str | None = None

    def __post_init__(self):
        _name(self.template_id, "Template ID")
        for name in ("battalions", "support"):
            values = _records(getattr(self, name), UnitPlacement)
            object.__setattr__(self, name, values)
            _unique([(value.row, value.column) for value in values], f"{name} positions")
        if self.source_template_id is not None:
            _name(self.source_template_id, "Source template ID")
        composition = bool(self.battalions or self.support)
        if composition == (self.source_template_id is not None):
            raise ValueError(
                "A template needs either composition or a source reference, exclusively"
            )

    def to_dict(self):
        record = {"template_id": self.template_id}
        if self.source_template_id is not None:
            return {**record, "source_template_id": self.source_template_id}
        return {
            **record,
            "battalions": [item.to_dict() for item in self.battalions],
            "support": [item.to_dict() for item in self.support],
        }

    @classmethod
    def from_dict(cls, value):
        data = _record(value, ("template_id",), ("battalions", "support", "source_template_id"))
        return cls(
            template_id=data["template_id"],
            battalions=tuple(
                UnitPlacement.from_dict(item) for item in _sequence(data.get("battalions", ()))
            ),
            support=tuple(
                UnitPlacement.from_dict(item) for item in _sequence(data.get("support", ()))
            ),
            source_template_id=data.get("source_template_id"),
        )


@dataclass(frozen=True, slots=True)
class EquipmentDeadline:
    equipment_id: str
    quantity: int
    deadline: CampaignDate
    accounting: EquipmentAccounting

    def __post_init__(self):
        _name(self.equipment_id, "Equipment ID")
        _count(self.quantity, "Equipment quantity")
        if not isinstance(self.deadline, CampaignDate):
            raise ValueError("Equipment deadline must use CampaignDate")
        object.__setattr__(self, "accounting", _choice(self.accounting, EquipmentAccounting))

    def to_dict(self):
        return {
            "equipment_id": self.equipment_id,
            "quantity": self.quantity,
            "deadline": str(self.deadline),
            "accounting": self.accounting.value,
        }

    @classmethod
    def from_dict(cls, value):
        data = _record(value, ("equipment_id", "quantity", "deadline", "accounting"))
        return cls(
            data["equipment_id"],
            data["quantity"],
            CampaignDate.parse(data["deadline"]),
            _choice(data["accounting"], EquipmentAccounting),
        )


@dataclass(frozen=True, slots=True)
class DivisionDeadline:
    template_id: str
    count: int
    deadline: CampaignDate

    def __post_init__(self):
        _name(self.template_id, "Template ID")
        _count(self.count, "Division count")
        if not isinstance(self.deadline, CampaignDate):
            raise ValueError("Division deadline must use CampaignDate")

    def to_dict(self):
        return {
            "template_id": self.template_id,
            "count": self.count,
            "deadline": str(self.deadline),
        }

    @classmethod
    def from_dict(cls, value):
        data = _record(value, ("template_id", "count", "deadline"))
        return cls(data["template_id"], data["count"], CampaignDate.parse(data["deadline"]))


@dataclass(frozen=True, slots=True)
class DatedDecision:
    at: CampaignDate
    kind: DecisionKind
    identifier: str
    phase: DecisionPhase

    def __post_init__(self):
        if not isinstance(self.at, CampaignDate):
            raise ValueError("Decision time must use CampaignDate")
        _name(self.identifier, "Decision ID")
        object.__setattr__(self, "kind", _choice(self.kind, DecisionKind))
        object.__setattr__(self, "phase", _choice(self.phase, DecisionPhase))
        allowed = (
            {DecisionPhase.ENACTED}
            if self.kind == DecisionKind.LAW
            else {DecisionPhase.STARTED, DecisionPhase.COMPLETED}
        )
        if self.phase not in allowed:
            raise ValueError("Research/focus phases are started/completed; law phase is enacted")

    def to_dict(self):
        return {
            "at": str(self.at),
            "kind": self.kind.value,
            "identifier": self.identifier,
            "phase": self.phase.value,
        }

    @classmethod
    def from_dict(cls, value):
        data = _record(value, ("at", "kind", "identifier", "phase"))
        return cls(
            CampaignDate.parse(data["at"]),
            _choice(data["kind"], DecisionKind),
            data["identifier"],
            _choice(data["phase"], DecisionPhase),
        )


@dataclass(frozen=True, slots=True)
class PlanningContract:
    """Structural inputs only: validation never certifies a runnable campaign."""

    ruleset: RulesetTarget
    country_tag: str
    horizon: HourlyHorizon
    division_templates: tuple[DivisionTemplate, ...] = ()
    equipment_targets: tuple[EquipmentDeadline, ...] = ()
    division_targets: tuple[DivisionDeadline, ...] = ()
    decisions: tuple[DatedDecision, ...] = ()
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if _count(self.schema_version, "Schema version") != SCHEMA_VERSION:
            raise ValueError("Unsupported planning schema version")
        if not isinstance(self.ruleset, RulesetTarget) or not isinstance(
            self.horizon, HourlyHorizon
        ):
            raise ValueError("Planning inputs require RulesetTarget and HourlyHorizon")
        if (
            not isinstance(self.country_tag, str)
            or re.fullmatch(r"[A-Z][A-Z0-9]{2}", self.country_tag) is None
        ):
            raise ValueError("Country tag must be a three-character uppercase game tag")
        for name, record_type in (
            ("division_templates", DivisionTemplate),
            ("equipment_targets", EquipmentDeadline),
            ("division_targets", DivisionDeadline),
            ("decisions", DatedDecision),
        ):
            object.__setattr__(self, name, _records(getattr(self, name), record_type))
        self._validate_targets()
        self._validate_decisions()

    def _validate_targets(self):
        templates = [item.template_id for item in self.division_templates]
        _unique(templates, "template IDs")
        _unique(
            [(item.equipment_id, item.deadline) for item in self.equipment_targets],
            "equipment deadlines",
        )
        _unique(
            [(item.template_id, item.deadline) for item in self.division_targets],
            "division deadlines",
        )
        for item in (*self.equipment_targets, *self.division_targets):
            self.horizon.offset_of(item.deadline)
        if any(item.template_id not in templates for item in self.division_targets):
            raise ValueError("Division target references an undeclared template")

    def _validate_decisions(self):
        _unique(
            [(item.at, item.kind, item.identifier, item.phase) for item in self.decisions],
            "dated decisions",
        )
        for item in self.decisions:
            self.horizon.offset_of(item.at)

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "ruleset": self.ruleset.to_dict(),
            "country_tag": self.country_tag,
            "horizon": self.horizon.to_dict(),
            **{
                name: [item.to_dict() for item in getattr(self, name)]
                for name in (
                    "division_templates",
                    "equipment_targets",
                    "division_targets",
                    "decisions",
                )
            },
        }

    @classmethod
    def from_dict(cls, value):
        data = _record(
            value,
            (
                "schema_version",
                "ruleset",
                "country_tag",
                "horizon",
                "division_templates",
                "equipment_targets",
                "division_targets",
                "decisions",
            ),
        )
        return cls(
            schema_version=data["schema_version"],
            ruleset=RulesetTarget.from_dict(data["ruleset"]),
            country_tag=data["country_tag"],
            horizon=HourlyHorizon.from_dict(data["horizon"]),
            division_templates=tuple(
                DivisionTemplate.from_dict(item) for item in _sequence(data["division_templates"])
            ),
            equipment_targets=tuple(
                EquipmentDeadline.from_dict(item) for item in _sequence(data["equipment_targets"])
            ),
            division_targets=tuple(
                DivisionDeadline.from_dict(item) for item in _sequence(data["division_targets"])
            ),
            decisions=tuple(DatedDecision.from_dict(item) for item in _sequence(data["decisions"])),
        )

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, text: str) -> PlanningContract:
        if not isinstance(text, str):
            raise ValueError("Planning JSON must be text")
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_json_object))


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result
