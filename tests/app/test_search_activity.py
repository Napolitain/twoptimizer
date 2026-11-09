"""Heartbeat activity preserves search observations without inventing a deadline."""

import pytest

from twoptimizer.progress import SearchStats
from twoptimizer.search_activity import SearchActivity, format_duration


def event(objective, bound, elapsed, *, label="CP-SAT", sense="maximize", unit="income/turn"):
    return SearchStats(label, objective, bound, elapsed, sense=sense, unit=unit)


def test_native_model_event_starts_elapsed_time_before_any_solver_observation():
    activity = SearchActivity()
    assert activity.summary(90) == "Search not started"
    activity.begin(100)
    snapshot = activity.snapshot(165)
    assert snapshot.elapsed_seconds == 65
    assert snapshot.stats is None and snapshot.first_candidate_seconds is None
    assert snapshot.improvement_age_seconds is None
    assert "No candidate observed yet" in activity.summary(165)
    assert "search 1m 5s" in activity.summary(165)
    assert "proof pending" in activity.summary(165)


def test_bound_only_then_zero_candidate_uses_native_first_candidate_time_and_keeps_ticking():
    activity = SearchActivity()
    activity.begin(100)
    activity.observe(event(None, 100, 2), now=102)
    activity.observe(event(0, 100, 5), now=109)
    snapshot = activity.snapshot(169)
    assert snapshot.elapsed_seconds == 69
    assert snapshot.first_candidate_seconds == 5
    assert snapshot.candidate_age_seconds == 64
    assert snapshot.bound_age_seconds == 67
    assert snapshot.improvement_age_seconds == 64
    assert snapshot.stats is not None and snapshot.stats.objective == 0
    assert snapshot.stats.elapsed_seconds == 69
    assert "Candidate found at 5s" in activity.summary(169)
    assert "layout 1m 4s ago" in activity.summary(169)


@pytest.mark.parametrize(
    "sense, first, better, worse",
    [
        ("maximize", (10, 100), (20, 90), (15, 95)),
        ("maximize", (-100, -10), (-90, -20), (-95, -15)),
        ("minimize", (100, 10), (90, 20), (95, 15)),
        ("minimize", (-10, -100), (-20, -90), (-15, -95)),
    ],
)
def test_only_strict_directional_improvement_resets_each_age(sense, first, better, worse):
    activity = SearchActivity()
    activity.observe(event(*first, 1, sense=sense), now=101)
    activity.observe(event(better[0], first[1], 3, sense=sense), now=103)
    activity.observe(event(*better, 4, sense=sense), now=104)
    activity.observe(event(*better, 5, sense=sense), now=105)
    activity.observe(event(*worse, 6, sense=sense), now=106)
    activity.observe(event(None, None, 7, sense=sense), now=107)
    snapshot = activity.snapshot(110)
    assert snapshot.first_candidate_seconds == 1
    assert snapshot.candidate_age_seconds == 7
    assert snapshot.bound_age_seconds == 6
    assert snapshot.improvement_age_seconds == 6
    assert snapshot.stats is not None
    assert (snapshot.stats.objective, snapshot.stats.bound) == better


def test_delayed_callbacks_cannot_move_clock_or_best_values_backwards():
    activity = SearchActivity()
    activity.observe(event(80, 100, 5), now=100)
    activity.observe(event(90, 95, 10), now=105)
    activity.observe(event(85, 99, 7), now=110)
    snapshot = activity.snapshot(120)
    assert snapshot.elapsed_seconds == 25
    assert snapshot.first_candidate_seconds == 5
    assert snapshot.candidate_age_seconds == snapshot.bound_age_seconds == 15
    assert snapshot.stats is not None
    assert snapshot.stats.objective == 90 and snapshot.stats.bound == 95


def test_native_elapsed_can_extend_clock_without_losing_local_heartbeat_time():
    activity = SearchActivity()
    activity.begin(100)
    activity.observe(event(80, 100, 10), now=101)
    assert activity.snapshot(106).elapsed_seconds == 15
    activity.observe(event(80, 100, 11), now=107)
    assert activity.snapshot(109).elapsed_seconds == 18
    assert activity.snapshot(109).candidate_age_seconds == 8


@pytest.mark.parametrize(
    "change",
    [
        {"label": "With requirements: CP-SAT"},
        {"sense": "minimize"},
        {"unit": "points"},
    ],
)
def test_distinct_search_identity_resets_the_previous_candidate_and_ages(change):
    activity = SearchActivity()
    activity.observe(event(80, 100, 100), now=100)
    activity.observe(event(None, None, 2, **change), now=150)
    snapshot = activity.snapshot(153)
    assert snapshot.elapsed_seconds == 5
    assert snapshot.first_candidate_seconds is None
    assert snapshot.candidate_age_seconds is snapshot.bound_age_seconds is None
    assert snapshot.stats is not None and snapshot.stats.objective is None


def test_new_case_begin_resets_even_when_solver_label_will_be_reused():
    activity = SearchActivity()
    activity.observe(event(80, 100, 5), now=100)
    activity.begin(120)
    snapshot = activity.snapshot(121)
    assert snapshot.elapsed_seconds == 1
    assert snapshot.stats is None
    assert snapshot.first_candidate_seconds is None
    assert snapshot.candidate_age_seconds is snapshot.bound_age_seconds is None
    activity.observe(event(1, 10, 2), now=122)
    assert activity.snapshot(123).first_candidate_seconds == 2


def test_zero_gap_or_unknown_observation_does_not_claim_optimality_or_infeasibility():
    activity = SearchActivity()
    activity.observe(event(0, 0, 0), now=100)
    assert activity.snapshot(100).first_candidate_seconds == 0
    stats = activity.snapshot(100).stats
    assert stats is not None and stats.gap_percent == 0
    summary = activity.summary(160)
    assert "proof pending" in summary
    assert "optimal" not in summary.lower() and "infeasible" not in summary.lower()


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (59.9, "59s"),
        (90, "1m 30s"),
        (7500, "2h 5m"),
        (90000, "1d 1h"),
        (1296000, "2w 1d"),
    ],
)
def test_duration_uses_human_units_for_elapsed_seconds_only(seconds, expected):
    assert format_duration(seconds) == expected


def test_long_silent_search_keeps_ages_live_without_claiming_an_eta():
    activity = SearchActivity()
    activity.observe(event(80, 100, 5), now=100)
    summary = activity.summary(1296100)
    assert "search 2w 1d" in summary
    assert "layout 2w 1d ago" in summary and "bound 2w 1d ago" in summary
    assert "ETA" not in summary and "remaining" not in summary
