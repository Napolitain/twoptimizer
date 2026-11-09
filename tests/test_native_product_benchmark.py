"""Fresh-process experiment selection and guard accounting without native search."""

import json
import sys
from types import SimpleNamespace

import pytest

from tools import native_product_benchmark as benchmark


def arguments(tmp_path, *extra):
    return benchmark.parser().parse_args(
        [
            "--baseline-python",
            sys.executable,
            "--native-python",
            sys.executable,
            "--output",
            str(tmp_path / "report.json"),
            *extra,
        ]
    )


def test_paired_matrix_keeps_limits_seeds_and_alternates_order(tmp_path):
    rows = list(benchmark.jobs(arguments(tmp_path)))
    assert len(rows) == 32
    for game in benchmark.GAMES:
        for scope in ("single", "all"):
            pair = [row for row in rows if (row["game"], row["scope"]) == (game, scope)]
            assert {row["seed"] for row in pair} == {0, 1}
            assert pair[0]["variant"] == pair[3]["variant"]
            assert pair[1]["variant"] == pair[2]["variant"]
            assert {row["workers"] for row in pair} == {4}
            expected = 10 if scope == "single" else benchmark.JOINT_SECONDS[game]
            assert {row["seconds"] for row in pair} == {expected}


def test_python_environment_symlink_path_is_preserved(tmp_path):
    executable = tmp_path / "installed-env" / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.symlink_to(sys.executable)
    args = arguments(tmp_path, "--baseline-python", str(executable), "--variants", "default")
    benchmark.validate_args(benchmark.parser(), args)
    assert {row["python"] for row in benchmark.jobs(args)} == {str(executable)}
    assert executable.resolve() != executable


@pytest.mark.parametrize(
    "game,count", [("attila", 62), ("rome2", 57), ("shogun2", 65), ("three_kingdoms", 70)]
)
def test_worker_requests_use_normal_named_single_and_joint_scenarios(game, count):
    job = {"game": game, "seconds": 10, "workers": 4, "seed": 1, "scope": "single"}
    single = benchmark.worker_request(job)
    joint = benchmark.worker_request({**job, "scope": "all"})
    assert single["province"] == benchmark.SINGLE_PROVINCES[game]
    assert not single["joint"] and joint["joint"]
    assert len(joint["provinces"]) == count
    assert single["seconds"] == joint["seconds"] == 10
    assert single["workers"] == joint["workers"] == 4


def test_native_selector_leaves_recursive_local_preparation_on_default(monkeypatch):
    calls = []

    class Economy:
        def __init__(self, local=False):
            self.local = local

        def optimize(self, *, native_products=False):
            calls.append(native_products)
            if not self.local:
                Economy(True).optimize()
            return native_products

    monkeypatch.setattr(
        benchmark.importlib, "import_module", lambda name: SimpleNamespace(Economy=Economy)
    )
    benchmark.install_selector("three_kingdoms")
    assert Economy().optimize() is True
    assert calls == [True, False]
    assert Economy(True).optimize() is True  # Nesting state resets after the outer call.


def test_default_worker_never_imports_or_injects_experimental_selector(monkeypatch, tmp_path):
    job = {"variant": "default", "game": "rome2", "seed": 1}
    job_path = tmp_path / "job.json"
    benchmark.write_json(job_path, job)
    monkeypatch.setattr(benchmark, "worker_environment", lambda: {"python": "test"})
    monkeypatch.setattr(benchmark, "worker_request", lambda job: {"algorithm": "cp-sat"})
    seeds = []
    monkeypatch.setattr(benchmark, "install_seed", seeds.append)

    def unexpected(game):
        raise AssertionError("The old baseline API must receive no experimental arguments")

    monkeypatch.setattr(benchmark, "install_selector", unexpected)
    calls = []
    fake_worker = SimpleNamespace(run_case=lambda *args: calls.append(args) or 0)
    monkeypatch.setitem(sys.modules, "twoptimizer.worker", fake_worker)
    assert benchmark.worker_main(job_path) == 0
    assert seeds == [1] and len(calls) == 1
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["peak_worker_rss_bytes"] > 0


