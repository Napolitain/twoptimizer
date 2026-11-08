"""Session timing evidence stays exact, bounded and separate from forecasts."""

from dataclasses import replace

import pytest

from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.models import AttilaOptions, RunConfig
from twoptimizer.runtime_history import RuntimeHistory


def test_empty_history_and_unrecognized_statuses_do_not_invent_a_runtime():
    history, job = RuntimeHistory(), RunConfig()
    assert history.summary([]) is None
    assert history.summary([job]) is None
    for status in ("ERROR", "MODEL_INVALID", "FAILED", ""):
        history.record(job, status, 42)
    assert history.summary([job]) is None
    assert history.details([job]) == "No runs with these exact settings recorded this session."


def test_proved_and_unfinished_runs_remain_distinct_even_when_unfinished_is_faster():
    history, job = RuntimeHistory(), RunConfig()
    history.record(job, "OPTIMAL", 125)
    history.record(job, "INFEASIBLE", 185)
    history.record(job, "FEASIBLE", 10)
    history.record(job, "UNKNOWN", 20)
    history.record(job, "CANCELLED", 30)
    assert history.summary([job]) == (
        "This session: previously proved in 2m 5s to 3m 5s; "
        "stopped without proof after 10.0s to 30.0s. Not an ETA."
    )
    details = history.details([job])
    assert "5 retained observations" in details
    assert "INFEASIBLE: 1" in details and "UNKNOWN: 1" in details and "CANCELLED: 1" in details
    assert "Unfinished runs do not establish how long a proof would take" in details


@pytest.mark.parametrize("status", ["FEASIBLE", "UNKNOWN", "CANCELLED"])
def test_unfinished_observations_never_become_proof_durations(status):
    history, job = RuntimeHistory(), RunConfig()
    history.record(job, status, 3605)
    assert history.summary([job]) == (
        "This session: stopped without proof after 1h 0m. Not an ETA."
    )
    assert "previously proved" not in history.details([job])


@pytest.mark.parametrize(
    "change",
    [
        {"seconds": 60},
        {"workers": 2},
        {"province": "inland"},
        {"provinces": ("coastal", "inland")},
        {"joint": True},
        {"adjacency": ()},
        {"faction": "rom_egypt"},
        {"algorithm": "highs"},
        {"research": "all"},
        {"fertility": 1},
        {"world_bonuses": False},
        {"constraints": ConstraintOptions(required_buildings=("temple",))},
        {"attila": AttilaOptions(seed=42)},
        {"compare_constraints": True},
        {"comparison_candidates": ("temple",)},
    ],
)
def test_every_request_setting_participates_in_matching(change):
    history, job = RuntimeHistory(), RunConfig()
    history.record(job, "OPTIMAL", 1.5)
    assert history.summary([replace(job, **change)]) is None
    restored = RunConfig.from_dict(dict(reversed(list(job.to_dict().items()))))
    assert history.summary([restored]) == "This session: previously proved in 1.5s. Not an ETA."


def test_partial_batch_history_does_not_extrapolate_or_duplicate_observations():
    history, known = RuntimeHistory(), RunConfig()
    unknown = replace(known, province="inland")
    history.record(known, "OPTIMAL", 1)
    history.record(known, "OPTIMAL", 3)
    jobs = [known, unknown, known]
    assert history.summary(jobs) == (
        "This session: history for 2/3 cases; previously proved in 1.0s to 3.0s per case. "
        "No batch ETA."
    )
    assert "2 retained observations" in history.details(jobs)
    assert "No durations are inferred for unmatched cases" in history.details(jobs)


def test_storage_limits_retain_recent_samples_and_recently_recorded_requests():
    history = RuntimeHistory(max_requests=2, samples_per_request=2)
    a = RunConfig()
    b, c = replace(a, province="inland"), replace(a, province="grain")
    for seconds in (100, 2, 3):
        history.record(a, "OPTIMAL", seconds)
    first_summary = history.summary([a])
    assert first_summary is not None and "2.0s to 3.0s" in first_summary
    assert "2 retained observations" in history.details([a])
    history.record(b, "UNKNOWN", 50)
    history.record(a, "OPTIMAL", 4)
    history.record(c, "OPTIMAL", 5)
    assert history.summary([b]) is None
    assert history.summary([a]) is not None and history.summary([c]) is not None
    updated_summary = history.summary([a])
    assert updated_summary is not None and "3.0s to 4.0s" in updated_summary


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, None, "1"])
def test_invalid_observed_times_are_rejected(value):
    history, job = RuntimeHistory(), RunConfig()
    with pytest.raises(ValueError, match="finite and nonnegative"):
        history.record(job, "OPTIMAL", value)
    assert history.summary([job]) is None


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
@pytest.mark.parametrize("setting", ["max_requests", "samples_per_request"])
def test_invalid_storage_limits_are_rejected(setting, value):
    with pytest.raises(ValueError, match="positive integers"):
        RuntimeHistory(**{setting: value})


@pytest.mark.parametrize(
    ("seconds", "display"), [(0, "0.0s"), (86401, "1d 0h"), (1296000, "2w 1d")]
)
def test_zero_and_long_elapsed_times_are_observations_not_forecasts(seconds, display):
    history, job = RuntimeHistory(), RunConfig()
    history.record(job, "OPTIMAL", seconds)
    assert history.summary([job]) == f"This session: previously proved in {display}. Not an ETA."
