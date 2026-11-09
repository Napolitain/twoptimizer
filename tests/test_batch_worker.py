"""Sequential worker reuse preserves case ownership, progress and cancellation."""

import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import Select

from twoptimizer import runner as runner_module
from twoptimizer.errors import ApplicationError
from twoptimizer.export import export_session
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats
from twoptimizer.runner import BatchRunner
from twoptimizer.tui import OptimizerApp


def install_worker(monkeypatch, script):
    """Run a real pipe/process with controlled case behavior, not a fake transport."""
    launch = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        return await launch(sys.executable, "-c", script, "--batch", **kwargs)

    monkeypatch.setattr(runner_module.asyncio, "create_subprocess_exec", spawn)


CONTROLLED_WORKER = """
import signal
import time
from tests.support.ui import result
from twoptimizer import worker
from twoptimizer.models import CaseResult
from twoptimizer.progress import ModelStats

def solve(config, progress, *, cancellation=None, session=None):
    if config.faction == "runtime-error":
        raise RuntimeError("Controlled native failure")
    progress("Starting controlled case")
    progress(ModelStats("Test model", 5, 4, stage="solver"))
    if config.algorithm == "highs":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        progress("Blocking native case")
        while True:
            time.sleep(1)
    payload = result(config)
    payload["timings"] = {}
    payload["raw"]["model_complexity"] = [ModelStats("Test model", 5, 4, stage="solver").to_dict()]
    print("Native output without a newline", end="")
    return CaseResult.from_dict(payload)

worker.solve_case = solve
raise SystemExit(worker.main())
"""


def test_real_worker_reuses_pid_but_keeps_games_requests_and_models_independent(monkeypatch):
    directories = []
    temporary_directory = runner_module.TemporaryDirectory

    def directory(**kwargs):
        temporary = temporary_directory(**kwargs)
        directories.append(Path(temporary.name))
        return temporary

    monkeypatch.setattr(runner_module, "TemporaryDirectory", directory)
    original = RunConfig(
        game="shogun2",
        faction="oda",
        province="jap_owari",
        research="all",
        algorithm="cp-sat",
        workers=None,
        tax=35,
        town_wealth=125,
    )

    async def exercise():
        runner = BatchRunner()
        try:
            first = await runner.run(original, lambda _: None)
            process = runner.process
            assert process is not None and process.returncode is None
            with pytest.raises(ApplicationError, match="complete optimizer"):
                await runner.run(RunConfig(game="hoi4"), lambda _: None)
            configs = [
                RunConfig(algorithm="cp-sat", workers=1, seconds=1),
                replace(original, province="jap_sado", tax=25),
                original,
            ]
            for config in configs:
                events = []
                output = await runner.run(config, lambda _: None, events.append)
                assert output["request"] == config.to_dict()
                assert runner.process is process and process.returncode is None
                assert output["timings"]["worker_dispatch_seconds"] >= 0
                assert "worker_startup_seconds" not in output["timings"]
                assert [e.to_dict() for e in events if isinstance(e, ModelStats)] == output["raw"][
                    "model_complexity"
                ]
            assert first["timings"]["worker_startup_seconds"] >= 0
            assert first["solver"]["status"] == output["solver"]["status"] == "OPTIMAL"
            for key in ("income", "metrics", "source_files"):
                assert output[key] == first[key]
            assert output["solver"]["objective"] == first["solver"]["objective"]
            assert output["solver"]["bound"] == first["solver"]["bound"]
            assert not any(path.exists() for path in directories)
        finally:
            await runner.stop()
        assert process.returncode is not None and process.stdin.is_closing()
        await runner.stop()

    asyncio.run(exercise())


def test_serialized_runtime_error_does_not_kill_a_healthy_worker(monkeypatch):
    install_worker(monkeypatch, CONTROLLED_WORKER)

    async def exercise():
        runner = BatchRunner()
        try:
            with pytest.raises(RuntimeError, match="Controlled native failure"):
                await runner.run(RunConfig(faction="runtime-error"), lambda _: None)
            process = runner.process
            assert process is not None
            logs = []
            output = await asyncio.wait_for(runner.run(RunConfig(), logs.append), 5)
            assert output["income"] == 4182.7
            assert "Native output without a newline" in logs and "" not in logs
            assert runner.process is process and process.returncode is None
        finally:
            await runner.stop()

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", ["exit", "empty", "wrong-id", "invalid-result"])
def test_broken_transport_fails_promptly_and_is_reaped(monkeypatch, failure):
    install_worker(
        monkeypatch,
        f"""
import json
import os
import sys
from pathlib import Path
from twoptimizer.progress import PREFIX
request = json.loads(sys.stdin.readline())
failure = {failure!r}
if failure == "exit":
    os._exit(7)
Path(request["output"]).write_text("{{}}" if failure == "invalid-result" else "")
print(PREFIX + json.dumps({{"completed": request["id"] + (failure == "wrong-id")}}), flush=True)
sys.stdin.read()
""",
    )

    async def exercise():
        runner = BatchRunner()
        with pytest.raises(RuntimeError, match="worker"):
            await asyncio.wait_for(runner.run(RunConfig(), lambda _: None), 5)
        assert runner.process is not None and runner.process.returncode is not None
        assert not runner.cancelled
        await runner.stop()

    asyncio.run(exercise())


def test_cancel_during_process_start_reaps_the_new_process(monkeypatch):
    async def exercise():
        launching, release = asyncio.Event(), asyncio.Event()
        launch = asyncio.create_subprocess_exec

        async def spawn(*args, **kwargs):
            launching.set()
            await release.wait()
            return await launch(*args, **kwargs)

        monkeypatch.setattr(runner_module.asyncio, "create_subprocess_exec", spawn)
        runner = BatchRunner()
        task = asyncio.create_task(runner.run(RunConfig(), lambda _: None))
        await launching.wait()
        await runner.stop()
        release.set()
        assert await asyncio.wait_for(task, 5) is None
        assert runner.process is not None and runner.process.returncode is not None
        assert await runner.run(RunConfig(), lambda _: None) is None
        await runner.stop()

    asyncio.run(exercise())


def test_cancel_force_kills_active_case_preserving_completed_tui_result(monkeypatch, tmp_path):
    install_worker(monkeypatch, CONTROLLED_WORKER)

    async def exercise():
        blocking = asyncio.Event()

        class ObservedRunner(BatchRunner):
            async def run(self, config, on_log, on_progress=None):
                def progress(event):
                    if on_progress is not None:
                        on_progress(event)
                    if event == "Blocking native case":
                        blocking.set()

                return await super().run(config, on_log, progress)

        app = OptimizerApp(runner_factory=ObservedRunner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(blocking.wait(), 10)
            completed = app.results[0]
            assert app.runner is not None
            process = app.runner.process
            assert process is not None
            with pytest.raises(RuntimeError, match="one case"):
                await app.runner.run(RunConfig(), lambda _: None)
            await app.action_cancel()
            assert app.busy and process.returncode is None
            await app.action_cancel()
            await app.workers.wait_for_complete()
            assert process.returncode == -9 and not app.busy
            assert app.results == [completed]
            assert completed["raw"]["model_complexity"][0]["variables"] == 5
            path, _ = export_session(tmp_path / "cancelled.json", app.results)
            assert json.loads(path.read_text())["cases"] == [completed]

    asyncio.run(exercise())


def test_stopping_an_unused_batch_does_not_launch_a_process():
    async def exercise():
        runner = BatchRunner()
        await runner.stop()
        await runner.stop()
        assert runner.process is None
        assert await runner.run(RunConfig(), lambda _: None) is None

    asyncio.run(exercise())
