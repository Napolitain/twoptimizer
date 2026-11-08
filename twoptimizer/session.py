"""Optional per-run model/proof reuse, independent of how a case is executed."""

import json
from dataclasses import dataclass, field

from twoptimizer.attila_session import AttilaSession
from twoptimizer.models import CaseResult
from twoptimizer.rome_session import RomeSession


@dataclass(slots=True)
class RunSession:
    attila: AttilaSession = field(default_factory=AttilaSession)
    rome: RomeSession = field(default_factory=RomeSession)
    _optima: dict[str, float] = field(default_factory=dict, init=False)

    def record(self, result: CaseResult) -> None:
        settings = result.request.to_dict()
        for key in ("algorithm", "seconds", "workers"):
            settings.pop(key, None)
        if result.objectives:
            self._record_objectives(result, settings)
            return
        if result.solver.status != "OPTIMAL" or result.income is None:
            return
        key = json.dumps(settings, sort_keys=True)
        self._record_value(key, result.income)

    def _record_value(self, key: str, value: float) -> None:
        previous = self._optima.setdefault(key, value)
        if abs(previous - value) > 1e-5:
            raise RuntimeError("Exact solvers disagree on a proved optimum")

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
