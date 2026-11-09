"""Throttled CP-SAT search snapshots in original objective units.

Callbacks execute on solver threads. Consumers should enqueue snapshots rather
than wait for UI or solver work. Objective conversion is ``native * scale +
offset`` for both minimization and maximization; the scale must be positive.
"""

import math
from collections.abc import Callable
from contextlib import nullcontext
from threading import Lock
from time import monotonic

from ortools.sat.python import cp_model

from games.optimization.cancellation import Cancellation

type SearchCallback = Callable[[float | None, float | None, float], None]

_INTERVAL_SECONDS = 0.75


def _validate_conversion(scale: float, offset: float) -> None:
    for name, value in (("scale", scale), ("offset", offset)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError(f"Progress {name} must be finite")
    if scale <= 0:
        raise ValueError("Progress scale must be positive")


class _Progress:
    def __init__(self, callback: SearchCallback, scale: float, offset: float):
        self.callback = callback
        self.scale, self.offset = scale, offset
        self.started = monotonic()
        self.elapsed = 0.0
        self.last_emitted: float | None = None
        self.objective: float | None = None
        self.has_candidate = False
        self.bound: float | None = None
        self.callback_bound: float | None = None
        self.lock = Lock()

    def convert(self, value: float) -> float | None:
        if not math.isfinite(value):
            return None
        converted = value * self.scale + self.offset
        return converted if math.isfinite(converted) else None

    def solution(self, objective: float, bound: float) -> None:
        with self.lock:
            self.objective = self.convert(objective)
            self.bound = self.convert(bound)
            first_candidate = not self.has_candidate and self.objective is not None
            self.has_candidate |= self.objective is not None
            self.emit(force=first_candidate)

    def best_bound(self, bound: float) -> None:
        with self.lock:
            converted = self.convert(bound)
            if converted is not None:
                self.bound = self.callback_bound = converted
            self.emit()

    def final(self, solver: cp_model.CpSolver, status) -> None:
        with self.lock:
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                self.objective = self.convert(solver.objective_value)
                self.bound = self.convert(solver.best_objective_bound)
            else:
                # UNKNOWN's response can contain an uncertified default zero.
                self.objective = None
                self.bound = self.callback_bound
            self.emit(force=True)

    def emit(self, *, force: bool = False) -> None:
        """Caller owns the lock through delivery, serializing user callbacks too."""
        self.elapsed = max(self.elapsed, monotonic() - self.started)
        if (
            not force
            and self.last_emitted is not None
            and self.elapsed - self.last_emitted < _INTERVAL_SECONDS
        ):
            return
        self.last_emitted = self.elapsed
        self.callback(self.objective, self.bound, self.elapsed)


class _SolutionObserver(cp_model.CpSolverSolutionCallback):
    def __init__(self, progress: _Progress):
        super().__init__()
        self.progress = progress

    def on_solution_callback(self) -> None:
        self.progress.solution(self.objective_value, self.best_objective_bound)


def _native_solve(solver, model, observer, cancellation):
    context = nullcontext() if cancellation is None else cancellation.interrupt(solver.stop_search)
    with context:
        return solver.solve(model) if observer is None else solver.solve(model, observer)


def solve_with_progress(
    solver: cp_model.CpSolver,
    model: cp_model.CpModel,
    *,
    on_search: SearchCallback | None = None,
    scale: float = 1.0,
    offset: float = 0.0,
    cancellation: Cancellation | None = None,
):
    """Solve without changing the model or solver parameters; return native status.

    ``original = native * scale + offset``. With no observer this uses the plain
    ``solver.solve(model)`` call. Otherwise it reports solutions and bound
    updates at most once per 0.75 seconds, except that the first event, first
    actual candidate and final normal return are always reported. A solution is
    required before reporting an incumbent. UNKNOWN bounds are reported only if
    a bound callback supplied one.

    An existing bound callback still receives every raw bound. It is restored
    even when solving or a callback raises; final progress is never emitted from
    exception cleanup. Callback exceptions propagate to the caller.
    """
    _validate_conversion(scale, offset)
    if on_search is None:
        return _native_solve(solver, model, None, cancellation)

    progress = _Progress(on_search, scale, offset)
    previous = solver.best_bound_callback

    def bound_callback(bound: float) -> None:
        if previous is not None:
            previous(bound)
        progress.best_bound(bound)

    try:
        solver.best_bound_callback = bound_callback
        status = _native_solve(solver, model, _SolutionObserver(progress), cancellation)
    finally:
        solver.best_bound_callback = previous
    progress.final(solver, status)
    return status
