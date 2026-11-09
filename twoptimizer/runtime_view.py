"""Runtime context for a TUI session, independent of widgets and solver execution."""

from collections.abc import Sequence

from twoptimizer.models import RunConfig
from twoptimizer.presentation import (
    bound_preparation_summary,
    search_measurement_summary,
    search_summary,
)
from twoptimizer.progress import ModelStats, ProgressEvent, SearchStats
from twoptimizer.runtime_evidence import runtime_details, runtime_outlook
from twoptimizer.runtime_history import RuntimeHistory
from twoptimizer.search_activity import SearchActivity, format_duration

RUNTIME_NOTE = (
    "A candidate can appear long before optimality is proved. The income gap is not "
    "a percentage of work completed. Quiet search can still be working on a proof; "
    "no improvement does not establish failure or predict a finish time. "
    "Time limits and cancellation leave unfinished work, not an infeasibility proof."
)


def case_status(result: dict | None) -> str:
    """A comparison is finished only when both searches have terminal proofs."""
    if result is None:
        return "CANCELLED"
    statuses = {result["solver"]["status"]}
    comparison = result.get("raw", {}).get("constraint_comparison", {})
    baseline = comparison.get("baseline")
    if baseline:
        statuses.add(baseline["solver"]["status"])
        if statuses == {"OPTIMAL"} and comparison.get("status") == "unavailable":
            return "ERROR"
    if statuses <= {"OPTIMAL", "INFEASIBLE"}:
        return "INFEASIBLE" if "INFEASIBLE" in statuses else "OPTIMAL"
    if not statuses <= {"OPTIMAL", "INFEASIBLE", "FEASIBLE", "UNKNOWN"}:
        return "ERROR"
    return "FEASIBLE" if "FEASIBLE" in statuses or "OPTIMAL" in statuses else "UNKNOWN"


class RuntimeView:
    def __init__(self):
        self.history = RuntimeHistory()
        self.search = SearchActivity()
        self.job: RunConfig | None = None
        self.started = 0.0
        self.finished: float | None = None
        self.outcome: str | None = None
        self.phase = "Starting engine"
        self.searching = False
        self.stop_requested = False
        self.retained = False
        self.measurement_details = ""

    def preview(self, config: RunConfig, jobs: Sequence[RunConfig]) -> tuple[str, str]:
        summary = self.history.summary(jobs) or runtime_outlook(config, jobs)
        details = self.history.details(jobs) + "\n\n" + runtime_details(config, jobs)
        return summary, details

    def begin(self, job: RunConfig, now: float) -> None:
        self.job, self.started = job, now
        self.finished = self.outcome = None
        self.phase, self.searching = "Starting engine", False
        self.stop_requested = self.retained = False
        self.measurement_details = ""
        self.search = SearchActivity()

    @property
    def stop_message(self) -> str:
        if self.job is not None and self.job.algorithm == "highs":
            return (
                "Cancellation requested. HiGHS cannot interrupt native search here; "
                "wait for its result or use Force stop."
            )
        return "Stopping search; validating the best layout found. Force stop may discard it."

    def observe(self, event: ProgressEvent, now: float) -> None:
        if self.job is None or self.finished is not None:
            return
        if isinstance(event, SearchStats):
            self.search.observe(event, now)
            self.searching = True
        elif isinstance(event, ModelStats):
            if event.stage == "solver" and self.job.algorithm == "cp-sat":
                self.search.begin(now)
                self.searching = True
        else:
            self.phase, self.searching = event, False

    def finish(self, result: dict | None, now: float) -> None:
        if self.job is None or self.finished is not None:
            return
        self.finished, self.outcome = now, case_status(result)
        if result is not None:
            self.stop_requested |= (
                result.get("raw", {}).get("cancellation", {}).get("requested", False)
            )
            self.retained = self.stop_requested and result.get("income") is not None
            self.measurement_details = "\n".join(
                text
                for text in (
                    search_measurement_summary(
                        result.get("raw", {}).get("search_measurements", {})
                    ),
                    bound_preparation_summary(result["solver"].get("joint_bound_search") or {}),
                )
                if text
            )
        self.history.record(self.job, self.outcome, max(0.0, now - self.started))
        self.searching = False

    def details(self, now: float) -> str:
        if self.job is None:
            return "No active case.\n\n" + RUNTIME_NOTE
        end = self.finished if self.finished is not None else now
        elapsed = format_duration(max(0.0, end - self.started))
        if self.outcome is not None:
            return self._finished_details(elapsed)
        lines = [f"Active case: {elapsed} elapsed", "Phase: " + self.phase]
        if self.stop_requested:
            lines.append(self.stop_message)
        if self.job.algorithm == "highs":
            lines.append("HiGHS does not stream candidate/bound progress here; completion unknown.")
        elif self.searching:
            snapshot = self.search.snapshot(now)
            lines.append(self.search.summary(now))
            if snapshot.stats is not None:
                lines.append(search_summary(snapshot.stats))
        else:
            lines.append("Preparation or validation is running; no search ETA is available.")
        return "\n".join(lines) + "\n\n" + RUNTIME_NOTE

    def _finished_details(self, elapsed: str) -> str:
        outcome = {
            "OPTIMAL": "Optimality proved",
            "INFEASIBLE": "Infeasibility proved",
            "FEASIBLE": "Finished with candidate(s); proof unfinished",
            "UNKNOWN": "Finished without a proof or validated candidate",
            "CANCELLED": "Cancelled; active case unfinished",
            "ERROR": "Case or comparison failed; inspect results and log",
        }.get(self.outcome, self.outcome)
        retained = "\nCancellation requested; validated layout retained." if self.retained else ""
        measurements = "\n\n" + self.measurement_details if self.measurement_details else ""
        return (
            f"Last case: {elapsed} elapsed · {outcome}{retained}{measurements}\n\n" + RUNTIME_NOTE
        )
