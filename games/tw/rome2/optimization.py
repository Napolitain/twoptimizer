"""Solver execution, proof reuse and independent result verification."""

from __future__ import annotations

import copy
from time import perf_counter
from typing import TYPE_CHECKING

from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

from games.tw.immutable import thaw
from games.tw.resources import resolve_workers
from games.tw.rome2.backends import NativeCP

if TYPE_CHECKING:
    from games.tw.rome2.model import Economy


class RomeOptimizer:
    def __init__(self, economy: Economy):
        self.economy = economy

    def _linear_backend(self, proto, algorithm, seconds, workers):
        solver = pywraplp.Solver.CreateSolver(
            {"cp-sat": "SAT", "cbc": "CBC", "scip": "SCIP"}[algorithm]
        )
        error = solver.LoadModelFromProtoKeepNames(proto)
        if error:
            raise ValueError(error)
        if seconds is not None:
            solver.SetTimeLimit(max(1, int(seconds * 1000)))
        effective_workers = 1
        if algorithm == "scip" and solver.SetNumThreads(workers):
            effective_workers = workers
        if algorithm == "cp-sat":
            solver.SetSolverSpecificParametersAsString(
                f"num_search_workers: {workers}\nrandom_seed: 0"
            )
        parameters = pywraplp.MPSolverParameters()
        parameters.SetDoubleParam(parameters.RELATIVE_MIP_GAP, 0.0)
        status = solver.Solve(parameters)
        return solver, status, effective_workers

    def optimize(self, algorithm="cp-sat", seconds=None, workers=None, incumbent=None):
        workers = resolve_workers(workers)
        start = perf_counter()
        if algorithm == "portfolio":
            return self._optimize_portfolio(seconds, workers, incumbent, start)
        if algorithm == "scip-nonlinear":
            return self._optimize_scip(seconds, workers, incumbent, start)
        if algorithm == "cp-sat":
            return self._optimize_cpsat(seconds, workers, incumbent, start)
        proto = self.economy.build()
        if algorithm not in {"cp-sat", "cbc", "scip"}:
            raise ValueError("Choose cp-sat, cbc or scip")
        solver, status, effective_workers = self._linear_backend(proto, algorithm, seconds, workers)
        label = {
            solver.OPTIMAL: "OPTIMAL",
            solver.FEASIBLE: "FEASIBLE",
            solver.INFEASIBLE: "INFEASIBLE",
            solver.NOT_SOLVED: "UNKNOWN",
            solver.MODEL_INVALID: "MODEL_INVALID",
            solver.ABNORMAL: "ABNORMAL",
        }.get(status, "UNKNOWN")
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": {
                "algorithm": algorithm,
                "status": label,
                "seconds": perf_counter() - start,
                "objective": None,
                "bound": None,
                "variables": len(proto.variable),
                "constraints": len(proto.constraint),
                "workers": effective_workers,
            },
            "exclusions": dict(self.economy.exclusions),
        }
        if status in (solver.OPTIMAL, solver.FEASIBLE):
            if not solver.VerifySolution(1e-5, False):
                raise AssertionError("Solver returned an invalid integer model solution")
            layout, selected_party = self._read_linear_solution(solver)
            economics = self.economy.evaluate(layout, selected_party)
            objective = solver.Objective().Value() / 10000
            if abs(objective - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError("Independent economics disagrees with solver objective")
            report["solver"].update(
                objective=objective, bound=solver.Objective().BestBound() / 10000
            )
            report.update(economics)
        return thaw(report)

    def _read_linear_solution(self, solver):
        layout = {site.id: [] for site in self.economy.scenario.sites}
        selected_party = None
        for variable in solver.variables():
            if variable.solution_value() > 0.5:
                if variable.name() in self.economy.decisions:
                    site, key = self.economy.decisions[variable.name()]
                    layout[site].append(key)
                if variable.name() in self.economy.party_variables:
                    selected_party = self.economy.party_variables[variable.name()]
        return layout, selected_party

    def _optimize_portfolio(self, seconds, workers, incumbent, start):
        first = self.optimize(
            "cp-sat", 5 if seconds is None else seconds * 0.35, workers, incumbent
        )
        if first["solver"]["status"] == "OPTIMAL":
            first["solver"]["algorithm"] = "portfolio"
            first["solver"]["proof_backend"] = "cp-sat"
            return first
        seed = first if "sites" in first else incumbent
        second = self.optimize(
            "scip-nonlinear",
            None if seconds is None else max(0.01, seconds - (perf_counter() - start)),
            workers,
            seed,
        )
        feasible = [r for r in (first, second) if "sites" in r]
        if not feasible:
            return second
        result = copy.deepcopy(max(feasible, key=lambda r: r["domestic_net_income"]))
        bounds = [r["solver"]["bound"] for r in (first, second) if r["solver"]["bound"] is not None]
        proven = next((r for r in (first, second) if r["solver"]["status"] == "OPTIMAL"), None)
        result["solver"].update(
            algorithm="portfolio",
            seconds=perf_counter() - start,
            bound=min(bounds) if bounds else None,
            status="OPTIMAL" if proven else "FEASIBLE",
            proof_backend=proven["solver"]["algorithm"] if proven else None,
            stages=[first["solver"], second["solver"]],
        )
        return result

    def _add_scip_incumbent(self, incumbent, solver, problem):
        if incumbent is not None:
            values = self.economy.warm_values(incumbent)
            solution = solver.createSol()
            for variable in problem.variables:
                solver.setSolVal(solution, variable, values[variable.name])
            if not solver.addSol(solution):
                raise ValueError("SCIP rejected independently validated warm start")

    def _optimize_scip(self, seconds, workers, incumbent, start):
        algorithm = "scip-nonlinear"
        problem = self.economy.build(native="scip-nonlinear")
        solver = problem.model
        if seconds is not None:
            solver.setParam("limits/time", seconds)
        solver.setParam("numerics/feastol", 1e-9)
        self._add_scip_incumbent(incumbent, solver, problem)
        solver.optimize()
        status = str(solver.getStatus()).upper()
        label = (
            "OPTIMAL"
            if status == "OPTIMAL"
            else "INFEASIBLE"
            if status == "INFEASIBLE"
            else "FEASIBLE"
            if solver.getNSols()
            else "UNKNOWN"
        )
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": {
                "algorithm": algorithm,
                "status": label,
                "seconds": perf_counter() - start,
                "objective": None,
                "bound": None,
                "variables": len(problem.variables),
                "constraints": solver.getNConss(),
                "workers": 1,
            },
            "exclusions": dict(self.economy.exclusions),
        }
        if solver.getNSols():
            layout = {site.id: [] for site in self.economy.scenario.sites}
            party = None
            for variable in problem.variables:
                if solver.getVal(variable) > 0.5:
                    if variable.name in self.economy.decisions:
                        site, key = self.economy.decisions[variable.name]
                        layout[site].append(key)
                    if variable.name in self.economy.party_variables:
                        party = self.economy.party_variables[variable.name]
            economics = self.economy.evaluate(layout, party)
            objective = solver.getObjVal() / 10000
            if abs(objective - economics["domestic_net_income"]) > 1e-5:
                raise AssertionError("Independent economics disagrees with nonlinear SCIP")
            report["solver"].update(objective=objective, bound=solver.getDualbound() / 10000)
            report.update(economics)
        return thaw(report)

    def _optimize_cpsat(self, seconds, workers, incumbent, start):
        algorithm = "cp-sat"
        if not hasattr(self.economy, "_prepared"):
            self.economy.fingerprint()
        canonical = self.economy._prepared
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
        search_start = perf_counter()
        status = solver.solve(problem.model)
        report = {
            "scenario": self.economy.scenario.to_dict(),
            "solver": {
                "algorithm": algorithm,
                "status": solver.status_name(status),
                "seconds": perf_counter() - start,
                "objective": None,
                "bound": None,
                "variables": len(problem.model.proto.variables),
                "constraints": len(problem.model.proto.constraints),
                "workers": workers,
                "formulation": "linearized_income",
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
            report["proof_fingerprint"] = self.economy._fingerprint
            selected = {
                v.name
                for v in problem.variables
                if (v.name in self.economy.decisions or v.name in self.economy.party_variables)
                and solver.value(v)
            }
            report["selected_decision_indices"] = [
                v.index for v in canonical.variables if v.name in selected
            ]
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
