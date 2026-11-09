"""Bounded Shogun layout reuse; every candidate is re-evaluated by its owning engine."""

import json
from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite


def _key(scenario):
    return json.dumps(scenario, sort_keys=True)


def _matching_province(case, scenario, province):
    previous = dict(case["scenario"])
    old_provinces = previous.pop("provinces")
    settings = dict(scenario)
    settings.pop("provinces")
    return _key(previous) == _key(settings) and province in old_provinces


def _validated_candidate(economy, report):
    if "provinces" not in report:
        return None
    layout = {key: row["buildings"] for key, row in report["provinces"].items()}
    try:
        economics = economy.evaluate(layout)
    except ValueError:
        return None
    return {**report, "scenario": economy.scenario.to_dict(), **economics}


def _best_seed(candidates):
    seed = deepcopy(max(candidates, key=lambda row: row["domestic_tax_income"], default=None))
    if seed is None or "model_fingerprint" not in seed:
        return seed
    bounds = [
        bound
        for case in candidates
        if case.get("model_fingerprint") == seed["model_fingerprint"]
        and type(bound := case.get("solver", {}).get("bound")) in {int, float}
        and isfinite(bound)
    ]
    seed.setdefault("solver", {})["bound"] = min(bounds, default=None)
    return seed


@dataclass(slots=True)
class ShogunSession:
    cases: dict[str, dict] = field(default_factory=dict)

    def clear(self):
        self.cases.clear()

    def trim(self, limit):
        while len(self.cases) > limit:
            self.cases.pop(next(iter(self.cases)))

    def _combined(self, economy):
        scenario = economy.scenario.to_dict()
        selected = {}
        for province in scenario["provinces"]:
            candidates = [
                case["provinces"][province["id"]]
                for case in self.cases.values()
                if "provinces" in case
                and province["id"] in case["provinces"]
                and _matching_province(case, scenario, province)
            ]
            if not candidates:
                return None
            selected[province["id"]] = max(candidates, key=lambda row: row["tax_income"])
        return _validated_candidate(economy, {"provinces": selected})

    def solve(self, economy, config, **observers):
        scenario = economy.scenario.to_dict()
        candidates = [
            validated
            for case in self.cases.values()
            if _key(case["scenario"]) == _key(scenario)
            and (validated := _validated_candidate(economy, case)) is not None
        ]
        if len(scenario["provinces"]) > 1 and (combined := self._combined(economy)) is not None:
            candidates.append(combined)
        seed = _best_seed(candidates)
        result = economy.optimize(
            config.algorithm,
            config.seconds,
            config.workers,
            incumbent=seed,
            **observers,
        )
        # Native bounds and statuses are never borrowed from an earlier model.
        if "provinces" in result:
            key = _key([scenario, config.algorithm])
            self.cases.pop(key, None)
            self.cases[key] = deepcopy(result)
            self.trim(128)
        return result
