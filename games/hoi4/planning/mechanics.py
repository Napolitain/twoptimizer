"""Small provisional hourly arithmetic helpers, not a simulator or optimizer.

Production uses a forward Euler approximation: an active hour produces at its
starting efficiency, then efficiency gains are applied at the ending boundary.
This numerical convention is not a claim about the engine's internal tick order.
Callers supply effective output after all resource, power and other modifiers.
No idle-hour, line-switching, equipment-allocation or training-reset rules are
inferred. Float64 arithmetic avoids exploding rational denominators when the
nonlinear efficiency curve is applied over a multi-year hourly horizon.
"""

import math
from dataclasses import dataclass

from games.hoi4.planning.time import HOURS_PER_DAY


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite nonnegative number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must fit finite float64 arithmetic") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite nonnegative number")
    return number


def _whole_nonnegative(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a nonnegative whole number")
    return value


def _eligible(fully_equipped: bool, manpower_available: bool) -> bool:
    if type(fully_equipped) is not bool or type(manpower_available) is not bool:
        raise ValueError("Equipment and manpower gates must be explicit booleans")
    return fully_equipped and manpower_available


@dataclass(frozen=True, slots=True)
class ProductionProfile:
    """Supplied effective rates; no current-version constants are implied."""

    efficiency_cap: float
    effective_ic_per_factory_day: float
    daily_efficiency_growth_coefficient: float
    efficiency_gain_multiplier: float

    def __post_init__(self):
        for name in (
            "efficiency_cap",
            "effective_ic_per_factory_day",
            "daily_efficiency_growth_coefficient",
            "efficiency_gain_multiplier",
        ):
            object.__setattr__(self, name, _finite_nonnegative(getattr(self, name), name))
        if self.efficiency_cap == 0:
            raise ValueError("Efficiency cap must be positive")


@dataclass(frozen=True, slots=True)
class EfficiencyCohort:
    """Factories sharing an efficiency and retaining fractional production IC."""

    factory_count: int
    efficiency: float
    carried_ic: float

    def __post_init__(self):
        if _whole_nonnegative(self.factory_count, "Factory count") == 0:
            raise ValueError("An active cohort must contain at least one factory")
        object.__setattr__(self, "efficiency", _finite_nonnegative(self.efficiency, "Efficiency"))
        object.__setattr__(self, "carried_ic", _finite_nonnegative(self.carried_ic, "Carried IC"))
        if self.efficiency == 0:
            raise ValueError("Efficiency must be positive for the reciprocal growth curve")


def advance_production_hour(
    cohort: EfficiencyCohort, profile: ProductionProfile
) -> EfficiencyCohort:
    """Advance one supplied active hour without rounding IC into equipment units.

    With coefficient k, cap c, gain multiplier g and starting efficiency e,
    e_next = min(c, e + k*c*c/e*g/24). The documented daily curve uses k=0.001;
    the caller must supply its coefficient and all other effective parameters.
    """
    if not isinstance(cohort, EfficiencyCohort) or not isinstance(profile, ProductionProfile):
        raise ValueError("Production requires EfficiencyCohort and ProductionProfile")
    if cohort.efficiency > profile.efficiency_cap:
        raise ValueError("Starting efficiency exceeds the supplied cap")
    try:
        produced_ic = (
            profile.effective_ic_per_factory_day
            * cohort.efficiency
            / HOURS_PER_DAY
            * cohort.factory_count
        )
        gain = (
            profile.daily_efficiency_growth_coefficient
            * profile.efficiency_cap**2
            / cohort.efficiency
            * profile.efficiency_gain_multiplier
            / HOURS_PER_DAY
        )
    except OverflowError as error:
        raise ValueError("Production inputs exceed finite float64 arithmetic") from error
    _finite_nonnegative(gain, "Hourly efficiency gain")
    return EfficiencyCohort(
        factory_count=cohort.factory_count,
        efficiency=min(profile.efficiency_cap, cohort.efficiency + gain),
        carried_ic=cohort.carried_ic + produced_ic,
    )


@dataclass(frozen=True, slots=True)
class RecruitmentProgress:
    """Training-hour bookkeeping for one division with supplied eligibility."""

    required_training_hours: int
    completed_training_hours: int

    def __post_init__(self):
        _whole_nonnegative(self.required_training_hours, "Required training hours")
        _whole_nonnegative(self.completed_training_hours, "Completed training hours")
        if self.completed_training_hours > self.required_training_hours:
            raise ValueError("Completed training cannot exceed its requirement")

    def ready_at_boundary(self, *, fully_equipped: bool, manpower_available: bool) -> bool:
        """Check readiness at the current boundary without advancing another hour."""
        eligible = _eligible(fully_equipped, manpower_available)
        return eligible and self.completed_training_hours == self.required_training_hours


def advance_recruitment_hour(
    progress: RecruitmentProgress, *, fully_equipped: bool, manpower_available: bool
) -> RecruitmentProgress:
    """Credit one training hour only when the caller supplies both readiness gates.

    Ineligible hours earn no training. Existing progress is preserved; deciding
    whether a loss of equipment should erase it belongs to the caller's model.
    """
    if not isinstance(progress, RecruitmentProgress):
        raise ValueError("Recruitment requires RecruitmentProgress")
    eligible = _eligible(fully_equipped, manpower_available)
    completed = min(
        progress.required_training_hours, progress.completed_training_hours + int(eligible)
    )
    return RecruitmentProgress(progress.required_training_hours, completed)
