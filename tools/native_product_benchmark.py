"""Compare installed default/native CP-SAT formulations in guarded, fresh workers.

Copy this standalone file outside the checkout and run it with the two installed
Python paths. The controller uses only the standard library. Each isolated child
uses the normal application worker and independent engine validation. Experimental
selectors and seeded solver wrappers exist only in that child process.
"""

import argparse
import functools
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
import platform
import resource
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

GAMES = ("attila", "rome2", "shogun2", "three_kingdoms")
SINGLE_PROVINCES = {
    "attila": "att_prov_thracia",
    "rome2": "rome_main_italia",
    "shogun2": "jap_owari",
    "three_kingdoms": "3k_main_province_yingchuan",
}
PAIR_PROVINCES = {
    "attila": ("att_prov_thracia", "att_prov_macedonia"),
    "rome2": ("rome_main_italia", "rome_main_magna_graecia"),
    "shogun2": ("jap_owari", "jap_mikawa"),
    "three_kingdoms": ("3k_main_province_yingchuan", "3k_main_province_changan"),
}
JOINT_SECONDS = {"attila": 60, "rome2": 60, "shogun2": 20, "three_kingdoms": 30}


@dataclass(frozen=True)
class Guards:
    wall_seconds: float = 180
    memory_mib: float = 4096

    def __post_init__(self):
        if any(not math.isfinite(v) or v <= 0 for v in (self.wall_seconds, self.memory_mib)):
            raise ValueError("Wall and memory limits must be finite and positive")
        if self.memory_mib > 4096:
            raise ValueError("Worker memory guard must not exceed 4096 MiB")


def install_seed(seed):
    """Apply the paired experimental seed immediately before every native solve."""
    from ortools.sat.python import cp_model

    original = cp_model.CpSolver.solve

    def solve(
        self: cp_model.CpSolver,
        model: cp_model.CpModel,
        solution_callback: cp_model.CpSolverSolutionCallback | None = None,
    ) -> cp_model.CpSolverStatus:
        self.parameters.random_seed = seed
        return original(self, model, solution_callback)

    cp_model.CpSolver.solve = solve


def install_selector(game):
    """Switch the outer solve only; nested local seed solves keep their defaults."""
    if game == "attila":
        _install_attila()
        return
    model = importlib.import_module(f"games.tw.{game}.model")
    original = model.Economy.optimize
    depth = 0

    @functools.wraps(original)
    def optimize(economy, *args, **kwargs):
        nonlocal depth
        if depth == 0:
            kwargs["native_products"] = True
        depth += 1
        try:
            return original(economy, *args, **kwargs)
        finally:
            depth -= 1

    model.Economy.optimize = optimize


def _install_attila():
    from games.tw.attila.native_experiment import with_native_products
    from twoptimizer.attila_session import AttilaSession, PreparedAttila
    from twoptimizer.models import RunConfig

    original = AttilaSession.prepare

    def prepare(self: AttilaSession, config: RunConfig) -> PreparedAttila:
        prepared = original(self, config)
        snapshot = replace(prepared.snapshot, model=with_native_products(prepared.snapshot.model))
        return replace(prepared, snapshot=snapshot)

    AttilaSession.prepare = prepare


def scope_holdings(game, scope):
    """Use declared pairs plus the first six other named catalogue provinces."""
    if scope == "single":
        return None
    if scope == "all":
        return ("all",)
    pair = PAIR_PROVINCES[game]
    if scope == "pair":
        return pair
    if scope != "eight":
        raise ValueError("Unknown benchmark holding scope")
    from twoptimizer.holdings import named_province_choices

    extras = tuple(key for _, key in named_province_choices(game) if key not in pair)[:6]
    if len(extras) != 6:
        raise ValueError("Eight-province benchmark requires six additional named provinces")
    return (*pair, *extras)


def worker_request(job):
    from twoptimizer.requests import default_config, make_jobs

    config = replace(
        default_config(job["game"]),
        province=SINGLE_PROVINCES[job["game"]],
        provinces=scope_holdings(job["game"], job["scope"]),
        joint=job["scope"] != "single",
        algorithm="cp-sat",
        seconds=job["seconds"],
        workers=job["workers"],
    )
    if job["game"] == "attila":
        config = replace(config, attila=replace(config.attila, seed=job["seed"]))
    jobs, skipped = make_jobs(config)
    if skipped or len(jobs) != 1:
        raise ValueError("Each experimental worker must receive exactly one complete case")
    return jobs[0].to_dict()


