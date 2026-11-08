"""Cooperative process cancellation retains validated results and case ownership."""

import asyncio
import sys
from pathlib import Path

import pytest

from twoptimizer import runner as runner_module
from twoptimizer.models import RunConfig
from twoptimizer.progress import SearchStats
from twoptimizer.runner import BatchRunner, CaseRunner

CONTROLLED_WORKER = """
import os
import time
from types import SimpleNamespace
from tests.support.ui import result
from twoptimizer import worker
from twoptimizer.models import CaseResult

def solve(config, progress, cancellation):
    requested_before_search = cancellation.requested
    progress("Searching controlled case")
    if config.faction == "ignore":
        while True:
            time.sleep(0.01)
    if config.faction != "complete":
        while not cancellation.requested:
            time.sleep(0.01)
    if config.faction == "error":
        raise RuntimeError("Controlled failure after cancellation")
    if config.faction == "exit":
        os._exit(7)
    if config.faction == "malformed":
        return SimpleNamespace(to_dict=lambda: {"solver": {}})
    payload = result(config)
    payload["timings"] = {}
    payload["raw"]["requested_before_search"] = requested_before_search
    if config.faction == "FEASIBLE":
        payload["solver"].update(status="FEASIBLE", objective=100, bound=102)
        payload.update(income=100, gap_percent=100 / 51)
    if config.faction == "UNKNOWN":
        payload["solver"].update(status="UNKNOWN", objective=None, bound=None)
        payload.update(income=None, gap_percent=None, metrics={}, buildings=[])
    return CaseResult.from_dict(payload)

worker.solve_case = solve
raise SystemExit(worker.main())
"""


def install_worker(monkeypatch):
    """Keep real pipes and the worker protocol, replacing only the engine case."""
    launch = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        return await launch(sys.executable, "-c", CONTROLLED_WORKER, *args[3:], **kwargs)

    monkeypatch.setattr(runner_module.asyncio, "create_subprocess_exec", spawn)


@pytest.mark.parametrize("runner_type", [CaseRunner, BatchRunner])
@pytest.mark.parametrize("status", ["FEASIBLE", "UNKNOWN", "OPTIMAL"])
def test_cooperative_stop_retains_the_active_case_result(monkeypatch, runner_type, status):
    install_worker(monkeypatch)

    async def exercise():
        runner, searching = runner_type(), asyncio.Event()

        def progress(event):
            if event == "Searching controlled case":
                searching.set()

        task = asyncio.create_task(runner.run(RunConfig(faction=status), lambda _: None, progress))
        try:
            await asyncio.wait_for(searching.wait(), 5)
            await asyncio.wait_for(runner.request_stop(), 0.5)
            output = await asyncio.wait_for(task, 5)
            assert output["solver"]["status"] == status
            assert output["raw"]["cancellation"] == {
                "requested": True,
                "incumbent_retained": status != "UNKNOWN",
            }
            assert output["raw"]["requested_before_search"] is False
            if status == "FEASIBLE":
                assert output["income"] == output["solver"]["objective"] == 100
                assert output["solver"]["bound"] == 102
                assert output["gap_percent"] == pytest.approx(100 / 51)
                assert output["buildings"][0]["id"] == "market_4"
            elif status == "UNKNOWN":
                assert output["income"] is None and output["buildings"] == []
            assert runner.process is not None and runner.process.returncode is not None
            assert await runner.run(RunConfig(), lambda _: None) is None
        finally:
            await runner.stop()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.parametrize("runner_type", [CaseRunner, BatchRunner])
def test_requesting_stop_before_run_never_launches_a_worker(runner_type):
    async def exercise():
        runner = runner_type()
        await runner.request_stop()
        assert await runner.run(RunConfig(), lambda _: None) is None
        assert runner.process is None
        await runner.stop()

    asyncio.run(exercise())


@pytest.mark.parametrize("runner_type", [CaseRunner, BatchRunner])
@pytest.mark.parametrize("failure", ["error", "malformed", "exit"])
def test_cooperative_stop_does_not_hide_worker_or_validation_errors(
    monkeypatch, runner_type, failure
):
    install_worker(monkeypatch)

    async def exercise():
        runner, searching = runner_type(), asyncio.Event()
        task = asyncio.create_task(
            runner.run(RunConfig(faction=failure), lambda _: None, lambda _: searching.set())
        )
        try:
            await asyncio.wait_for(searching.wait(), 5)
            await runner.request_stop()
            with pytest.raises(RuntimeError):
                await asyncio.wait_for(task, 5)
            assert runner.process is not None and runner.process.returncode is not None
        finally:
            await runner.stop()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.parametrize("runner_type", [CaseRunner, BatchRunner])
