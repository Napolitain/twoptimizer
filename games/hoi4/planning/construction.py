"""Simultaneous hourly construction with explicit completion-overflow policy.

All allocations and infrastructure multipliers use the starting boundary.
Completions become available at the ending boundary. This is an explicit hourly
integration convention, not verified internal engine event ordering.
"""

import math
from dataclasses import dataclass, replace
from enum import StrEnum

from games.hoi4.planning.mechanics import _finite_nonnegative, _whole_nonnegative
from games.hoi4.planning.time import HOURS_PER_DAY


class BuildingKind(StrEnum):
    CIVILIAN_FACTORY = "industrial_complex"
    MILITARY_FACTORY = "arms_factory"
    INFRASTRUCTURE = "infrastructure"


class OverflowPolicy(StrEnum):
    DISCARD = "discard"
    RETAIN_FOR_CALLER = "retain_for_caller"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or not value.isprintable():
        raise ValueError(
            f"{label} must be nonempty text without surrounding whitespace or controls"
        )
    return value


def _state_id(value: object) -> int:
    result = _whole_nonnegative(value, "State ID")
    if result == 0:
        raise ValueError("State ID must be positive")
    return result


@dataclass(frozen=True, slots=True)
class StateConstruction:
    state_id: int
    slot_capacity: int
    civilian_factories: int
    military_factories: int
    other_shared_slots: int
    infrastructure_level: int
    infrastructure_max_level: int

    def __post_init__(self):
        _state_id(self.state_id)
        for name in (
            "slot_capacity",
            "civilian_factories",
            "military_factories",
            "other_shared_slots",
            "infrastructure_level",
            "infrastructure_max_level",
        ):
            _whole_nonnegative(getattr(self, name), name)
        if self.occupied_slots > self.slot_capacity:
            raise ValueError("Existing buildings exceed supplied shared-slot capacity")
        if self.infrastructure_level > self.infrastructure_max_level:
            raise ValueError("Infrastructure exceeds supplied maximum level")

    @property
    def occupied_slots(self) -> int:
        return self.civilian_factories + self.military_factories + self.other_shared_slots


@dataclass(frozen=True, slots=True)
class ConstructionProject:
    project_id: str
    state_id: int
    building: BuildingKind
    required_ic: float
    progress_ic: float
    infrastructure_affected: bool

    def __post_init__(self):
        _identifier(self.project_id, "Project ID")
        _state_id(self.state_id)
        if not isinstance(self.building, str):
            raise ValueError("Choose an explicit building kind")
        object.__setattr__(self, "building", BuildingKind(self.building))
        for name in ("required_ic", "progress_ic"):
            object.__setattr__(self, name, _finite_nonnegative(getattr(self, name), name))
        if self.required_ic == 0 or self.progress_ic >= self.required_ic:
            raise ValueError("A pending project needs positive cost and progress below cost")
        if type(self.infrastructure_affected) is not bool:
            raise ValueError("Infrastructure applicability must be an explicit boolean")


@dataclass(frozen=True, slots=True)
class ConstructionAllocation:
    project_id: str
    civilian_factories: int
    effective_ic_per_factory_day: float

    def __post_init__(self):
        _identifier(self.project_id, "Project ID")
        _whole_nonnegative(self.civilian_factories, "Allocated factories")
        object.__setattr__(
            self,
            "effective_ic_per_factory_day",
            _finite_nonnegative(self.effective_ic_per_factory_day, "Effective output"),
        )


@dataclass(frozen=True, slots=True)
class ConstructionProfile:
    max_factories_per_project: int
    infrastructure_bonus_per_level: float

    def __post_init__(self):
        if _whole_nonnegative(self.max_factories_per_project, "Project factory cap") == 0:
            raise ValueError("Project factory cap must be positive")
        object.__setattr__(
            self,
            "infrastructure_bonus_per_level",
            _finite_nonnegative(self.infrastructure_bonus_per_level, "Infrastructure bonus"),
        )


@dataclass(frozen=True, slots=True)
class ConstructionCompletion:
    project_id: str
    state_id: int
    building: BuildingKind
    retained_ic: float
    discarded_ic: float


@dataclass(frozen=True, slots=True)
class ConstructionHour:
    states: tuple[StateConstruction, ...]
    projects: tuple[ConstructionProject, ...]
    completions: tuple[ConstructionCompletion, ...]
    allocated_civilian_factories: int
    produced_ic: float
    applied_ic: float

    @property
    def new_civilian_factories(self) -> int:
        return sum(item.building == BuildingKind.CIVILIAN_FACTORY for item in self.completions)

    @property
    def new_military_factories(self) -> int:
        return sum(item.building == BuildingKind.MILITARY_FACTORY for item in self.completions)


