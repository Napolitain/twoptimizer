"""Bounded reuse survives a new Run without crossing scenario or source boundaries."""

import asyncio
import io
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from games.tw.three_kingdoms.model import Economy
from tests.support.ui import result
from twoptimizer import session as session_module
from twoptimizer import worker
from twoptimizer.adapters.three_kingdoms import prepare_scenario
from twoptimizer.models import CaseResult
from twoptimizer.requests import default_config
from twoptimizer.runner import BatchRunner
from twoptimizer.session import RunSession
from twoptimizer.three_kingdoms_session import ThreeKingdomsSession
from twoptimizer.tui import OptimizerApp


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_worker_session_limit_rejects_unbounded_or_invalid_values(limit):
    with pytest.raises(ValueError, match="positive whole number"):
        RunSession(max_cases=limit)


def test_source_change_invalidates_only_the_affected_game(monkeypatch):
    sources = {"three_kingdoms": "old", "rome2": "rome"}
    monkeypatch.setattr(session_module, "source_files", lambda game: {"model.py": sources[game]})
    state = RunSession()
    state.prepare("three_kingdoms")
    state.prepare("rome2")
    state.three_kingdoms.cases["snapshot"] = {"income": 100}
    state.rome.cases["roman"] = {"income": 200}
    state.prepare("three_kingdoms")
    assert state.three_kingdoms.cases
    sources["three_kingdoms"] = "changed"
    state.prepare("three_kingdoms")
    assert not state.three_kingdoms.cases
    assert state.rome.cases == {"roman": {"income": 200}}


def test_session_maps_and_consistency_records_are_bounded():
    state = RunSession(max_cases=2)
    for index in range(5):
        state.rome.cases[str(index)] = {"index": index}
        state.rome.proofs[str(index)] = {"index": index}
        state.three_kingdoms.cases[str(index)] = {"index": index}
    state.trim()
    assert list(state.rome.cases) == list(state.rome.proofs) == ["3", "4"]
    assert list(state.three_kingdoms.cases) == ["3", "4"]
    for index in range(12):
        state._record_value(str(index), index)
    assert len(state._optima) == 8 and "0" not in state._optima


def test_optimum_consistency_is_scoped_to_the_report_sources():
    state = RunSession()
    original = CaseResult.from_dict({**result(), "timings": {}})
    state.record(original)
    changed = replace(original, income=123, source_files={"model.py": "changed"})
    state.record(changed)
    with pytest.raises(RuntimeError, match="disagree"):
        state.record(replace(changed, income=124))


def test_batch_worker_shares_one_session_between_requests(monkeypatch):
    sessions = []

    def run(request_path, output_path, cancel_path, *, session):
        sessions.append(session)
        return 0

    requests = [{"id": i, "request": f"request-{i}", "output": f"output-{i}"} for i in range(2)]
    monkeypatch.setattr(worker.sys, "stdin", io.StringIO("\n".join(map(json.dumps, requests))))
    monkeypatch.setattr(worker, "run_case", run)
    assert worker.batch_main() == 0
    assert len(sessions) == 2 and sessions[0] is sessions[1]
    assert isinstance(sessions[0], RunSession)


def test_three_kingdoms_reuses_only_matching_scenarios_and_owns_its_snapshots(monkeypatch):
    state = ThreeKingdomsSession()
    config = default_config("three_kingdoms")
    received = []
    report = {"domestic_income": -5, "solver": {"status": "FEASIBLE", "bound": 10}}

    local_candidates = []

    def optimize(algorithm, seconds, workers, *, incumbent, local_incumbents):
        received.append(deepcopy(incumbent))
        local_candidates.append(deepcopy(local_incumbents))
        if incumbent is not None:
            incumbent["solver"]["bound"] = 99
        return deepcopy(report)

    economy = Economy(prepare_scenario(config))
    monkeypatch.setattr(economy, "optimize", optimize)
    first = state.solve(economy, config)
    first["solver"]["bound"] = 999
    state.solve(economy, replace(config, algorithm="highs"))
    assert received == [None, report]
    assert local_candidates == [(), (report,)]
    assert next(iter(state.cases.values())) == report
    economy.scenario = replace(
        economy.scenario,
        commanderies=(replace(economy.scenario.commanderies[0], population=200),),
    )
    state.solve(economy, config)
    assert received[-1] is None


def test_tui_reuses_batch_session_after_graceful_cancel_and_closes_on_unmount():
    async def exercise():
        active, release = asyncio.Event(), asyncio.Event()
        launched = []

        class RetainedRunner(BatchRunner):
            calls = 0
            stopped = False

            async def run(self, config, on_log, on_progress=None):
                self.calls += 1
                if self.calls == 1:
                    active.set()
                    await release.wait()
                assert not self._forced_stop
                return result(config)

            async def stop(self):
                self.stopped = True
                await super().stop()

        def factory():
            runner = RetainedRunner()
            launched.append(runner)
            return runner

        app = OptimizerApp(runner_factory=factory)
        async with app.run_test(size=(100, 36)) as pilot:
            app.action_run()
            await asyncio.wait_for(active.wait(), 5)
            await app.action_cancel()
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(app.results) == 1 and not app.busy
            assert launched[0].cancelled and not launched[0].stopped
            app.action_run()
            await app.workers.wait_for_complete()
            assert len(launched) == 1 and launched[0].calls == 2
            assert not launched[0].cancelled and not launched[0].stopped
            assert len(app.results) == 1
        assert launched[0].stopped

    asyncio.run(exercise())


def test_active_batch_cannot_reset_its_cancellation_state():
    runner = BatchRunner()
    runner._active = runner.cancelled = True
    with pytest.raises(RuntimeError, match="active case"):
        runner.begin_batch()
    assert runner.cancelled
