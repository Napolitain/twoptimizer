"""Optional per-run model/proof reuse, independent of how a case is executed."""

import json
from dataclasses import dataclass, field

from twoptimizer.attila_session import AttilaSession
from twoptimizer.models import CaseResult
from twoptimizer.provenance import source_files
from twoptimizer.registry import game_plugin, game_plugins
from twoptimizer.rome_session import RomeSession
from twoptimizer.session_cache import trim_cache
from twoptimizer.shogun_session import ShogunSession
from twoptimizer.three_kingdoms_session import ThreeKingdomsSession

MAX_CASES = 128


@dataclass(slots=True)
class RunSession:
    attila: AttilaSession = field(default_factory=AttilaSession)
    rome: RomeSession = field(default_factory=RomeSession)
    shogun: ShogunSession = field(default_factory=ShogunSession)
    three_kingdoms: ThreeKingdomsSession = field(default_factory=ThreeKingdomsSession)
    max_cases: int = MAX_CASES
    _optima: dict[str, float] = field(default_factory=dict, init=False)
    _sources: dict[str, dict[str, str]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.max_cases, bool) or not isinstance(self.max_cases, int):
            raise ValueError("Session case limit must be a positive whole number")
        if self.max_cases < 1:
            raise ValueError("Session case limit must be a positive whole number")

    def prepare(self, game: str) -> None:
        current = source_files(game)
        previous = self._sources.get(game)
        if previous is not None and previous != current:
            self._invalidate(game)
        self._sources[game] = current
        self.trim()

    def _invalidate(self, game: str) -> None:
        cache = game_plugin(game).session_cache
        if cache is not None:
            cache(self).clear()

    def trim(self) -> None:
        for plugin in game_plugins():
            if plugin.session_cache is not None:
                plugin.session_cache(self).trim(self.max_cases)
        trim_cache(self._optima, self.max_cases * 4)

    def record(self, result: CaseResult) -> None:
        self.trim()
        settings = result.request.to_dict()
        for key in ("algorithm", "seconds", "workers"):
            settings.pop(key, None)
        if result.objectives:
            self._record_objectives(result, settings)
            return
        if result.solver.status != "OPTIMAL" or result.income is None:
            return
        key = json.dumps({"request": settings, "source_files": result.source_files}, sort_keys=True)
        self._record_value(key, result.income)

    def _record_value(self, key: str, value: float) -> None:
        previous = self._optima.setdefault(key, value)
        if abs(previous - value) > 1e-5:
            raise RuntimeError("Exact solvers disagree on a proved optimum")
        trim_cache(self._optima, self.max_cases * 4)

    def _record_objectives(self, result: CaseResult, settings: dict) -> None:
        if result.solver.status not in {"OPTIMAL", "FEASIBLE"}:
            return
        priorities = []
        for objective in result.objectives:
            if (objective.status or result.solver.status) != "OPTIMAL" or objective.value is None:
                break
            priorities.append((objective.identifier, objective.unit, objective.sense))
            key = json.dumps(
                {
                    "request": settings,
                    "source_files": result.source_files,
                    "objective_priorities": priorities,
                },
                sort_keys=True,
            )
            self._record_value(key, objective.value)