def _indexed(values, record_type, key: str):
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(value, record_type) for value in values
    ):
        raise ValueError(f"Expected an ordered sequence of {record_type.__name__}")
    result = {getattr(value, key): value for value in values}
    if len(result) != len(values):
        raise ValueError(f"Duplicate {key}")
    return result


def _validate_reservations(states, projects):
    reservations = {state_id: [0, 0] for state_id in states}
    for project in projects.values():
        if project.state_id not in states:
            raise ValueError("Project references unknown state")
        reservations[project.state_id][project.building == BuildingKind.INFRASTRUCTURE] += 1
    for state_id, (shared, infrastructure) in reservations.items():
        state = states[state_id]
        if state.occupied_slots + shared > state.slot_capacity:
            raise ValueError("Pending construction exceeds shared-slot capacity")
        if state.infrastructure_level + infrastructure > state.infrastructure_max_level:
            raise ValueError("Pending infrastructure exceeds maximum level")


def _validate_allocations(projects, allocations, available, profile):
    assigned = sum(item.civilian_factories for item in allocations.values())
    if assigned > available:
        raise ValueError("Allocated construction factories exceed available civilians")
    for item in allocations.values():
        if item.project_id not in projects:
            raise ValueError("Allocation references unknown project")
        if item.civilian_factories > profile.max_factories_per_project:
            raise ValueError("Allocation exceeds civilian factories per project cap")
    return assigned


def _finish_project(project, overflow, policy, states):
    state = states[project.state_id]
    field = {
        BuildingKind.CIVILIAN_FACTORY: "civilian_factories",
        BuildingKind.MILITARY_FACTORY: "military_factories",
        BuildingKind.INFRASTRUCTURE: "infrastructure_level",
    }[project.building]
    states[project.state_id] = replace(state, **{field: getattr(state, field) + 1})
    return ConstructionCompletion(
        project.project_id,
        project.state_id,
        project.building,
        overflow if policy == OverflowPolicy.RETAIN_FOR_CALLER else 0.0,
        overflow if policy == OverflowPolicy.DISCARD else 0.0,
    )


def _project_output(project, state, allocation, profile):
    if allocation is None:
        return 0.0
    infrastructure = (
        1 + state.infrastructure_level * profile.infrastructure_bonus_per_level
        if project.infrastructure_affected
        else 1.0
    )
    value = (
        allocation.civilian_factories
        * allocation.effective_ic_per_factory_day
        * infrastructure
        / HOURS_PER_DAY
    )
    return _finite_nonnegative(value, "Hourly construction output")


def advance_construction_hour(
    states: tuple[StateConstruction, ...],
    projects: tuple[ConstructionProject, ...],
    allocations: tuple[ConstructionAllocation, ...],
    *,
    available_civilian_factories: int,
    profile: ConstructionProfile,
    overflow_policy: OverflowPolicy,
) -> ConstructionHour:
    """Apply one simultaneous hour; completed buildings enter the ending state.

    Retained excess is returned per completion for explicit caller routing. It
    is not automatically converted across projects with different modifiers.
    Pending projects reserve their future shared/infrastructure slots.
    """
    _whole_nonnegative(available_civilian_factories, "Available civilian factories")
    if not isinstance(profile, ConstructionProfile) or not isinstance(overflow_policy, str):
        raise ValueError("Explicit ConstructionProfile and overflow policy are required")
    policy = OverflowPolicy(overflow_policy)
    initial = _indexed(states, StateConstruction, "state_id")
    pending = _indexed(projects, ConstructionProject, "project_id")
    assigned = _indexed(allocations, ConstructionAllocation, "project_id")
    _validate_reservations(initial, pending)
    factory_count = _validate_allocations(pending, assigned, available_civilian_factories, profile)
    final_states, remaining, completions, outputs, applied = dict(initial), [], [], [], []
    for project in pending.values():
        output = _project_output(
            project, initial[project.state_id], assigned.get(project.project_id), profile
        )
        outputs.append(output)
        applied.append(min(output, project.required_ic - project.progress_ic))
        total = _finite_nonnegative(project.progress_ic + output, "Construction progress")
        if total >= project.required_ic:
            completions.append(
                _finish_project(project, total - project.required_ic, policy, final_states)
            )
        else:
            remaining.append(replace(project, progress_ic=total))
    return ConstructionHour(
        tuple(final_states.values()),
        tuple(remaining),
        tuple(completions),
        factory_count,
        math.fsum(outputs),
        math.fsum(applied),
    )