def worker_environment():
    import twoptimizer

    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "prefix": sys.prefix,
        "package_path": str(Path(twoptimizer.__file__).resolve()),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("napolitain-twoptimizer", "ortools", "numpy", "textual")
        },
    }


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def worker_main(job_path):
    """The caller guards the complete process, including import and model building."""
    job = json.loads(job_path.read_text())
    directory = job_path.parent
    metadata = {"environment": worker_environment(), "request": worker_request(job)}
    write_json(directory / "metadata.json", metadata)
    install_seed(job["seed"])
    if job["variant"] == "native":
        install_selector(job["game"])
    request_path = directory / "request.json"
    write_json(request_path, metadata["request"])
    from twoptimizer.worker import run_case

    status = run_case(request_path, directory / "result.json")
    metadata["peak_worker_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    write_json(directory / "metadata.json", metadata)
    return status


def memory_bytes(pid):
    try:
        rows = dict(
            line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines()
        )
        return int(rows["VmHWM"].split()[0]) * 1024
    except OSError, KeyError, ValueError:
        return 0


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    except ProcessLookupError:
        process.wait(timeout=5)


def monitor(process, guards, started=None):
    started = time.perf_counter() if started is None else started
    peak, outcome = 0, "COMPLETE"
    try:
        while process.poll() is None:
            peak = max(peak, memory_bytes(process.pid))
            if peak > guards.memory_mib * 1024**2:
                outcome = "MEMORY_LIMIT"
                break
            if time.perf_counter() - started >= guards.wall_seconds:
                outcome = "WALL_LIMIT"
                break
            time.sleep(0.05)
    finally:
        stop_process(process)
    return {
        "completion": outcome,
        "exit_code": process.returncode,
        "wall_seconds": time.perf_counter() - started,
        "peak_worker_rss_bytes": peak,
    }


def read_json(path):
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Worker JSON must be an object")
        return value
    except (ValueError, OSError) as error:
        return {"error": f"Cannot read worker JSON: {error}"}


def result_record(result):
    if result is None or "error" in result:
        return result
    return {
        "request": result["request"],
        "status": result["solver"]["status"],
        "income": result["income"],
        "bound": result["solver"]["bound"],
        "gap_percent": result["gap_percent"],
        "solver": result["solver"],
        "actual_model_stats": result["solver"].get("model_stats", {}),
        "timings": result.get("timings", {}),
        "model_complexity": result["raw"].get("model_complexity", []),
        "search_measurements": result["raw"].get("search_measurements"),
        "building_count": len(result["buildings"]),
        "layout_sha256": hashlib.sha256(
            json.dumps(result["buildings"], sort_keys=True).encode()
        ).hexdigest(),
        "source_files": result["source_files"],
        "assumptions": result["assumptions"],
    }


def finish_record(record, directory):
    metadata = read_json(directory / "metadata.json")
    record["metadata"] = metadata
    if metadata and "peak_worker_rss_bytes" in metadata:
        record["peak_worker_rss_bytes"] = max(
            record["peak_worker_rss_bytes"], metadata["peak_worker_rss_bytes"]
        )
    result = read_json(directory / "result.json")
    try:
        record["result"] = result_record(result)
    except (KeyError, TypeError) as error:
        result = {"error": f"Malformed worker result: {error}"}
        record["result"] = result
    if record["completion"] == "COMPLETE" and (
        record["exit_code"] != 0 or result is None or "error" in result
    ):
        record["completion"] = "WORKER_ERROR"
    log = directory / "worker.log"
    if record["completion"] != "COMPLETE" and log.exists():
        with log.open("rb") as stream:
            stream.seek(max(0, log.stat().st_size - 8000))
            record["log_tail"] = stream.read().decode(errors="replace")
    return record


def run_job(job, directory, guards):
    directory.mkdir(parents=True, exist_ok=False)
    job_path = directory / "job.json"
    write_json(job_path, job)
    command = [job["python"], "-I", str(Path(__file__).resolve()), "--worker", str(job_path)]
    record = {"job": job, "command": command, "artifacts": str(directory)}
    started = time.perf_counter()
    try:
        with (directory / "worker.log").open("wb") as log:
            process = subprocess.Popen(
                command, cwd=directory, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
            )
            record.update(monitor(process, guards, started))
    except OSError as error:
        record.update(
            completion="WORKER_ERROR",
            exit_code=None,
            peak_worker_rss_bytes=0,
            wall_seconds=time.perf_counter() - started,
            error=str(error),
        )
    return finish_record(record, directory)


def case_allowance(args, game, scope):
    if scope == "single":
        return args.single_seconds
    return JOINT_SECONDS[game] if args.joint_seconds is None else args.joint_seconds


def jobs(args):
    for repeat in range(args.repeat):
        for game_index, game in enumerate(args.game or GAMES):
            for scope_index, scope in enumerate(args.scope or ("single", "all")):
                variants = list(args.variants)
                if (repeat + game_index + scope_index) % 2:
                    variants.reverse()
                for variant in variants:
                    yield {
                        "game": game,
                        "scope": scope,
                        "variant": variant,
                        "repeat": repeat + 1,
                        "seed": args.seed + repeat,
                        "workers": args.workers,
                        "seconds": case_allowance(args, game, scope),
                        "python": str(getattr(args, variant + "_python").absolute()),
                    }


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--baseline-python", "--default-python", dest="default_python", type=Path)
    cli.add_argument("--native-python", type=Path)
    cli.add_argument(
        "--variants", nargs="+", choices=("default", "native"), default=("default", "native")
    )
    cli.add_argument("--game", action="append", choices=GAMES)
    cli.add_argument("--scope", action="append", choices=("single", "pair", "eight", "all"))
    cli.add_argument("--repeat", type=int, default=2)
    cli.add_argument("--seed", type=int, default=0)
    cli.add_argument("--workers", type=int, default=4)
    cli.add_argument("--single-seconds", type=float, default=10)
    cli.add_argument(
        "--joint-seconds",
        type=float,
        help="Override the game-specific solver allowance for pair/eight/all holdings",
    )
    cli.add_argument("--wall-seconds", type=float, default=180)
    cli.add_argument("--memory-mib", type=float, default=4096)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--artifacts", type=Path)
    return cli


def validate_args(cli, args):
    try:
        guards = Guards(args.wall_seconds, args.memory_mib)
    except ValueError as error:
        cli.error(str(error))
    if args.repeat < 1 or args.workers < 1 or args.seed < 0:
        cli.error("Repeat/workers must be positive and seed must be nonnegative")
    allowances = (args.single_seconds, args.joint_seconds)
    if any(v is not None and (not math.isfinite(v) or v <= 0) for v in allowances):
        cli.error("Solver allowances must be finite and positive")
    if len(set(args.variants)) != len(args.variants):
        cli.error("Select each variant at most once")
    for variant in args.variants:
        executable = getattr(args, variant + "_python")
        if executable is None or not executable.is_file():
            cli.error(f"Provide an installed Python executable for {variant}")
    if args.output.exists():
        cli.error("Output exists; choose a new report path")
    if not Path("/proc/self/status").exists():
        cli.error("Linux /proc is required for worker memory guards")
    return guards


def main(argv=None):
    values = sys.argv[1:] if argv is None else argv
    if len(values) == 2 and values[0] == "--worker":
        return worker_main(Path(values[1]))
    cli = parser()
    args = cli.parse_args(values)
    guards = validate_args(cli, args)
    args.output = args.output.resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    directory = (args.artifacts or args.output.with_suffix("")).resolve()
    report = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "guards": {"wall_seconds": guards.wall_seconds, "memory_mib": guards.memory_mib},
        "method": [
            "Sequential fresh workers; imports/startup/preparation included in wall time.",
            "Explicit installed Python environments; isolated mode excludes checkout imports.",
            "Paired seeds increase per repeat; order alternates when both variants are selected.",
            "Every CP-SAT solve receives the paired seed; other native parameters are unchanged.",
            "Native outer solve; local seed searches retain default formulation.",
            "Normal requests, preparation and independent result validation remain enabled.",
            "Supplemental pair/eight scopes use fixed pairs plus six other catalogue provinces.",
            "Solver limits may include conversion; process wall time and RSS guarded separately.",
            "Worker RSS sampled every 50ms and final Linux high-water RSS recorded when available.",
            "Failures retained; unfinished cases never count as optimal or zero income.",
        ],
        "runs": [],
    }
    for index, job in enumerate(jobs(args), 1):
        name = f"{index:03d}-{job['game']}-{job['scope']}-{job['variant']}-seed{job['seed']}"
        record = run_job(job, directory / name, guards)
        report["runs"].append(record)
        write_json(args.output, report)
        print(f"{name}: {record['completion']} {record['wall_seconds']:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
