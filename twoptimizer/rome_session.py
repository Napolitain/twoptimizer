"""Per-run Rome II incumbents and independently validated portable proofs."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from games.tw.rome2.model import Economy
    from twoptimizer.models import RunConfig


def _same_scenario(left: dict, right: dict) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _merge_incumbent(old: dict | None, result: dict) -> dict:
    previous_income = old.get("domestic_net_income") if old is not None else None
    income = result.get("domestic_net_income")
    best = (
        old
        if previous_income is not None and (income is None or previous_income > income)
        else result
    )
    assert best is not None
    merged = deepcopy(best)
    bounds = [
        case["solver"]["bound"]
        for case in (old, result)
        if case and case["solver"]["bound"] is not None and isfinite(case["solver"]["bound"])
    ]
    bound = min(bounds, default=None)
    retained_income = merged.get("domestic_net_income")
    if bound is not None and retained_income is not None and bound < retained_income - 1e-5:
        raise RuntimeError("Reported upper bound is below a validated feasible solution")
    merged["solver"]["bound"] = bound
    return merged


@dataclass(slots=True)
class RomeSession:
    """Own native report snapshots needed by the engine's warm-start/proof boundary."""

    cases: dict[str, dict[str, Any]] = field(default_factory=dict)
    proofs: dict[str, dict[str, Any]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.cases = deepcopy(self.cases)
        self.proofs = {
            case["proof_fingerprint"]: case
            for case in self.cases.values()
            if case["solver"]["status"] == "OPTIMAL" and "proof_fingerprint" in case
        }

    def should_skip(self, config: RunConfig, *, fill_missing: bool = False) -> bool:
        from twoptimizer.adapters.rome2 import request_key

        previous = self.cases.get(request_key(config))
        if previous is None or fill_missing:
            return previous is not None
        if config.compare_constraints:
            from twoptimizer.constraint_comparison import has_requirements

            if (
                has_requirements(config)
                and previous.get("constraint_comparison", {}).get("status") != "exact"
            ):
                return False
        return previous["solver"]["status"] == "OPTIMAL"

    def solve(self, economy: Economy, config: RunConfig) -> dict[str, Any]:
        scenario = economy.scenario.to_dict()
        key = json.dumps([scenario, config.algorithm], sort_keys=True)
        seeds = [
            case
            for case in self.cases.values()
            if "sites" in case and _same_scenario(case["scenario"], scenario)
        ]
        seed = max(seeds, key=lambda case: case["domestic_net_income"], default=None)
        fingerprint = economy.fingerprint() if config.algorithm in {"cp-sat", "portfolio"} else None
        result = (
            economy.reuse_optimum(self.proofs[fingerprint])
            if fingerprint in self.proofs
            else economy.optimize(
                config.algorithm,
                config.seconds,
                config.workers,
                incumbent=seed
                if config.algorithm in {"cp-sat", "scip-nonlinear", "portfolio"}
                else None,
            )
        )
        if (
            fingerprint
            and result.get("proof_fingerprint") == fingerprint
            and result["solver"]["status"] == "OPTIMAL"
        ):
            self.proofs[fingerprint] = result
        merged = _merge_incumbent(self.cases.get(key), result)
        self.cases[key] = merged
        self._assert_matching_proofs(scenario)
        return merged

    def _assert_matching_proofs(self, scenario: dict) -> None:
        proven = [
            case["domestic_net_income"]
            for case in self.cases.values()
            if _same_scenario(case["scenario"], scenario) and case["solver"]["status"] == "OPTIMAL"
        ]
        if proven and max(proven) - min(proven) > 1e-5:
            raise AssertionError("Exact solvers disagree on a proved optimum")
