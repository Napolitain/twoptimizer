"""Translate optional engine observations into application progress events."""

from twoptimizer.adapters.model_stats import record_cp_result
from twoptimizer.progress import PhaseTimer, SearchStats


def search_observers(phase: PhaseTimer, label: str, decisions, *, phases=False) -> dict:
    observers = {} if phase.cancellation is None else {"cancellation": phase.cancellation}
    if phase.progress is None and not phase.collect_search:
        return observers

    def search(objective, bound, elapsed):
        # The engine observer already throttles; preserve its forced first/final events.
        phase.record_search(SearchStats(label, objective, bound, elapsed), force=True)

    def model(stats):
        record_cp_result(phase, {"algorithm": "cp-sat", "model_stats": stats}, decisions())

    return {
        **observers,
        "on_search": search,
        "on_model": model,
        **({"on_phase": phase.progress} if phases else {}),
    }
