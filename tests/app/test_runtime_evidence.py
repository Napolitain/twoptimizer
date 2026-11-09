"""Historical runtimes are matched narrowly and never turn censored runs into ETAs."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.models import AttilaOptions, RunConfig
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.runtime_evidence import Observation, _evidence, runtime_details, runtime_outlook


def _all(game, *, joint=True, **changes):
    config = replace(default_config(game), provinces=("all",), joint=joint, **changes)
    return config, make_jobs(config)[0]


@pytest.mark.parametrize("game", ["attila", "rome2"])
def test_full_world_unfinished_references_do_not_predict_a_completion_time(game):
    config, jobs = _all(game)
    text = runtime_outlook(config, jobs)
    assert text.startswith("Proof time unknown")
    assert "unfinished after" in text
    assert "completed in" not in text
    details = runtime_details(config, jobs)
    assert "FEASIBLE" in details
    assert "1m 0s total" in details
    assert "4 solver workers" in details and "Historical reference measured" in details
    assert "SHA-256" not in details
    assert "minutes, hours or weeks" in details
    assert "gap is not percent of work completed" in details


def test_all_independent_shogun_cases_use_only_completed_historical_batch_times():
    config, jobs = _all("shogun2", joint=False)
    assert len(jobs) == 65
    text = runtime_outlook(config, jobs)
    assert text == "Historical reference: completed in 1.8s to 1.9s · not an ETA."
    details = runtime_details(config, jobs)
    assert "65 OPTIMAL" in details and "12.0s total" in details
    assert "current build, machine, worker count and time limit may differ" in details


def test_mixed_shogun_joint_reference_keeps_the_unfinished_repeat_visible():
    config, jobs = _all("shogun2")
    text = runtime_outlook(config, jobs)
    assert "uncertain" in text and "proof 8.0s" in text
    assert "unfinished after 13.0s" in text
    details = runtime_details(config, jobs)
    assert "1 OPTIMAL" in details and "1 FEASIBLE" in details


@pytest.mark.parametrize(
    "change",
    [
        {"faction": "att_fact_western_roman_empire"},
        {"research": "none"},
        {"algorithm": "highs"},
        {"fertility": 1},
        {"religion": "ROMAN_PAGANISM"},
        {"adjacency": ()},
        {"world_bonuses": False},
        {"attila": AttilaOptions(city_level=3)},
        {"constraints": ConstraintOptions(minimum_religious_influence=5)},
        {"compare_constraints": True},
        {"comparison_candidates": ("extra_candidate",)},
    ],
)
def test_changed_settings_never_inherit_a_benchmarked_outlook(change):
    config, jobs = _all("attila")
    config = replace(config, **change)
    jobs = [replace(job, **change) for job in jobs]
    assert runtime_outlook(config, jobs) == (
        "Completion time unknown · no matching measured query."
    )


def test_province_identity_and_joint_mode_matter_not_just_count():
    config, jobs = _all("rome2")
    job = jobs[0]
    changed = replace(job, provinces=(*job.holdings[:-1], "different_province"))
    assert "no matching" in runtime_outlook(config, [changed])
    independent = replace(config, joint=False)
    assert "no matching" in runtime_outlook(independent, make_jobs(independent)[0])


def test_explicit_province_lists_and_reordering_preserve_the_same_query_reference():
    config, jobs = _all("rome2")
    explicit = replace(config, provinces=tuple(reversed(jobs[0].holdings)), province="unused")
    assert runtime_outlook(explicit, make_jobs(explicit)[0]) == runtime_outlook(config, jobs)
    config, jobs = _all("shogun2", joint=False)
    assert runtime_outlook(config, list(reversed(jobs))) == runtime_outlook(config, jobs)


def test_limits_and_workers_do_not_relabel_the_reference_as_a_forecast():
    config, jobs = _all("attila", seconds=1, workers=16)
    assert "Proof time unknown" in runtime_outlook(config, jobs)
    text = runtime_details(config, jobs)
    assert "4 solver workers" in text and "1m 0s total" in text
    assert "worker count and time limit may differ" in text


def test_empty_and_unmatched_queries_have_useful_nonpredictive_information():
    config = RunConfig()
    assert runtime_outlook(config, []) == "No cases selected."
    assert "Select at least one province" in runtime_details(config, [])
    jobs = make_jobs(config)[0]
    assert "Completion time unknown" in runtime_outlook(config, jobs)
    assert "1 separate solver cases" in runtime_details(config, jobs)


def test_mixed_queries_do_not_receive_a_single_profile_estimate():
    config, jobs = _all("shogun2", joint=False)
    jobs[0] = replace(jobs[0], algorithm="highs")
    assert "no matching" in runtime_outlook(config, jobs)


def test_bundled_observations_retain_exact_source_hashes_outcomes_and_timings():
    for evidence in _evidence():
        path = Path(evidence.source_path)
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == evidence.source_sha256
        source = json.loads(raw)
        if "variants" in source:
            samples = source["variants"]["candidate"][evidence.request.game]["samples"]
        else:
            group = next(
                group
                for group in source["groups"]
                if group["request"]["joint"] == evidence.request.joint
            )
            samples = group["samples"]
        for row, original in zip(evidence.observations, samples, strict=True):
            assert row.wall_seconds == original["wall_seconds"]
            assert dict(row.statuses) == original["summary"]["statuses"]
            assert row.complete == (original["completion"] == "COMPLETE")
        assert evidence.holdings == tuple(
            sorted(tuple(sorted(case["provinces"])) for case in samples[0]["cases"])
        )


@pytest.mark.parametrize(
    ("statuses", "complete", "proved"),
    [
        ((("OPTIMAL", 1),), True, True),
        ((("INFEASIBLE", 1),), True, True),
        ((("OPTIMAL", 1), ("INFEASIBLE", 1)), True, True),
        ((("OPTIMAL", 1), ("FEASIBLE", 1)), True, False),
        ((("UNKNOWN", 1),), True, False),
        ((("OPTIMAL", 1),), False, False),
        ((("OPTIMAL", 0),), True, False),
        ((), True, False),
    ],
)
def test_only_completed_terminal_proofs_establish_an_observed_completion(
    statuses, complete, proved
):
    assert Observation(5, statuses, 60, complete).proved is proved
