"""The execution boundary preserves application results and completed UI work."""

import asyncio
import csv
import json
import sys
from dataclasses import replace

import pytest
from textual.widgets import Select

from games.tw.attila.scenario import Scenario
from twoptimizer import worker
from twoptimizer.errors import ApplicationError, deserialize_error, serialize_error
from twoptimizer.export import export_session
from twoptimizer.models import AttilaOptions, CaseResult, RegionFertility, RunConfig, SolverSummary
from twoptimizer.runner import CaseRunner
from twoptimizer.service import solve_case
from twoptimizer.tui import OptimizerApp


def test_stop_reaps_a_worker_that_exits_while_receiving_termination(monkeypatch):
    class ExitingProcess:
        returncode = None
        waited = False

        def terminate(self):
            raise ProcessLookupError

        async def wait(self):
            self.waited = True
            self.returncode = 0
            return self.returncode

    async def exercise():
        runner = CaseRunner()
        process = ExitingProcess()
        monkeypatch.setattr(runner, "process", process)
        await runner.stop()
        assert process.waited and process.returncode == 0
        assert runner.cancelled

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "config",
    [RunConfig(seconds=-1), RunConfig(seconds=float("nan")), RunConfig(workers=0)],
)
def test_direct_and_isolated_invalid_requests_have_identical_errors(config):
    with pytest.raises(ApplicationError) as direct:
        solve_case(config)

    async def exercise():
        runner = CaseRunner()
        with pytest.raises(ApplicationError) as isolated:
            await runner.run(config, lambda _: None)
        assert str(isolated.value) == str(direct.value)
        assert isolated.value.code == direct.value.code
        assert runner.process is not None and runner.process.returncode == 1

    asyncio.run(exercise())


def test_worker_errors_distinguish_invalid_requests_from_runtime_failure():
    rejected = ApplicationError("Unknown holding", code="unknown_holding")
    payload = serialize_error(rejected)
    assert payload == {
        "error": "Unknown holding",
        "error_type": "ApplicationError",
        "code": "unknown_holding",
    }
    restored = deserialize_error(json.loads(json.dumps(payload)))
    assert isinstance(restored, ApplicationError)
    assert restored.code == "unknown_holding"
    assert str(restored) == str(rejected)
    runtime = deserialize_error(serialize_error(RuntimeError("Solver failed")))
    assert isinstance(runtime, RuntimeError) and str(runtime) == "Solver failed"
    assert isinstance(deserialize_error({"error": "Legacy worker failed"}), RuntimeError)


def test_worker_decodes_typed_campaign_inputs_before_invoking_case_service(tmp_path, monkeypatch):
    config = RunConfig(
        game="attila",
        faction="att_fact_eastern_roman_empire",
        province="att_prov_thracia",
        provinces=("att_prov_thracia", "att_prov_asia"),
        joint=True,
        algorithm="cp-sat",
        research="all",
        attila=AttilaOptions(
            campaign=Scenario(
                {
                    "campaign": {"active_trade_routes": 3, "at_peace_with_sassanids": True},
                    "provinces": {"att_prov_thracia": {"public_order": 25}},
                }
            ),
            region_fertility=(RegionFertility("att_reg_thracia_constantinopolis", 1),),
            city_level=3,
            military=True,
            seed=7,
            beam_width=32,
            restarts=4,
        ),
    )
    captured = []

    def solve(received, progress):
        captured.append(received)
        progress("Checking decoded campaign")
        return CaseResult(
            request=received,
            faction="Eastern Roman Empire",
            province="Thracia + Asia",
            solver=SolverSummary("cp-sat", "FEASIBLE", 0.5, 100, 110),
            income=100,
            gap_percent=100 / 11,
            metrics={"food_surplus": 10},
            buildings=[],
            assumptions="Supplied campaign inputs",
            source_files={"model.py": "a" * 64},
            raw={"layout": {"objective": 100}},
            timings={"solve_and_check_seconds": 0.5},
        )

    request, output = tmp_path / "request.json", tmp_path / "result.json"
    request.write_text(json.dumps(config.to_dict(), allow_nan=False))
    monkeypatch.setattr(worker, "solve_case", solve)
    monkeypatch.setattr(sys, "argv", ["worker", str(request), str(output)])
    assert worker.main() == 0
    assert captured == [config]
    decoded = captured[0]
    assert isinstance(decoded.attila.campaign, Scenario)
    assert decoded.attila.campaign.campaign.active_trade_routes == 3
    assert decoded.attila.campaign.provinces["att_prov_thracia"].public_order == 25
    assert decoded.attila.region_fertility == config.attila.region_fertility
    report = CaseResult.from_dict(json.loads(output.read_text()))
    assert report.request == config
    assert report.solver.status == "FEASIBLE"
    assert report.solver.bound == 110 and report.income == 100
    assert report.raw["layout"]["objective"] == report.income
    assert report.source_files == {"model.py": "a" * 64}


