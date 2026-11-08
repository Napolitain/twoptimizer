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
        if result.solver.status != "OPTIMAL" or result.income is None:
            return
        settings = result.request.to_dict()
        for key in ("algorithm", "seconds", "workers"):
            settings.pop(key, None)
        key = json.dumps(settings, sort_keys=True)
        previous = self._optima.setdefault(key, result.income)
        if abs(previous - result.income) > 1e-5:
            raise RuntimeError("Exact solvers disagree on a proved optimum")
