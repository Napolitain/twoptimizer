"""Bounded reusable Three Kingdoms layouts; the engine validates every warm start."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from games.tw.three_kingdoms.model import Economy
    from twoptimizer.models import RunConfig


@dataclass(slots=True)
class ThreeKingdomsSession:
    cases: dict[str, dict[str, Any]] = field(default_factory=dict)

    def clear(self) -> None:
        self.cases.clear()

    def trim(self, limit: int) -> None:
        while len(self.cases) > limit:
            self.cases.pop(next(iter(self.cases)))

    def solve(self, economy: Economy, config: RunConfig, **observers) -> dict[str, Any]:
        key = json.dumps(economy.scenario.to_dict(), sort_keys=True)
        incumbent = self.cases.get(key)
        result = economy.optimize(
            config.algorithm,
            config.seconds,
            config.workers,
            incumbent=deepcopy(incumbent),
            local_incumbents=deepcopy(tuple(self.cases.values())),
            **observers,
        )
        if result.get("domestic_income") is not None:
            # An incumbent is only a candidate: the owning engine rechecks its
            # scenario, model identity and full economics before accepting it.
            self.cases.pop(key, None)
            self.cases[key] = deepcopy(result)
        return result
