"""Compilation telemetry is available before search and preserves model identity."""

from dataclasses import replace

import numpy as np
import pytest
from ortools.sat.python import cp_model

from games.tw.competition import BinaryModel, solve
from games.tw.rome2.holdings import HoldingEconomy, HoldingScenario
from games.tw.rome2.model import Economy
from twoptimizer.adapters.rome2 import prepare_scenario
from twoptimizer.adapters.rome_models import ObservedEconomy, ObservedHoldingEconomy
from twoptimizer.catalog import choices
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats, PhaseTimer
from twoptimizer.service import solve_case


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_compiled_model_sizes_are_published_before_native_search(game, monkeypatch):
    events = []
    options = choices(game)
    config = RunConfig(
        game=game,
        faction=options["default_faction"],
        province=options["default_province"],
        research=options["default_research"],
        algorithm="cp-sat",
        workers=1,
    )

    class SearchReached(Exception):
        pass

    def search(_solver, _model):
        compiled = [event for event in events if isinstance(event, ModelStats)]
        assert compiled
        assert all(row.variables > 0 and row.constraints > 0 for row in compiled)
        assert all(0 < row.decision_variables <= row.variables for row in compiled)
        assert compiled[-1].stage == "reference"
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
    else:
        assert actual == baseline
        assert row.stage == "solver"
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
