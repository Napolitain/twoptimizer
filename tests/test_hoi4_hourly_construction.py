"""Construction conserves hourly IC and adds capacity only at a boundary."""

import math
from dataclasses import replace

import pytest

from games.hoi4.planning.construction import (
    BuildingKind,
    ConstructionAllocation,
    ConstructionProfile,
    ConstructionProject,
    OverflowPolicy,
    StateConstruction,
    advance_construction_hour,
)
from games.hoi4.planning.economy import ConsumerGoodsInputs, consumer_goods


@pytest.fixture
def state():
    return StateConstruction(1, 10, 2, 1, 1, 2, 5)


@pytest.fixture
def project():
    return ConstructionProject("civ", 1, BuildingKind.CIVILIAN_FACTORY, 10800, 0, True)


@pytest.fixture
def profile():
    return ConstructionProfile(15, 0.2)


def hour(states, projects, allocations, profile, available=100, policy=OverflowPolicy.DISCARD):
    return advance_construction_hour(
        tuple(states),
        tuple(projects),
        tuple(allocations),
        available_civilian_factories=available,
        profile=profile,
        overflow_policy=policy,
    )


def test_project_progress_includes_infrastructure_and_retains_fractional_ic(
    state, project, profile
):
    result = hour([state], [project], [ConstructionAllocation("civ", 3, 5)], profile)
    assert result.produced_ic == pytest.approx(3 * 5 * 1.4 / 24)
    assert result.projects[0].progress_ic == result.applied_ic == result.produced_ic
    assert result.completions == () and result.states == (state,)


def test_allocations_use_supplied_effective_dated_output_each_hour(state, project, profile):
    first = hour([state], [project], [ConstructionAllocation("civ", 1, 5)], profile)
    second = hour(first.states, first.projects, [ConstructionAllocation("civ", 1, 10)], profile)
    assert second.produced_ic == 2 * first.produced_ic
    assert second.projects[0].progress_ic == pytest.approx(3 * first.produced_ic)


@pytest.mark.parametrize("policy", list(OverflowPolicy))
def test_completion_excess_has_an_explicit_policy_and_preserves_accounting(
    state, project, profile, policy
):
    almost = replace(project, progress_ic=10799.75)
    result = hour([state], [almost], [ConstructionAllocation("civ", 1, 24)], profile, policy=policy)
    completion = result.completions[0]
    assert result.projects == () and result.new_civilian_factories == 1
    assert result.states[0].civilian_factories == state.civilian_factories + 1
    assert result.applied_ic == 0.25
    assert completion.retained_ic + completion.discarded_ic == pytest.approx(1.15)
    assert result.produced_ic == pytest.approx(
        result.applied_ic + completion.retained_ic + completion.discarded_ic
    )
    assert (completion.retained_ic > 0) == (policy == OverflowPolicy.RETAIN_FOR_CALLER)


def test_simultaneous_infrastructure_completion_affects_only_next_hour(state, project, profile):
    infrastructure = ConstructionProject("infra", 1, BuildingKind.INFRASTRUCTURE, 6000, 5999, False)
    allocations = [ConstructionAllocation("infra", 1, 24), ConstructionAllocation("civ", 1, 24)]
    first = hour([state], [infrastructure, project], allocations, profile)
    assert first.states[0].infrastructure_level == 3
    assert first.projects[0].progress_ic == pytest.approx(1.4)
    second = hour(first.states, first.projects, [allocations[1]], profile)
    assert second.produced_ic == pytest.approx(1.6)
    assert second.projects[0].progress_ic == pytest.approx(3.0)


def test_civilian_completion_compounds_next_hour_after_consumer_goods_recalculation(profile):
    state = StateConstruction(1, 5, 1, 0, 0, 0, 5)
    first_project = ConstructionProject("first", 1, BuildingKind.CIVILIAN_FACTORY, 1, 0, True)
    first = hour(
        [state], [first_project], [ConstructionAllocation("first", 1, 24)], profile, available=1
    )
    assert first.allocated_civilian_factories == 1 and first.new_civilian_factories == 1
    next_civs = first.states[0].civilian_factories
    capacity = consumer_goods(ConsumerGoodsInputs(next_civs, next_civs, (0,), (), 0, 0))
    assert capacity.construction_factories == 2
    second_project = ConstructionProject("second", 1, BuildingKind.CIVILIAN_FACTORY, 10, 0, True)
    second = hour(
        first.states,
        [second_project],
        [ConstructionAllocation("second", 2, 24)],
        profile,
        available=capacity.construction_factories,
    )
    assert second.produced_ic == 2 and second.projects[0].progress_ic == 2


