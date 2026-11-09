"""Cooperative cancellation preserves validated results and requested requirements."""

from dataclasses import replace

import pytest

from games.optimization.cancellation import Cancellation
from twoptimizer import service
from twoptimizer.adapters.search import search_observers
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.errors import ApplicationError
from twoptimizer.models import BuildingSelection, EngineResult
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.requests import default_config


def _install(monkeypatch, game, adapter):
    monkeypatch.setattr(service, "solve_adapter", lambda identifier: {game: adapter}[identifier])
    # These tests exercise orchestration, with deliberately fabricated adapters;
    # keep the two sides independent of concurrent edits to source files.
    monkeypatch.setattr(service, "source_files", lambda game: {"test_source": game})


def _candidate(config, *, status="FEASIBLE", income=80, bound=100):
    required = bool(config.constraints.required_buildings)
    return EngineResult(
        {
            "solver": {
                "algorithm": config.algorithm,
                "status": status,
                "seconds": 1.25,
                "objective": income,
                "bound": bound,
            },
            "cancellation": {"reason": "Native result independently validated"},
        },
        income,
        [
            BuildingSelection(
                "Capital", "Temple" if required else "Market", "temple" if required else "market"
            )
        ],
        {"food_surplus": 7, "public_order": 3},
    )


def _comparison():
    return replace(
        default_config("rome2"),
        compare_constraints=True,
        constraints=ConstraintOptions(required_buildings=("temple",)),
    )


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
def test_already_cancelled_case_returns_unknown_without_entering_an_adapter(monkeypatch, game):
    token = Cancellation()
    token.cancel()

    def unexpected(*args):
        raise AssertionError("Cancelled work must not enter the engine")

    _install(monkeypatch, game, unexpected)
    result = service.solve_case(default_config(game), cancellation=token)
    assert result.solver.status == "UNKNOWN"
    assert (
        result.income
        is result.solver.objective
        is result.solver.bound
        is result.gap_percent
        is None
    )
    assert result.buildings == [] and result.metrics == {}
    assert result.raw["cancellation"]["requested"] is True
    assert result.raw["cancellation"]["incumbent_retained"] is False
    assert "before a solver result" in result.raw["cancellation"]["reason"]


@pytest.mark.parametrize("game", ["attila", "rome2", "shogun2"])
@pytest.mark.parametrize("with_progress", [False, True])
def test_cancellation_reaches_the_engine_independently_of_progress(
    monkeypatch, game, with_progress
):
    token, events, forwarded = Cancellation(), [], []

    def adapter(config, phase, session):
        assert phase.cancellation is token
        observers = search_observers(phase, "Test solver", lambda: 2)
        forwarded.append(observers["cancellation"])
        assert set(observers) == {"cancellation", "on_search", "on_model"}
        assert callable(observers["on_model"])
        observers["on_search"](80, 80, 1.25)
        return _candidate(config, status="OPTIMAL", bound=80)

    _install(monkeypatch, game, adapter)
    result = service.solve_case(
        default_config(game), events.append if with_progress else None, cancellation=token
    )
    assert forwarded == [token]
    assert result.solver.status == "OPTIMAL" and result.income == 80
    assert not token.requested
    assert any(isinstance(event, SearchStats) for event in events) == with_progress
    measurements = result.raw["search_measurements"]
    assert measurements["observations"] == 1
    assert measurements["samples"][0]["objective"] == 80
    assert measurements["final"]["validated_layout"] is True


def test_preparation_cancellation_retains_model_observations_without_a_candidate(monkeypatch):
    token = Cancellation()
    model = ModelStats("Prepared reference", 3, 2, stage="reference", decision_variables=2)

    def adapter(config, phase, session):
        phase("build_model_seconds", "Preparing model")
        phase.record_model(model)
        token.cancel()
        phase.cancellation.checkpoint()
        raise AssertionError("No native search should start after this checkpoint")

    _install(monkeypatch, "rome2", adapter)
    result = service.solve_case(default_config("rome2"), cancellation=token)
    assert result.solver.status == "UNKNOWN" and result.income is None
    assert result.solver.bound is None and result.gap_percent is None
    assert result.raw["model_complexity"] == [model.to_dict()]
    assert result.timings["build_model_seconds"] >= 0
    assert result.raw["cancellation"]["incumbent_retained"] is False


