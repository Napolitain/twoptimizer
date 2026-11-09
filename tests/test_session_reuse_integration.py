"""Actual worker and engine boundaries preserve validated reuse across new runs."""

import asyncio
from dataclasses import replace

from twoptimizer.models import CaseResult
from twoptimizer.requests import default_config
from twoptimizer.runner import BatchRunner
from twoptimizer.service import solve_case
from twoptimizer.session import RunSession


def test_three_kingdoms_cross_backend_repeat_retains_a_validated_start():
    config = replace(default_config("three_kingdoms"), seconds=5, workers=1)
    session = RunSession()
    first = solve_case(config, session=session)
    second = solve_case(replace(config, algorithm="highs"), session=session)
    assert first.solver.status == second.solver.status == "OPTIMAL"
    assert first.income == second.income == 627.75
    assert second.raw["solver"]["seed_reused"]
    assert second.raw["model_fingerprint"] == first.raw["model_fingerprint"]
    assert len(session.three_kingdoms.cases) == 1


def test_independent_three_kingdoms_cases_supply_a_valid_joint_start():
    config = replace(default_config("three_kingdoms"), seconds=5, workers=1)
    session = RunSession()
    holdings = ("3k_main_province_yingchuan", "3k_main_province_changan")
    for province in holdings:
        case = solve_case(replace(config, province=province), session=session)
        assert case.solver.status == "OPTIMAL"
    joint = solve_case(replace(config, provinces=holdings, joint=True), session=session)
    assert joint.income is not None and joint.income >= 1438
    assert joint.raw["solver"]["joint_bound_search"]["cached_local_cases"] == 2
    food = joint.metrics["food_surplus"]
    assert food is not None and food >= 0
    assert set(joint.raw["commanderies"]) == set(holdings)


def test_real_batch_worker_keeps_session_across_completed_batches():
    async def exercise():
        config = replace(default_config("three_kingdoms"), seconds=5, workers=1)
        runner = BatchRunner()
        try:
            first = await runner.run(config, lambda _: None)
            process = runner.process
            assert process is not None and process.returncode is None
            runner.begin_batch()
            second = await runner.run(replace(config, algorithm="highs"), lambda _: None)
            assert second is not None and first is not None
            assert runner.process is process and process.returncode is None
            assert CaseResult.from_dict(second).income == CaseResult.from_dict(first).income
            assert second["raw"]["solver"]["seed_reused"]
            assert "worker_dispatch_seconds" in second["timings"]
        finally:
            await runner.stop()
        assert process.returncode is not None

    asyncio.run(exercise())
