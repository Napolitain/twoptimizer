"""Public request invariants survive normalization and batch expansion."""

import json
from dataclasses import replace

import pytest

from games.tw.attila.scenario import Scenario
from twoptimizer.errors import ApplicationError
from twoptimizer.models import AttilaOptions, RegionFertility, RunConfig, RunRequest
from twoptimizer.requests import default_config, make_jobs
from twoptimizer.service import error_result
from twoptimizer.session import RunSession


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2", "three_kingdoms"])
def test_default_requests_are_valid_unlimited_and_roundtrip(game):
    config = default_config(game)
    jobs, skipped = make_jobs(config)
    assert jobs == [config] and not skipped
    assert config.seconds is None and config.workers is None
    assert config.algorithm == "cp-sat"
    assert RunConfig.from_dict(json.loads(json.dumps(config.to_dict()))) == config


def test_joint_and_independent_expansion_remain_distinct():
    config = default_config("shogun2")
    selected = ("jap_owari", "jap_sado")
    request = RunRequest(
        config,
        factions=("oda", "takeda"),
        provinces=selected,
        algorithms=("cp-sat", "highs"),
        soils=("native", "barren"),
    )
    separate, _ = make_jobs(request)
    assert len(separate) == 16
    assert {(j.province, j.faction, j.algorithm, j.soil) for j in separate} == {
        (p, f, a, s)
        for p in selected
        for f in ("oda", "takeda")
        for a in ("cp-sat", "highs")
        for s in ("native", "barren")
    }
    together, _ = make_jobs(replace(request, joint=True))
    assert len(together) == 8
    assert all(j.holdings == selected and j.joint for j in together)


@pytest.mark.parametrize("value", [None, 1, 2, 16])
def test_worker_counts_preserve_explicit_overrides(value):
    jobs, _ = make_jobs(RunConfig(workers=value))
    assert jobs[0].workers == value


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "2"])
def test_invalid_worker_counts_are_rejected_at_the_shared_boundary(value):
    with pytest.raises(ApplicationError) as rejected:
        make_jobs(RunConfig(workers=value))
    assert str(rejected.value) == "Workers must be a positive whole number."
    assert rejected.value.code == "invalid_request"


@pytest.mark.parametrize(
    "options",
    [
        AttilaOptions(city_level=0),
        AttilaOptions(city_level=True),
        AttilaOptions(building_level=5),
        AttilaOptions.from_dict({"seed": 1.5}),
        AttilaOptions(region_fertility=(RegionFertility("region", float("nan")),)),
    ],
)
def test_invalid_advanced_settings_fail_before_loading_an_engine(options):
    with pytest.raises(ApplicationError):
        make_jobs(replace(default_config("attila"), attila=options))


def test_income_only_rejects_campaign_objective_weights():
    config = replace(
        default_config("attila"),
        attila=AttilaOptions(
            campaign=Scenario(
                {
                    "weights": [{"metric": "research_percent", "scope": "faction", "value": 1}],
                }
            )
        ),
    )
    with pytest.raises(ApplicationError, match="Only income optimization"):
        make_jobs(config)


def test_game_specific_options_cannot_be_silently_ignored():
    with pytest.raises(ApplicationError, match="Attila options require"):
        make_jobs(RunConfig(attila=AttilaOptions(military=True)))
    with pytest.raises(ApplicationError, match="research profile"):
        make_jobs(RunConfig(technology_profile="missing"))
    with pytest.raises(ApplicationError, match="complete optimizer"):
        default_config("missing")


def test_invalid_wire_fields_have_shared_validation_semantics():
    with pytest.raises(ApplicationError, match="unexpected keyword"):
        RunConfig.from_dict({"objective": "wealth"})
    with pytest.raises(ApplicationError, match="unexpected keyword"):
        RunConfig.from_dict({"attila": {"objective": "wealth"}})


def test_failed_cases_keep_the_typed_report_shape():
    config = default_config("shogun2")
    failed = error_result(config, ApplicationError("Missing province"))
    assert failed.request == config
    assert failed.solver.status == "ERROR"
    assert failed.income is failed.solver.objective is failed.solver.bound is None
    assert failed.gap_percent is None and not failed.buildings
    assert failed.raw["error"] == "Missing province"
    assert failed.raw["code"] == "invalid_request"


def test_session_detects_conflicting_optimal_income_without_comparing_tied_layouts():
    config = default_config("shogun2")
    base = error_result(config, RuntimeError("unused"))
    proof = replace(base, income=100, solver=replace(base.solver, status="OPTIMAL"))
    session = RunSession()
    session.record(proof)
    session.record(replace(proof, request=replace(config, algorithm="highs", workers=1)))
    with pytest.raises(RuntimeError, match="disagree"):
        session.record(replace(proof, income=101))


@pytest.mark.parametrize("payload", [[], [["game", "rome2"]], None, "rome2", 0])
def test_non_object_wire_requests_cannot_start_a_default_solve(payload):
    with pytest.raises(ApplicationError, match="JSON object"):
        RunConfig.from_dict(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"province": None},
        {"provinces": "coastal"},
        {"world_bonuses": "false"},
        {"attila": []},
        {"attila": {"military": "false"}},
    ],
)
def test_malformed_fields_are_validation_errors(payload):
    with pytest.raises(ApplicationError):
        make_jobs(RunConfig.from_dict(payload))


@pytest.mark.parametrize(
    "game, fields",
    [
        ("attila", {"fertility": True}),
        ("shogun2", {"tax": True}),
        ("shogun2", {"town_wealth": False}),
        ("rome2", {"seconds": True}),
    ],
)
def test_numeric_request_fields_reject_boolean_values(game, fields):
    with pytest.raises(ApplicationError):
        make_jobs(replace(default_config(game), **fields))


def test_technology_list_cannot_be_coerced_from_a_string():
    with pytest.raises(ApplicationError, match="list of names"):
        RunConfig.from_dict({"attila": {"technologies": "one technology"}})


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2", "three_kingdoms"])
@pytest.mark.parametrize(
    "algorithm",
    ["cbc", "scip", "scip-nonlinear", "portfolio", "glop", "greedy", "beam", "multistart"],
)
def test_retired_solver_requests_are_rejected_instead_of_silently_redirected(game, algorithm):
    config = replace(default_config(game), algorithm=algorithm)
    with pytest.raises(ApplicationError, match="Supported solvers are CP-SAT and HiGHS"):
        make_jobs(config)


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2", "three_kingdoms"])
def test_exact_comparison_expands_only_supported_solvers(game):
    config = replace(default_config(game), algorithm="compare")
    jobs, skipped = make_jobs(config)
    assert [job.algorithm for job in jobs] == ["cp-sat", "highs"]
    assert not skipped


@pytest.mark.parametrize("field", ["beam_width", "restarts"])
def test_retired_heuristic_options_are_rejected_on_the_wire(field):
    with pytest.raises(ApplicationError, match="unexpected keyword"):
        RunConfig.from_dict({"attila": {field: 3}})
