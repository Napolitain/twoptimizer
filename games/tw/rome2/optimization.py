"""Solver execution, proof reuse and independent result verification."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from games.tw.immutable import thaw
from games.tw.resources import resolve_workers
from games.tw.rome2.backends import NativeCP

if TYPE_CHECKING:
    from games.tw.rome2.model import Economy


class RomeOptimizer:
    def __init__(self, economy: Economy):
        self.economy = economy

    def optimize(
        self,
        algorithm="cp-sat",
        seconds=None,
        workers=None,
        incumbent=None,
        *,
        on_search=None,
        on_model=None,
        cancellation=None,
        on_phase=None,
    ):
        if algorithm not in {"cp-sat", "highs"}:
            raise ValueError("Choose cp-sat or highs")
        workers = resolve_workers(workers)
        if cancellation is not None:
            cancellation.checkpoint()
        start = perf_counter()
        if algorithm == "cp-sat":
            return self._optimize_cpsat(
                seconds, workers, incumbent, start, on_search, on_model, cancellation, on_phase
            )
        return self._optimize_highs(seconds, workers, incumbent, start, cancellation)

    def _optimize_highs(self, seconds, workers, incumbent, start, cancellation=None):
        from games.tw.highs_backend import solve_highs

        if not hasattr(self.economy, "_prepared"):
            self.economy.fingerprint()
        proto = self.economy.build()
        hints = self._decision_hints(incumbent)
        converted = perf_counter()
        result = solve_highs(
            proto,
            seconds=None if seconds is None else max(0.001, seconds - (converted - start)),
            workers=workers,
            incumbent=hints,
            cancellation=cancellation,
        )
        values = result.pop("values")
        result["seconds"] = perf_counter() - start
        result["timings"]["model_conversion_seconds"] += converted - start
        result.update(
            variables=len(proto.variable),
            constraints=len(proto.constraint),
            formulation="linearized_income",
        )
        for key in ("objective", "bound"):
            if result[key] is not None:
                result[key] /= 10000
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": result,
            "exclusions": dict(self.economy.exclusions),
        }
        if values is not None:
            selected = {
                variable.name
                for variable, value in zip(proto.variable, values, strict=True)
                if value > 0.5
            }
            economics = self._evaluate_selected(selected)
            if abs(result["objective"] - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError("Independent economics disagrees with HiGHS")
            report.update(economics)
            report.update(self._proof_metadata(selected))
        return thaw(report)

    def _decision_hints(self, incumbent):
        if incumbent is None:
            return None
        values = self.economy.warm_values(incumbent)
        names = self.economy.decisions.keys() | self.economy.party_variables.keys()
        return {name: values[name] for name in names}

    def _evaluate_selected(self, selected):
        layout = {site.id: [] for site in self.economy.scenario.sites}
        party = None
        for name in selected:
            if name in self.economy.decisions:
                site, key = self.economy.decisions[name]
                layout[site].append(key)
            if name in self.economy.party_variables:
                party = self.economy.party_variables[name]
        return self.economy.evaluate(layout, party)

    def _proof_metadata(self, selected):
        return {
            "proof_fingerprint": self.economy._fingerprint,
            "selected_decision_indices": [
                variable.index
                for variable in self.economy._prepared.variables
                if variable.name in selected
                and (
                    variable.name in self.economy.decisions
                    or variable.name in self.economy.party_variables
                )
            ],
        }

    def _optimize_cpsat(
        self,
        seconds,
        workers,
        incumbent,
        start,
        on_search=None,
        on_model=None,
        cancellation=None,
        on_phase=None,
    ):
        from games.tw.rome2.joint_search import solve

        if not hasattr(self.economy, "_prepared"):
            self.economy.fingerprint()
        proto = self.economy.build()
        problem = NativeCP.from_linear(proto)
        previous = self._cpsat_hints(incumbent, problem)
        result, values = solve(
            problem,
            proto,
            seconds=seconds,
            workers=workers,
            started=start,
            incumbent_income=None if incumbent is None else incumbent["domestic_net_income"],
            on_search=on_search,
            on_model=on_model,
            on_phase=on_phase,
            cancellation=cancellation,
        )
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": result,
            "exclusions": dict(self.economy.exclusions),
        }
        selected = (
            {
                variable.name
                for variable, value in zip(problem.variables, values, strict=True)
                if value > 0
            }
            if values is not None
            else None
        )
        selected = self._retain_incumbent(result, selected, incumbent, previous)
        if selected is not None:
            economics = self._evaluate_selected(selected)
            if abs(result["objective"] - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError("Independent economics disagrees with CP-SAT")
            report.update(economics)
            report.update(self._proof_metadata(selected))
        return thaw(report)

    @staticmethod
    def _retain_incumbent(result, selected, incumbent, previous):
        if incumbent is None:
            return selected
        income = incumbent["domestic_net_income"]
        objective, bound, status = result["objective"], result["bound"], result["status"]
        if status == "INFEASIBLE" or (bound is not None and bound < income - 1e-5):
            raise AssertionError("Native proof contradicts the validated previous incumbent")
        if status == "OPTIMAL" and objective < income - 1e-5:
            raise AssertionError("Native optimum is below the validated previous incumbent")
        if status in {"UNKNOWN", "FEASIBLE"} and (objective is None or income > objective):
            result.setdefault("native_status", status)
            result.update(status="FEASIBLE", objective=income, incumbent_retained=True)
            return previous
        return selected

    def _cpsat_hints(self, incumbent, problem):
        selected = None
        if incumbent is not None:
            values = self.economy.warm_values(incumbent)
            selected = set()
            problem.model.clear_hints()
            for variable in problem.variables:
                if (
                    variable.name in self.economy.decisions
                    or variable.name in self.economy.party_variables
                ):
                    problem.model.add_hint(variable, values[variable.name])
                    if values[variable.name]:
                        selected.add(variable.name)
        return selected