def test_slot_reservations_prevent_simultaneous_completion_overbooking(state, project, profile):
    tight = replace(state, slot_capacity=state.occupied_slots + 1)
    other = replace(project, project_id="mil", building=BuildingKind.MILITARY_FACTORY)
    with pytest.raises(ValueError, match="shared-slot"):
        hour([tight], [project, other], [], profile)
    valid = hour([tight], [project], [], profile)
    assert valid.projects == (project,)


def test_full_shared_slots_do_not_block_infrastructure_but_maximum_level_does(state, profile):
    full = replace(state, slot_capacity=state.occupied_slots)
    infrastructure = ConstructionProject("infra", 1, BuildingKind.INFRASTRUCTURE, 1, 0, False)
    result = hour([full], [infrastructure], [ConstructionAllocation("infra", 1, 24)], profile)
    assert result.states[0].occupied_slots == full.occupied_slots
    with pytest.raises(ValueError, match="maximum level"):
        hour([replace(full, infrastructure_level=5)], [infrastructure], [], profile)


def test_military_factory_completion_is_reported_at_boundary(state, project, profile):
    military = replace(project, building=BuildingKind.MILITARY_FACTORY, required_ic=1)
    result = hour([state], [military], [ConstructionAllocation("civ", 1, 24)], profile)
    assert result.new_military_factories == 1 and result.new_civilian_factories == 0
    assert result.states[0].military_factories == state.military_factories + 1


def test_per_project_factory_cap_and_country_pool_are_independent(state, project, profile):
    with pytest.raises(ValueError, match="per project cap"):
        hour([state], [project], [ConstructionAllocation("civ", 16, 5)], profile)
    with pytest.raises(ValueError, match="available civilians"):
        hour([state], [project], [ConstructionAllocation("civ", 2, 5)], profile, available=1)
    result = hour([state], [project], [ConstructionAllocation("civ", 15, 5)], profile, available=15)
    assert result.allocated_civilian_factories == 15


def test_unknown_references_and_duplicate_inputs_are_rejected(state, project, profile):
    with pytest.raises(ValueError, match="unknown state"):
        hour([], [project], [], profile)
    with pytest.raises(ValueError, match="unknown project"):
        hour([state], [], [ConstructionAllocation("civ", 1, 5)], profile)
    with pytest.raises(ValueError, match="Duplicate state_id"):
        hour([state, state], [], [], profile)
    with pytest.raises(ValueError, match="Duplicate project_id"):
        hour([state], [project, project], [], profile)
    allocation = ConstructionAllocation("civ", 1, 5)
    with pytest.raises(ValueError, match="Duplicate project_id"):
        hour([state], [project], [allocation, allocation], profile)


@pytest.mark.parametrize("value", [True, 1.5, "1", -1, None])
def test_counts_reject_coercion(state, profile, value):
    with pytest.raises(ValueError):
        replace(state, slot_capacity=value)
    with pytest.raises(ValueError):
        replace(profile, max_factories_per_project=value)
    with pytest.raises(ValueError):
        ConstructionAllocation("project", value, 5)


@pytest.mark.parametrize("value", [True, None, "1", -1, math.nan, math.inf])
def test_ic_and_profile_rates_require_finite_nonnegative_numbers(project, profile, value):
    with pytest.raises(ValueError):
        replace(project, progress_ic=value)
    with pytest.raises(ValueError):
        replace(profile, infrastructure_bonus_per_level=value)
    with pytest.raises(ValueError):
        ConstructionAllocation("project", 1, value)


def test_pending_projects_and_state_capacities_validate_their_boundaries(state, project, profile):
    with pytest.raises(ValueError, match="below cost"):
        replace(project, progress_ic=project.required_ic)
    with pytest.raises(ValueError, match="positive cost"):
        replace(project, required_ic=0)
    with pytest.raises(ValueError, match="shared-slot"):
        replace(state, slot_capacity=0)
    with pytest.raises(ValueError, match="maximum level"):
        replace(state, infrastructure_level=6)
    with pytest.raises(ValueError, match="positive"):
        replace(profile, max_factories_per_project=0)
    with pytest.raises(ValueError, match="explicit boolean"):
        replace(project, infrastructure_affected=1)


@pytest.mark.parametrize("policy", [None, True, "automatic"])
def test_overflow_policy_has_no_implicit_default(state, project, profile, policy):
    with pytest.raises(ValueError):
        hour([state], [project], [], profile, policy=policy)


def test_empty_hour_has_no_implicit_work_or_capacity(profile):
    result = hour([], [], [], profile, available=0)
    assert result.states == result.projects == result.completions == ()
    assert result.produced_ic == result.applied_ic == result.allocated_civilian_factories == 0