@pytest.mark.parametrize("guard", ["wall", "memory"])
def test_guards_stop_the_worker_and_preserve_failure_kind(monkeypatch, guard):
    process = SimpleNamespace(pid=123, returncode=None)
    process.poll = lambda: process.returncode
    clock = iter((0, 2, 3))
    monkeypatch.setattr(benchmark.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(
        benchmark, "memory_bytes", lambda pid: 2 * 1024**2 if guard == "memory" else 0
    )
    monkeypatch.setattr(
        benchmark, "stop_process", lambda worker: setattr(worker, "returncode", -15)
    )
    result = benchmark.monitor(process, benchmark.Guards(wall_seconds=1, memory_mib=1))
    assert result["completion"] == ("MEMORY_LIMIT" if guard == "memory" else "WALL_LIMIT")
    assert result["exit_code"] == -15


def test_native_failure_and_malformed_result_remain_inspectable(tmp_path):
    (tmp_path / "worker.log").write_text("Native model rejected")
    (tmp_path / "result.json").write_text("[]")
    record = benchmark.finish_record(
        {"completion": "COMPLETE", "exit_code": 1, "peak_worker_rss_bytes": 0}, tmp_path
    )
    assert record["completion"] == "WORKER_ERROR"
    assert "object" in record["result"]["error"]
    assert "Native model rejected" in record["log_tail"]


def test_result_preserves_full_native_counts_and_bound_preparation_details():
    solver = {
        "status": "FEASIBLE",
        "bound": 100,
        "model_stats": {"formulation": "native_products", "native_product_count": 17},
        "joint_bound_search": {"components": 4, "upper_bound": 100},
    }
    record = benchmark.result_record(
        {
            "request": {},
            "solver": solver,
            "income": 90,
            "gap_percent": 10,
            "buildings": [],
            "source_files": {"engine": "hash"},
            "assumptions": "Declared snapshot",
            "raw": {},
        }
    )
    assert record["actual_model_stats"] == solver["model_stats"]
    assert record["solver"]["joint_bound_search"] == solver["joint_bound_search"]
    assert record["source_files"] == {"engine": "hash"}


def test_controller_writes_each_outcome_before_starting_next_worker(monkeypatch, tmp_path):
    output = tmp_path / "report.json"
    observed = []

    def run(job, directory, guards):
        if observed:
            assert len(json.loads(output.read_text())["runs"]) == len(observed)
        observed.append(job["variant"])
        return {"completion": "WORKER_ERROR", "wall_seconds": 1, "job": job}

    monkeypatch.setattr(benchmark, "run_job", run)
    assert (
        benchmark.main(
            [
                "--baseline-python",
                sys.executable,
                "--native-python",
                sys.executable,
                "--game",
                "rome2",
                "--scope",
                "single",
                "--repeat",
                "1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert observed == ["default", "native"]
    assert [r["completion"] for r in json.loads(output.read_text())["runs"]] == ["WORKER_ERROR"] * 2


@pytest.mark.parametrize(
    "options", [{"memory_mib": 4097}, {"wall_seconds": float("nan")}, {"memory_mib": 0}]
)
def test_guard_limits_reject_unsafe_or_invalid_requests(options):
    with pytest.raises(ValueError):
        benchmark.Guards(**options)


@pytest.mark.parametrize("game", benchmark.GAMES)
@pytest.mark.parametrize("scope,count", [("pair", 2), ("eight", 8)])
def test_supplemental_scopes_are_joint_named_holdings_with_reproducible_membership(
    game, scope, count
):
    selected = benchmark.scope_holdings(game, scope)
    assert selected is not None
    assert len(selected) == len(set(selected)) == count
    assert selected[:2] == benchmark.PAIR_PROVINCES[game]
    assert benchmark.scope_holdings(game, scope) == selected
    request = benchmark.worker_request(
        {"game": game, "scope": scope, "seconds": 15, "workers": 4, "seed": 0}
    )
    assert request["joint"] is True
    assert set(request["provinces"]) == set(selected)
    assert request["seconds"] == 15
    if game == "rome2":
        assert request["provinces"][:2] == ["rome_main_italia", "rome_main_magna_graecia"]
        assert not {"coastal", "inland", "grain"} & set(selected)


def test_joint_override_changes_all_joint_scopes_but_keeps_single_allowance(tmp_path):
    args = arguments(
        tmp_path,
        "--game",
        "rome2",
        "--joint-seconds",
        "15",
        "--scope",
        "single",
        "--scope",
        "pair",
        "--scope",
        "eight",
        "--scope",
        "all",
    )
    benchmark.validate_args(benchmark.parser(), args)
    rows = list(benchmark.jobs(args))
    assert {row["seconds"] for row in rows if row["scope"] == "single"} == {10}
    assert {row["seconds"] for row in rows if row["scope"] != "single"} == {15}
    assert len(rows) == 16


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_invalid_joint_override_is_rejected_before_worker_launch(tmp_path, value):
    args = arguments(tmp_path, "--joint-seconds", value)
    with pytest.raises(SystemExit):
        benchmark.validate_args(benchmark.parser(), args)