def test_force_stop_remains_available_after_a_cooperative_request(monkeypatch, runner_type):
    install_worker(monkeypatch)

    async def exercise():
        runner, searching = runner_type(), asyncio.Event()
        task = asyncio.create_task(
            runner.run(RunConfig(faction="ignore"), lambda _: None, lambda _: searching.set())
        )
        try:
            await asyncio.wait_for(searching.wait(), 5)
            await runner.request_stop()
            assert not task.done()
            await runner.stop()
            assert await asyncio.wait_for(task, 5) is None
            assert runner.process is not None and runner.process.returncode is not None
        finally:
            await runner.stop()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.parametrize("runner_type", [CaseRunner, BatchRunner])
def test_cooperative_stop_during_process_launch_is_not_lost(monkeypatch, runner_type):
    install_worker(monkeypatch)

    async def exercise():
        launching, release = asyncio.Event(), asyncio.Event()
        launch = asyncio.create_subprocess_exec

        async def spawn(*args, **kwargs):
            launching.set()
            await release.wait()
            return await launch(*args, **kwargs)

        monkeypatch.setattr(runner_module.asyncio, "create_subprocess_exec", spawn)
        runner = runner_type()
        task = asyncio.create_task(runner.run(RunConfig(faction="UNKNOWN"), lambda _: None))
        try:
            await asyncio.wait_for(launching.wait(), 5)
            await runner.request_stop()
            release.set()
            output = await asyncio.wait_for(task, 5)
            if runner_type is BatchRunner:
                assert output is None  # No request has been dispatched yet.
            else:
                assert output["solver"]["status"] == "UNKNOWN"
                assert output["raw"]["requested_before_search"] is True
            assert runner.process is not None and runner.process.returncode is not None
        finally:
            release.set()
            await runner.stop()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


def test_batch_reuse_keeps_marker_files_and_cancellation_requests_separate(monkeypatch):
    install_worker(monkeypatch)
    temporary_directory = runner_module.TemporaryDirectory
    directories = []

    def directory(**kwargs):
        temporary = temporary_directory(**kwargs)
        directories.append(temporary.name)
        return temporary

    monkeypatch.setattr(runner_module, "TemporaryDirectory", directory)

    async def exercise():
        runner = BatchRunner()
        try:
            for _ in range(2):
                output = await asyncio.wait_for(
                    runner.run(RunConfig(faction="complete"), lambda _: None), 5
                )
                assert output["raw"]["requested_before_search"] is False
                assert "cancellation" not in output["raw"]
                assert not any(Path(path).exists() for path in directories)
            searching = asyncio.Event()
            task = asyncio.create_task(
                runner.run(RunConfig(faction="FEASIBLE"), lambda _: None, lambda _: searching.set())
            )
            await asyncio.wait_for(searching.wait(), 5)
            await runner.request_stop()
            output = await asyncio.wait_for(task, 5)
            assert output["income"] == 100
            assert output["raw"]["requested_before_search"] is False
            assert len(set(directories)) == 3
            assert not any(Path(path).exists() for path in directories)
        finally:
            await runner.stop()

    asyncio.run(exercise())


def test_real_joint_attila_worker_validates_and_retains_an_interrupted_incumbent():
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        province="att_prov_thracia",
        provinces=("att_prov_thracia", "att_prov_asia"),
        joint=True,
        research="all",
        workers=2,
        seconds=30,
    )

    async def exercise():
        runner, requests, observations = CaseRunner(), [], []

        def progress(event):
            if isinstance(event, SearchStats) and event.objective is not None:
                observations.append(event)
                if not requests:
                    requests.append(asyncio.create_task(runner.request_stop()))

        try:
            output = await asyncio.wait_for(runner.run(config, lambda _: None, progress), 45)
            await asyncio.gather(*requests)
            assert output["solver"]["status"] in {"FEASIBLE", "OPTIMAL"}
            assert output["raw"]["cancellation"]["incumbent_retained"] is True
            assert output["income"] >= observations[0].objective - 1e-5
            assert output["solver"]["bound"] >= output["income"] - 1e-5
            assert output["buildings"] and output["metrics"]["food_surplus"] >= 0
            assert output["source_files"]
            assert runner.process is not None and runner.process.returncode == 0
        finally:
            await runner.stop()

    asyncio.run(exercise())
