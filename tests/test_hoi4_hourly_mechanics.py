"""Provisional active-hour approximation boundaries and numerical conservation."""

import math
from dataclasses import FrozenInstanceError, replace

import pytest

from games.hoi4.planning import CampaignDate, HourlyHorizon
from games.hoi4.planning.mechanics import (
    EfficiencyCohort,
    ProductionProfile,
    RecruitmentProgress,
    advance_production_hour,
    advance_recruitment_hour,
)


@pytest.fixture
def profile():
    return ProductionProfile(0.5, 4.5, 0.001, 1.0)


def test_active_hour_uses_starting_efficiency_then_updates_boundary(profile):
    before = EfficiencyCohort(2, 0.1, 0.25)
    after = advance_production_hour(before, profile)
    assert after.carried_ic == pytest.approx(0.25 + 2 * 4.5 * 0.1 / 24)
    assert after.efficiency == pytest.approx(0.1 + 0.001 * 0.5**2 / 0.1 / 24)
    assert before.carried_ic == 0.25 and before.efficiency == 0.1


def test_growth_is_capped_and_gained_efficiency_is_not_applied_early(profile):
    before = EfficiencyCohort(1, 0.49999, 0)
    after = advance_production_hour(before, profile)
    assert after.efficiency == profile.efficiency_cap
    assert after.carried_ic == pytest.approx(4.5 * before.efficiency / 24)
    assert advance_production_hour(after, profile).efficiency == profile.efficiency_cap


def test_fractional_ic_is_retained_across_hours_instead_of_flooring_equipment(profile):
    constant = replace(profile, daily_efficiency_growth_coefficient=0)
    cohort = EfficiencyCohort(1, 0.5, 0)
    for _ in range(24):
        cohort = advance_production_hour(cohort, constant)
    assert cohort.carried_ic == pytest.approx(2.25)
    assert cohort.efficiency == 0.5


def test_splitting_identical_cohorts_preserves_production_and_growth(profile):
    whole = EfficiencyCohort(5, 0.1, 0.7)
    parts = [EfficiencyCohort(2, 0.1, 0.2), EfficiencyCohort(3, 0.1, 0.5)]
    for _ in range(240):
        whole = advance_production_hour(whole, profile)
        parts = [advance_production_hour(part, profile) for part in parts]
    assert whole.carried_ic == pytest.approx(sum(part.carried_ic for part in parts))
    assert all(part.efficiency == whole.efficiency for part in parts)


def test_multiyear_hourly_growth_stays_finite_and_bounded(profile):
    cohort = EfficiencyCohort(10, 0.1, 0)
    for _ in range(30_000):
        cohort = advance_production_hour(cohort, profile)
    assert math.isfinite(cohort.carried_ic) and cohort.carried_ic > 0
    assert cohort.efficiency == profile.efficiency_cap


def test_zero_supplied_gain_and_output_are_not_replaced_with_defaults(profile):
    paused = replace(profile, effective_ic_per_factory_day=0, efficiency_gain_multiplier=0)
    cohort = EfficiencyCohort(1, 0.1, 2.5)
    assert advance_production_hour(cohort, paused) == cohort


@pytest.mark.parametrize("value", [True, "0.5", None, -0.1, math.inf, -math.inf, math.nan])
def test_rates_and_cohort_values_require_finite_nonnegative_numbers(profile, value):
    for field in (
        "efficiency_cap",
        "effective_ic_per_factory_day",
        "daily_efficiency_growth_coefficient",
        "efficiency_gain_multiplier",
    ):
        with pytest.raises(ValueError, match="finite nonnegative"):
            replace(profile, **{field: value})
    for field in ("efficiency", "carried_ic"):
        with pytest.raises(ValueError, match="finite nonnegative"):
            replace(EfficiencyCohort(1, 0.1, 0), **{field: value})


def test_zero_efficiency_and_lowered_cap_require_explicit_caller_handling(profile):
    with pytest.raises(ValueError, match="positive"):
        replace(profile, efficiency_cap=0)
    with pytest.raises(ValueError, match="positive"):
        EfficiencyCohort(1, 0, 0)
    with pytest.raises(ValueError, match="exceeds"):
        advance_production_hour(EfficiencyCohort(1, 0.6, 0), profile)


@pytest.mark.parametrize("value", [True, 1.5, "1", -1, None])
def test_counts_and_training_hours_reject_coercion(value):
    with pytest.raises(ValueError, match="whole number"):
        EfficiencyCohort(value, 0.1, 0)
    with pytest.raises(ValueError, match="whole number"):
        RecruitmentProgress(value, 0)
    with pytest.raises(ValueError, match="whole number"):
        RecruitmentProgress(24, value)


def test_empty_factory_cohort_and_excess_training_are_rejected():
    with pytest.raises(ValueError, match="at least one"):
        EfficiencyCohort(0, 0.1, 0)
    with pytest.raises(ValueError, match="exceed"):
        RecruitmentProgress(24, 25)


@pytest.mark.parametrize("equipment,manpower", [(False, False), (False, True), (True, False)])
def test_training_earns_no_progress_without_full_equipment_and_manpower(equipment, manpower):
    progress = RecruitmentProgress(24, 3)
    assert (
        advance_recruitment_hour(progress, fully_equipped=equipment, manpower_available=manpower)
        == progress
    )
    assert not progress.ready_at_boundary(fully_equipped=equipment, manpower_available=manpower)


def test_readiness_at_deadline_does_not_receive_an_extra_hour():
    start = CampaignDate(1936, 1, 1)
    horizon = HourlyHorizon(start, start.add_hours(24))
    exact, short = RecruitmentProgress(24, 0), RecruitmentProgress(25, 0)
    for _ in horizon.offsets():
        exact = advance_recruitment_hour(exact, fully_equipped=True, manpower_available=True)
        short = advance_recruitment_hour(short, fully_equipped=True, manpower_available=True)
    assert exact.ready_at_boundary(fully_equipped=True, manpower_available=True)
    assert not short.ready_at_boundary(fully_equipped=True, manpower_available=True)
    assert exact.completed_training_hours == short.completed_training_hours == 24
    assert advance_recruitment_hour(exact, fully_equipped=True, manpower_available=True) == exact


def test_finished_training_still_requires_equipment_and_manpower_at_deadline():
    completed = RecruitmentProgress(24, 24)
    assert not completed.ready_at_boundary(fully_equipped=False, manpower_available=True)
    assert not completed.ready_at_boundary(fully_equipped=True, manpower_available=False)
    assert completed.ready_at_boundary(fully_equipped=True, manpower_available=True)


def test_zero_duration_is_explicit_and_requires_readiness_gates():
    completed = RecruitmentProgress(0, 0)
    assert completed.ready_at_boundary(fully_equipped=True, manpower_available=True)
    assert not completed.ready_at_boundary(fully_equipped=False, manpower_available=True)


@pytest.mark.parametrize("value", [0, 1, "yes", None])
def test_readiness_gates_require_explicit_booleans(value):
    progress = RecruitmentProgress(24, 0)
    with pytest.raises(ValueError, match="booleans"):
        advance_recruitment_hour(progress, fully_equipped=value, manpower_available=True)
    with pytest.raises(ValueError, match="booleans"):
        progress.ready_at_boundary(fully_equipped=True, manpower_available=value)


def test_arithmetic_records_are_immutable(profile):
    for record, attribute in (
        (profile, "efficiency_cap"),
        (EfficiencyCohort(1, 0.1, 0), "carried_ic"),
        (RecruitmentProgress(24, 0), "completed_training_hours"),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(record, attribute, 1)