@pytest.mark.parametrize(
    ("status", "income", "bound"),
    [("FEASIBLE", 80, 100), ("FEASIBLE", 0, 100), ("OPTIMAL", 80, 80)],
)
def test_cancelled_validated_candidate_keeps_native_status_bound_gap_and_layout(
    monkeypatch, status, income, bound
):
    token = Cancellation()

    def adapter(config, phase, session):
        candidate = _candidate(config, status=status, income=income, bound=bound)
        token.cancel()
        return candidate

    _install(monkeypatch, "rome2", adapter)
    result = service.solve_case(default_config("rome2"), cancellation=token)
    assert result.solver.status == status
    assert result.income == result.solver.objective == income
    assert result.solver.bound == bound
    assert result.gap_percent == pytest.approx(100 * (bound - income) / max(1, abs(bound)))
    assert result.buildings == [BuildingSelection("Capital", "Market", "market")]
    assert result.metrics == {"food_surplus": 7, "public_order": 3}
    assert result.raw["cancellation"] == {
        "reason": "Native result independently validated",
        "requested": True,
        "incumbent_retained": True,
    }
    assert result.to_dict()["raw"]["cancellation"]["incumbent_retained"] is True


@pytest.mark.parametrize("error_type", [ValueError, AssertionError])
def test_cancellation_does_not_mask_independent_validation_errors(monkeypatch, error_type):
    token = Cancellation()

    def adapter(config, phase, session):
        token.cancel()
        raise error_type("Independent economics disagrees")

    _install(monkeypatch, "rome2", adapter)
    with pytest.raises(error_type, match="Independent economics disagrees"):
        service.solve_case(default_config("rome2"), cancellation=token)


def test_cancelled_invalid_request_still_fails_request_validation():
    token = Cancellation()
    token.cancel()
    with pytest.raises(ApplicationError):
        service.solve_case(
            replace(default_config("rome2"), faction="unknown_faction"), cancellation=token
        )


@pytest.mark.parametrize("has_candidate", [False, True])
def test_cancel_during_requested_comparison_side_skips_baseline_and_never_substitutes_it(
    monkeypatch, has_candidate
):
    token, calls = Cancellation(), []

    def adapter(config, phase, session):
        calls.append(config)
        assert config.constraints.required_buildings == ("temple",)
        token.cancel()
        if not has_candidate:
            token.checkpoint()
        return _candidate(config)

    _install(monkeypatch, "rome2", adapter)
    requested = _comparison()
    result = service.solve_case(requested, cancellation=token)
    assert len(calls) == 1 and not calls[0].compare_constraints
    assert result.request == requested
    assert result.solver.status == ("FEASIBLE" if has_candidate else "UNKNOWN")
    assert result.income == (80 if has_candidate else None)
    assert [row.id for row in result.buildings] == (["temple"] if has_candidate else [])
    comparison = result.raw["constraint_comparison"]
    assert comparison["status"] == "unavailable" and comparison["exact_cost"] is None
    baseline = comparison["baseline"]
    assert baseline["solver"]["status"] == "UNKNOWN" and baseline["income"] is None
    assert baseline["buildings"] == []
    assert baseline["raw"]["cancellation"]["requested"] is True
    assert result.raw["cancellation"]["incumbent_retained"] is has_candidate


@pytest.mark.parametrize("baseline_candidate", [False, True])
def test_cancel_during_baseline_preserves_proved_constrained_layout_and_incomplete_comparison(
    monkeypatch, baseline_candidate
):
    token, calls = Cancellation(), []

    def adapter(config, phase, session):
        required = bool(config.constraints.required_buildings)
        calls.append(required)
        if required:
            return _candidate(config, status="OPTIMAL", bound=80)
        token.cancel()
        if not baseline_candidate:
            token.checkpoint()
        return _candidate(config, income=95, bound=105)

    _install(monkeypatch, "rome2", adapter)
    requested = _comparison()
    result = service.solve_case(requested, cancellation=token)
    assert calls == [True, False]
    assert result.request == requested
    assert result.solver.status == "OPTIMAL"  # Requested side's completed proof survives.
    assert result.income == result.solver.objective == result.solver.bound == 80
    assert result.gap_percent == 0
    assert [row.id for row in result.buildings] == ["temple"]
    comparison = result.raw["constraint_comparison"]
    assert comparison["status"] == ("bounded" if baseline_candidate else "unavailable")
    assert comparison["exact_cost"] is None
    baseline = comparison["baseline"]
    assert baseline["solver"]["status"] == ("FEASIBLE" if baseline_candidate else "UNKNOWN")
    assert baseline["income"] == (95 if baseline_candidate else None)
    assert result.raw["cancellation"]["requested"] is True
    assert result.raw["cancellation"]["incumbent_retained"] is True


def test_constrained_validation_error_after_cancel_still_propagates_and_skips_baseline(monkeypatch):
    token, calls = Cancellation(), []

    def adapter(config, phase, session):
        calls.append(config)
        token.cancel()
        raise ValueError("Rejected retained layout")

    _install(monkeypatch, "rome2", adapter)
    with pytest.raises(ApplicationError, match="Rejected retained layout"):
        service.solve_case(_comparison(), cancellation=token)
    assert len(calls) == 1 and calls[0].constraints.required_buildings == ("temple",)
