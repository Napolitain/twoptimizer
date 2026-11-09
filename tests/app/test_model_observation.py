"""Compilation telemetry is available before search and preserves model identity."""

from dataclasses import replace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.optimization.competition import BinaryModel, solve
from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario
from games.tw.rome2.model import Economy
from twoptimizer.adapters.rome2 import prepare_scenario
from twoptimizer.adapters.rome_models import ObservedEconomy, ObservedHoldingEconomy
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats, PhaseTimer, SearchStats
from twoptimizer.registry import choices
from twoptimizer.service import solve_case


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_compiled_model_sizes_are_published_before_native_search(game, monkeypatch):
    events = []
    options = choices(game)
    config = RunConfig(
        game=game,
        faction=options.default_faction,
        province=options.default_province,
        research=options.default_research,
        algorithm="cp-sat",
        workers=1,
    )

    class SearchReached(Exception):
        pass

    def search(_solver, model, callback=None):
        compiled = [event for event in events if isinstance(event, ModelStats)]
        references = [row for row in compiled if row.stage == "reference"]
        native = [row for row in compiled if row.stage == "solver"]
        assert references and len(native) == 1
        assert compiled[-1] == native[0]
        assert native[0].variables == len(model.proto.variables)
        assert native[0].constraints == len(model.proto.constraints)
        assert all(row.variables > 0 and row.constraints > 0 for row in compiled)
        for row in compiled:
            if row.stage == "solver" and row.formulation == "factored_income":
                assert row.decision_variables is None
            else:
                assert row.decision_variables is not None
                assert 0 < row.decision_variables <= row.variables
        assert isinstance(callback, cp_model.CpSolverSolutionCallback)
        assert not any(isinstance(event, SearchStats) for event in events)
        raise SearchReached

    monkeypatch.setattr(cp_model.CpSolver, "solve", search)
    with pytest.raises(SearchReached):
        solve_case(config, progress=events.append)


@pytest.mark.parametrize("joint", [False, True])
@pytest.mark.parametrize("native", [False, True])
def test_rome_observers_preserve_models_and_distinguish_solver_inputs(joint, native):
    config = RunConfig(faction="rom_rome", province="Italia", algorithm="highs")
    if joint:
        config = replace(config, provinces=("Italia", "Magna Graecia"), joint=True, adjacency=())
    scenario = prepare_scenario(config)
    timer = PhaseTimer()
    if joint:
        assert isinstance(scenario, HoldingScenario)
        original = HoldingEconomy(scenario)
        observed = ObservedHoldingEconomy(scenario, original.data, timer, config.algorithm)
    else:
        original = Economy(scenario)
        observed = ObservedEconomy(scenario, original.data, timer, config.algorithm)
    baseline, actual = original.build(native), observed.build(native)
    row = timer.models[-1]
    assert row.decision_variables == len(observed.decisions) + len(observed.party_variables)
    if native:
        assert str(actual.model.proto) == str(baseline.model.proto)
        assert row.stage == "reference"
        assert row.variables == len(baseline.model.proto.variables)
        assert row.constraints == len(baseline.model.proto.constraints)
    else:
        assert actual == baseline
        assert row.stage == "solver"
        assert row.variables == len(baseline.variable)
        assert row.constraints == len(baseline.constraint)
        assert row.nonzeros == sum(len(c.var_index) for c in baseline.constraint)


def test_cp_counts_include_implicit_constants():
    reference = BinaryModel(
        ("choice",), np.array([1]), np.zeros((1, 1)), np.array([0]), np.array([0])
    )
    result = solve(reference, "cp-sat", workers=1)
    assert result.status == "OPTIMAL" and result.objective == 1
    # CP-SAT adds a fixed true literal for the two constant constraints.
    assert result.model_stats["variables"] == 2
    assert result.model_stats["constraints"] == 2