@pytest.mark.parametrize("provinces", [None, ("jap_owari", "jap_sado")])
def test_worker_roundtrip_preserves_economic_proof_and_provenance(provinces):
    config = RunConfig(
        game="shogun2",
        faction="oda",
        province="jap_owari",
        algorithm="cp-sat",
        research="all",
        workers=1,
        tax=35,
        town_wealth=125,
        provinces=provinces,
        joint=provinces is not None,
    )
    direct = solve_case(config)
    assert set(direct.raw["provinces"]) == set(config.holdings)

    async def exercise():
        payload = await CaseRunner().run(config, lambda _: None)
        assert payload is not None
        isolated = CaseResult.from_dict(payload)
        assert isolated.request == direct.request
        assert isolated.solver.status == direct.solver.status == "OPTIMAL"
        assert isolated.income == direct.income
        assert isolated.solver.objective == direct.solver.objective
        assert isolated.solver.bound == direct.solver.bound
        assert isolated.gap_percent == direct.gap_percent == 0
        assert isolated.metrics == direct.metrics
        assert isolated.assumptions == direct.assumptions
        assert isolated.source_files == direct.source_files
        assert isolated.timings["worker_wall_seconds"] > 0
        assert isolated.timings["worker_startup_seconds"] >= 0
        assert isolated.to_dict() == json.loads(json.dumps(payload))

    asyncio.run(exercise())


def test_cancel_native_worker_preserves_completed_case_and_export(tmp_path):
    async def exercise():
        solving_second = asyncio.Event()

        class ObservedRunner(CaseRunner):
            async def run(self, config, on_log, on_progress=None):
                def progress(phase):
                    if on_progress is not None:
                        on_progress(phase)
                    if config.algorithm == "cbc" and phase == "Solving and validating":
                        solving_second.set()

                return await super().run(replace(config, workers=1), on_log, progress)

        app = OptimizerApp(runner_factory=ObservedRunner)
        async with app.run_test(size=(110, 36)) as pilot:
            app.query_one("#game", Select).value = "attila"
            await pilot.pause()
            app.query_one("#algorithm", Select).value = "compare"
            await pilot.pause()
            app.action_run()
            await asyncio.wait_for(solving_second.wait(), 30)
            assert len(app.results) == 1 and app.busy
            assert app.runner is not None and app.runner.process is not None
            process = app.runner.process
            assert process.returncode is None
            completed = app.results[0]
            await app.action_cancel()
            await app.workers.wait_for_complete()
            assert process.returncode is not None
            assert not app.busy and app.results == [completed]
            assert completed["solver"]["status"] == "OPTIMAL"
            assert completed["income"] == 24140.375
            json_path, csv_path = export_session(tmp_path / "cancelled.json", app.results)
            saved = json.loads(json_path.read_text())
            assert saved["schema_version"] == 1
            assert saved["cases"] == [completed]
            with csv_path.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == 1
            assert rows[0]["status"] == "OPTIMAL"
            assert float(rows[0]["income"]) == completed["income"]

    asyncio.run(exercise())
