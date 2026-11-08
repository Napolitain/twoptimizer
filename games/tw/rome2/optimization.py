"""Solver execution, proof reuse and independent result verification."""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from games.tw.immutable import thaw
from games.tw.resources import resolve_workers
from games.tw.rome2.backends import NativeCP

if TYPE_CHECKING:
    from games.tw.rome2.model import Economy


def _native_statistics(problem, observer):
    stats = {
        "formulation": "linearized_income",
        "variables": len(problem.model.proto.variables),
        "constraints": len(problem.model.proto.constraints),
    }
    if observer is not None:
        observer(stats)
    return stats


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
    ):
        if algorithm not in {"cp-sat", "highs"}:
            raise ValueError("Choose cp-sat or highs")
        workers = resolve_workers(workers)
        start = perf_counter()
        if algorithm == "cp-sat":
            return self._optimize_cpsat(seconds, workers, incumbent, start, on_search, on_model)
        return self._optimize_highs(seconds, workers, incumbent, start)

    def _optimize_highs(self, seconds, workers, incumbent, start):
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

    def _optimize_cpsat(self, seconds, workers, incumbent, start, on_search=None, on_model=None):
        algorithm = "cp-sat"
        if not hasattr(self.economy, "_prepared"):
            self.economy.fingerprint()
        problem = NativeCP.from_linear(self.economy.build())
        self._cpsat_hints(incumbent, problem)
        error = problem.model.validate()
        if error:
            raise ValueError(error)
        solver = cp_model.CpSolver()
        if seconds is not None:
            solver.parameters.max_time_in_seconds = max(0.001, seconds - (perf_counter() - start))
        solver.parameters.num_search_workers = workers
        solver.parameters.random_seed = 0
        solver.parameters.linearization_level = 2
        stats = _native_statistics(problem, on_model)
        from games.tw.search_progress import solve_with_progress

        search_start = perf_counter()
        status = solve_with_progress(solver, problem.model, on_search=on_search, scale=1 / 10000)
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": {
                "algorithm": algorithm,
                "status": solver.status_name(status),
                "seconds": perf_counter() - start,
                "objective": None,
                "bound": None,
                **stats,
                "workers": workers,
                "timings": {
                    "model_conversion_seconds": search_start - start,
                    "search_seconds": perf_counter() - search_start,
                },
            },
            "exclusions": dict(self.economy.exclusions),
        }
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            layout = {site.id: [] for site in self.economy.scenario.sites}
            party = None
            for variable in problem.variables:
                if solver.value(variable) > 0:
                    if variable.name in self.economy.decisions:
                        site, key = self.economy.decisions[variable.name]
                        layout[site].append(key)
                    if variable.name in self.economy.party_variables:
                        party = self.economy.party_variables[variable.name]
            economics = self.economy.evaluate(layout, party)
            objective = solver.objective_value / 10000
            if abs(objective - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError("Independent economics disagrees with CP-SAT")
            report["solver"].update(objective=objective, bound=solver.best_objective_bound / 10000)
            report.update(economics)
            selected = {
                v.name
                for v in problem.variables
                if (v.name in self.economy.decisions or v.name in self.economy.party_variables)
                and solver.value(v)
            }
            report.update(self._proof_metadata(selected))
        return thaw(report)

    def _cpsat_hints(self, incumbent, problem):
        if incumbent is not None:
            values = self.economy.warm_values(incumbent)
            problem.model.clear_hints()
            for variable in problem.variables:
                if (
                    variable.name in self.economy.decisions
                    or variable.name in self.economy.party_variables
                ):
                    problem.model.add_hint(variable, values[variable.name])
