"""Fair search budgets and safe incomplete-sample reporting without solver timing tests."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from tests.support.ui import result
from tools import holding_benchmark as benchmark
from tools import holding_benchmark_sensitivity as sensitivity
from twoptimizer.progress import ModelStats
from twoptimizer.requests import default_config


@pytest.mark.parametrize("game, count", [("attila", 62), ("rome2", 57), ("shogun2", 65)])
def test_joint_and_independent_workloads_share_one_configured_search_allowance(game, count):
    config = replace(default_config(game), provinces=("all",), workers=1)
    limits = benchmark.Limits(solver_seconds=12)
    independent = benchmark.jobs_for(config, limits)
    joint = benchmark.jobs_for(replace(config, joint=True), limits)
    assert len(independent) == count and len(joint) == 1
    assert all(job.seconds is not None for job in independent)
    assert sum(job.seconds for job in independent if job.seconds is not None) == pytest.approx(12)
    assert joint[0].seconds == 12
    assert {job.province for job in independent} == set(joint[0].holdings)


def test_matrix_keeps_only_supported_backends_and_distinguishes_ownership():
    rows = list(
        benchmark.request_matrix(("attila", "rome2", "shogun2"), ("pair",), ("cp-sat", "highs"), 1)
    )
    assert len(rows) == 12
    assert all(config.workers == 1 and len(config.holdings) == 2 for _, config in rows)
    assert {(config.game, config.algorithm, config.joint) for _, config in rows} == {
        (game, algorithm, joint)
        for game in ("attila", "rome2", "shogun2")
        for algorithm in ("cp-sat", "highs")
        for joint in (False, True)
    }


@pytest.mark.parametrize("algorithm", ["cbc", "scip", "portfolio", "scip-nonlinear", "glop"])
def test_retired_solver_names_are_rejected_before_benchmark_work(algorithm, tmp_path):
    with pytest.raises(ValueError, match="cp-sat or highs"):
        list(benchmark.request_matrix(("rome2",), ("pair",), (algorithm,), 1))
    with pytest.raises(SystemExit):
        benchmark.main(["--algorithm", algorithm, "--output", str(tmp_path / "never.json")])
    assert not (tmp_path / "never.json").exists()


class Runner:
    def __init__(self, *, blocking=False, changing_sources=False):
        self.process = SimpleNamespace(pid=123)
        self.stopped = False
        self.calls = 0
        self.blocking = blocking
        self.changing_sources = changing_sources

    async def run(self, config, on_log, on_progress):
        self.calls += 1
        on_progress("Building")
        model = ModelStats("Reference", 5, 4, stage="reference")
        on_progress(model)
        if self.blocking:
            while not self.stopped:
                await asyncio.sleep(0.001)
            return None
        payload = result(config)
        payload["timings"] = {"build_model_seconds": 0.1, "solve_and_check_seconds": 0.2}
        payload["source_files"] = {"source": str(self.calls) if self.changing_sources else "same"}
        payload["raw"]["model_complexity"] = [model.to_dict()]
        return payload

    async def stop(self):
        self.stopped = True


def _sample(monkeypatch, runner, *, memory=0, wall_seconds=1):
    monkeypatch.setattr(benchmark, "worker_memory", lambda pid: memory)
    config = replace(default_config("shogun2"), provinces=("jap_owari", "jap_mikawa"))
    return asyncio.run(
        benchmark.run_sample(
            config,
            benchmark.Limits(wall_seconds=wall_seconds, memory_mib=1),
            runner_factory=lambda: runner,
        )
    )


def test_completed_samples_keep_independent_case_counts_and_model_stage_totals(monkeypatch):
    runner = Runner()
    sample = _sample(monkeypatch, runner)
    assert sample["completion"] == "COMPLETE" and runner.stopped
    assert sample["requested_cases"] == sample["summary"]["completed_cases"] == 2
    assert sample["summary"]["all_optimal"]
    assert sample["summary"]["income_sum"] == pytest.approx(8365.4)
    assert sample["summary"]["reference_variables_sum"] == 10
    assert sample["summary"]["solver_variables_sum"] == 0
    assert sample["summary"]["phase_seconds"]["build_model_seconds"] == pytest.approx(0.2)
    assert sample["last_progress"] == "Building" and sample["last_model"]["variables"] == 5


@pytest.mark.parametrize("cause", ["memory", "wall", "source_change"])
def test_guarded_or_inconsistent_samples_never_publish_partial_totals(monkeypatch, cause):
    runner = Runner(blocking=cause != "source_change", changing_sources=cause == "source_change")
    sample = _sample(
        monkeypatch,
        runner,
        memory=2 * 1024**2 if cause == "memory" else 0,
        wall_seconds=0.01 if cause == "wall" else 1,
    )
    assert runner.stopped
    assert (
        sample["completion"]
        == {"memory": "MEMORY_LIMIT", "wall": "WALL_LIMIT", "source_change": "WORKER_ERROR"}[cause]
    )
    assert sample["summary"]["income_sum"] is None
    assert sample["summary"]["bound_sum"] is None
    assert not sample["summary"]["all_optimal"]


def test_missing_incumbents_and_bounds_are_not_replaced_by_zero(monkeypatch):
    sample = _sample(monkeypatch, Runner())
    sample["cases"][0].update(status="UNKNOWN", income=None, bound=None)
    summary = benchmark.summarize_sample(sample)
    assert summary["income_sum"] is None and summary["bound_sum"] is None
    assert summary["aggregate_gap_percent"] is None and not summary["all_optimal"]


def test_unavailable_native_timing_splits_remain_unknown(monkeypatch):
    sample = _sample(monkeypatch, Runner())
    summary = sample["summary"]
    assert summary["model_preparation_seconds"] == pytest.approx(0.2)
    assert summary["model_build_and_conversion_seconds"] is None
    assert summary["native_search_seconds"] is None
    grouped = benchmark.group_summary([sample])
    assert grouped["model_build_and_conversion_seconds_median"] is None
    assert grouped["native_search_seconds_median"] is None


@pytest.mark.parametrize(
    "flag, value", [("--repeat", "0"), ("--memory-mib", "nan"), ("--workers", "0")]
)
def test_invalid_resource_limits_stop_before_any_work(flag, value, tmp_path):
    with pytest.raises(SystemExit):
        benchmark.main([flag, value, "--output", str(tmp_path / "never.json")])
    assert not (tmp_path / "never.json").exists()


def test_highs_diagnostic_preserves_existing_cp_sat_report(monkeypatch, tmp_path):
    cp_report = tmp_path / "holding-performance-sensitivity-shogun2.json"
    cp_report.write_text("Existing CP-SAT observation")
    monkeypatch.setattr(benchmark, "worker_memory", lambda pid: 0)
    monkeypatch.setattr(sensitivity, "environment", lambda revision: {"revision": revision})

    async def run_sample(config, limits):
        assert config.algorithm == "highs"
        return await benchmark.run_sample(config, limits, runner_factory=Runner)

    monkeypatch.setattr(sensitivity, "run_sample", run_sample)
    assert (
        sensitivity.main(
            [
                "--game",
                "shogun2",
                "--algorithm",
                "highs",
                "--output-directory",
                str(tmp_path),
            ]
        )
        == 0
    )
    report = json.loads(
        (tmp_path / "holding-performance-sensitivity-shogun2-highs.json").read_text()
    )
    assert cp_report.read_text() == "Existing CP-SAT observation"
    assert report["groups"][0]["request"]["algorithm"] == "highs"
    assert report["groups"][0]["samples"][0]["requested_cases"] == 65
    assert report["groups"][0]["samples"][0]["completion"] == "COMPLETE"
