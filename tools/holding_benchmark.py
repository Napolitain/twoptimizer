"""Measure bounded, serial CLI/TUI worker workloads across supported campaigns.

Run with ``uv run --frozen python -m tools.holding_benchmark --output report.json``.
Configured solver allowances are equal per holding, not per independent province.
Some backends charge conversion against that allowance; native search is separate.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from time import perf_counter

from games.tw.resources import available_workers
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.runner import BatchRunner

PAIRS = {
    "attila": ("att_prov_thracia", "att_prov_macedonia"),
    "rome2": ("rome_main_italia", "rome_main_magna_graecia"),
    "shogun2": ("jap_owari", "jap_mikawa"),
}


@dataclass(frozen=True)
class Limits:
    solver_seconds: float = 6
    wall_seconds: float = 120
    memory_mib: float = 2048


def jobs_for(config: RunConfig, limits: Limits) -> list[RunConfig]:
    jobs, skipped = make_jobs(config)
    if skipped or not jobs:
        raise ValueError("Benchmark cases must expand without skipped or empty selections")
    return [replace(job, seconds=limits.solver_seconds / len(jobs)) for job in jobs]


def worker_memory(pid: int) -> int:
    """Linux per-process RSS high-water mark, including native solver allocations."""
    try:
        fields = dict(
            line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines()
        )
        return int(fields["VmHWM"].split()[0]) * 1024
    except OSError, KeyError, ValueError:
        return 0


async def monitor(runner, state, memory_bytes):
    while True:
        if runner.process is not None:
            state["peak_worker_rss_bytes"] = max(
                state["peak_worker_rss_bytes"], worker_memory(runner.process.pid)
            )
            if state["peak_worker_rss_bytes"] > memory_bytes:
                state["completion"] = "MEMORY_LIMIT"
                await runner.stop()
                return
        await asyncio.sleep(0.05)


def case_record(result):
    return {
        "provinces": result["request"].get("provinces") or [result["request"]["province"]],
        "status": result["solver"]["status"],
        "income": result["income"],
        "bound": result["solver"]["bound"],
        "gap_percent": result["gap_percent"],
        "solver_seconds": result["solver"]["seconds"],
        "solver_timings": result["solver"].get("timings", {}),
        "effective_workers": result["solver"].get("workers"),
        "timings": result["timings"],
        "model_complexity": result["raw"].get("model_complexity", []),
    }


async def run_sample(config, limits, *, runner_factory=BatchRunner):
    started = perf_counter()
    jobs = jobs_for(config, limits)
    runner = runner_factory()
    state = {
        "completion": "COMPLETE",
        "peak_worker_rss_bytes": 0,
        "requested_cases": len(jobs),
        "solver_seconds_per_case": limits.solver_seconds / len(jobs),
        "total_configured_solver_seconds": limits.solver_seconds,
        "cases": [],
        "source_files": {},
        "last_progress": None,
        "last_model": None,
    }

    def progress(event):
        key = "last_model" if isinstance(event, ModelStats) else "last_progress"
        state[key] = event.to_dict() if isinstance(event, ModelStats) else str(event)

    watcher = asyncio.create_task(monitor(runner, state, limits.memory_mib * 1024**2))
    try:
        async with asyncio.timeout(limits.wall_seconds):
            await _run_jobs(runner, jobs, state, progress)
    except TimeoutError:
        state["completion"] = "WALL_LIMIT"
    except Exception as error:
        if state["completion"] == "COMPLETE":
            state["completion"] = "WORKER_ERROR"
        state["error"] = f"{type(error).__name__}: {error}"
    finally:
        if runner.process is not None:
            state["peak_worker_rss_bytes"] = max(
                state["peak_worker_rss_bytes"], worker_memory(runner.process.pid)
            )
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
        await runner.stop()
    state["wall_seconds"] = perf_counter() - started
    state["summary"] = summarize_sample(state)
    return state


async def _run_jobs(runner, jobs, state, progress):
    for job in jobs:
        result = await runner.run(job, lambda _: None, progress)
        if result is None:
            if state["completion"] == "COMPLETE":
                state["completion"] = "INTERRUPTED"
            return
        sources = result["source_files"]
        if state["source_files"] and state["source_files"] != sources:
            raise RuntimeError("Source files changed during the benchmark sample")
        state["source_files"] = sources
        state["cases"].append(case_record(result))


def _total(cases, key):
    values = [case[key] for case in cases]
    return (
        sum(values) if values and all(v is not None and math.isfinite(v) for v in values) else None
    )


def _model_totals(cases):
    result = {}
    for stage in ("reference", "solver"):
        stage_models = [
            [model for model in case["model_complexity"] if model["stage"] == stage]
            for case in cases
        ]
        for field in ("variables", "constraints"):
            result[f"{stage}_{field}_sum"] = sum(
                max((model[field] for model in models), default=0) for models in stage_models
            )
    return result


def summarize_sample(sample):
    cases = sample["cases"]
    complete = sample["completion"] == "COMPLETE" and len(cases) == sample["requested_cases"]
    statuses = Counter(case["status"] for case in cases)
    phase_seconds = Counter()
    solver_timings = Counter()
    for case in cases:
        phase_seconds.update(case["timings"])
        solver_timings.update(case["solver_timings"])
    incomes = _total(cases, "income") if complete else None
    bound = _total(cases, "bound") if complete else None
    return {
        "completed_cases": len(cases),
        "statuses": dict(statuses),
        "all_optimal": complete and set(statuses) == {"OPTIMAL"},
        "income_sum": incomes,
        "bound_sum": bound,
        "aggregate_gap_percent": (
            100 * max(0, bound - incomes) / max(1, abs(bound))
            if incomes is not None and bound is not None
            else None
        ),
        "phase_seconds": dict(phase_seconds),
        "solver_seconds": sum(case["solver_seconds"] for case in cases),
        "solver_timings": dict(solver_timings),
        "model_preparation_seconds": phase_seconds["build_model_seconds"] if cases else None,
        "model_build_and_conversion_seconds": (
            phase_seconds["build_model_seconds"] + solver_timings["model_conversion_seconds"]
            if cases and all("model_conversion_seconds" in case["solver_timings"] for case in cases)
            else None
        ),
        "native_search_seconds": (
            solver_timings["search_seconds"]
            if cases and all("search_seconds" in case["solver_timings"] for case in cases)
            else None
        ),
        "effective_worker_counts": sorted(
            {case["effective_workers"] for case in cases if case["effective_workers"] is not None}
        ),
        **_model_totals(cases),
    }


def request_matrix(games, sizes, algorithms, workers):
    for game in games:
        for size in sizes:
            for algorithm in algorithms:
                if algorithm in {"portfolio", "scip-nonlinear"} and game != "rome2":
                    continue
                for joint in (False, True):
                    yield (
                        size,
                        replace(
                            default_config(game),
                            provinces=PAIRS[game] if size == "pair" else ("all",),
                            joint=joint,
                            algorithm=algorithm,
                            workers=workers,
                        ),
                    )


def environment(revision=None):
    def optional(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_model": next(
            (
                line.split(":", 1)[1].strip()
                for line in (optional("/proc/cpuinfo") or "").splitlines()
                if line.startswith("model name")
            ),
            None,
        ),
        "available_workers": available_workers(),
        "logical_cpus": os.cpu_count(),
        "cpu_quota": optional("/sys/fs/cgroup/cpu.max"),
        "memory_limit_bytes": optional("/sys/fs/cgroup/memory.max"),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("ortools", "pyscipopt", "numpy", "textual")
        },
        "lock_sha256": hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_revision": revision
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    }


def group_summary(samples):
    complete = all(sample["completion"] == "COMPLETE" for sample in samples)
    search = [sample["summary"]["native_search_seconds"] for sample in samples]
    build = [sample["summary"]["model_build_and_conversion_seconds"] for sample in samples]
    return {
        "repeats": len(samples),
        "completion_counts": dict(Counter(sample["completion"] for sample in samples)),
        "wall_seconds_min": min(sample["wall_seconds"] for sample in samples),
        "wall_seconds_median": median(sample["wall_seconds"] for sample in samples),
        "wall_seconds_max": max(sample["wall_seconds"] for sample in samples),
        "peak_worker_rss_mib_max": max(sample["peak_worker_rss_bytes"] for sample in samples)
        / 1024**2,
        "all_repeats_optimal": all(sample["summary"]["all_optimal"] for sample in samples),
        "model_build_and_conversion_seconds_median": (
            median(build) if complete and all(value is not None for value in build) else None
        ),
        "native_search_seconds_median": (
            median(search) if complete and all(value is not None for value in search) else None
        ),
    }


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game", action="append", choices=tuple(PAIRS))
    cli.add_argument("--size", action="append", choices=("pair", "all"))
    cli.add_argument(
        "--algorithm",
        action="append",
        choices=("cp-sat", "cbc", "scip", "portfolio", "scip-nonlinear"),
    )
    cli.add_argument("--repeat", type=int, default=2)
    cli.add_argument("--workers", type=int, default=None, help="Default: machine allocation")
    cli.add_argument(
        "--solver-seconds",
        "--search-seconds",
        dest="solver_seconds",
        type=float,
        default=6,
        help="Total configured solver allowance; some backends include native conversion",
    )
    cli.add_argument("--wall-seconds", type=float, default=120)
    cli.add_argument("--memory-mib", type=float, default=2048)
    cli.add_argument("--output", type=Path, required=True)
    cli.add_argument("--revision", help="Source commit when running an installed wheel outside Git")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    values = (args.repeat, args.solver_seconds, args.wall_seconds, args.memory_mib)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        cli.error("Repeat count and all resource limits must be finite and positive")
    if args.workers is not None and args.workers < 1:
        cli.error("Workers must be positive or omitted")
    if not Path("/proc/self/status").exists():
        cli.error("This benchmark requires Linux /proc for its worker memory guard")
    limits = Limits(args.solver_seconds, args.wall_seconds, args.memory_mib)
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "environment": environment(args.revision),
        "limits": vars(limits),
        "method": [
            "Serial samples; fresh BatchRunner worker per sample, reused across independent cases.",
            "No RunSession/proof reuse or instrumentation; ordinary Python/native solver build.",
            "Samples include cold worker startup; filesystem caches may be warm on later runs.",
            "Equal total configured solver allowance per holding, split across independent cases.",
            "Solver allowances may include conversion; actual native search time is separate.",
            "Separate wall/RSS guards cover preparation, conversion, search and validation.",
            "RSS is Linux worker VmHWM sampled every 50ms; guard can overshoot between samples.",
            "Independent totals describe separate hypothetical realms, not a legal joint layout.",
            "Model counts sum largest observed formulation per stage/case; stages are not added.",
            "Unavailable build/search splits remain null; raw phase/timing keys are retained.",
        ],
        "groups": [],
    }
    matrix = request_matrix(
        args.game or tuple(PAIRS),
        args.size or ("pair", "all"),
        args.algorithm or ("cp-sat",),
        args.workers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for size, config in matrix:
        group = {"size": size, "request": config.to_dict(), "samples": []}
        report["groups"].append(group)
        for repetition in range(args.repeat):
            sample = asyncio.run(run_sample(config, limits))
            group["samples"].append(sample)
            group["summary"] = group_summary(group["samples"])
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
            print(
                f"{config.game} {size} {config.algorithm} "
                f"{'joint' if config.joint else 'independent'} "
                f"repeat {repetition + 1}: {sample['completion']} {sample['wall_seconds']:.3f}s "
                f"{sample['summary']['statuses']}",
                flush=True,
            )
    return report


if __name__ == "__main__":
    main()
