"""Formatting shared by terminal result views."""

from collections.abc import Sequence

from twoptimizer.holdings import BORDER_GAMES, resolved_borders
from twoptimizer.models import RunConfig
from twoptimizer.progress import ModelStats, SearchStats

MODEL_SIZE_NOTE = (
    "Counts describe the formulation before presolve. Model size does not predict "
    "runtime or guarantee a quick proof. Reported storage covers the constraint "
    "matrix, not total solver memory."
)


def money(value):
    return "—" if value is None else f"{value:,.3f}"


def search_summary(stats: SearchStats) -> str:
    """Keep unfinished candidates separate from independently checked results."""
    bound_label = "upper bound" if stats.sense == "maximize" else "lower bound"
    candidate = "not found" if stats.objective is None else money(stats.objective)
    bound = "unknown" if stats.bound is None else money(stats.bound)
    gap = "unknown" if stats.gap_percent is None else f"{stats.gap_percent:.2f}%"
    units = f" {stats.unit}" if stats.unit else ""
    return (
        f"{stats.label} · solver candidate: {candidate}{units}\n"
        f"{bound_label.capitalize()}: {bound} · gap: {gap}\n"
        f"Search {stats.elapsed_seconds:.1f}s · unfinished; validation pending"
    )


def primary_metric(result: dict) -> dict:
    """Read an explicit primary objective without calling another quantity income."""
    if result.get("objectives"):
        objective = result["objectives"][0]
        return {**objective, "status": objective.get("status") or result["solver"]["status"]}
    return {
        "identifier": "income",
        "label": "Income",
        "unit": "",
        "sense": "maximize",
        "value": result["income"],
        "bound": result["solver"].get("bound"),
        "status": result["solver"]["status"],
    }


def objective_summary(result: dict) -> str:
    """Describe lexicographic priorities with their individual proof statuses."""
    objectives = result.get("objectives") or (primary_metric(result),)
    return "\n".join(
        f"{index}. {objective['label']}: {money(objective['value'])}"
        + (f" {objective['unit']}" if objective.get("unit") else "")
        + f" · {objective['sense']} · {objective.get('status') or result['solver']['status']}"
        for index, objective in enumerate(objectives, 1)
    )


def timing_summary(result):
    times = result.get("timings", {})
    return " · ".join(
        f"{label} {times[key]:.2f}s"
        for key, label in (
            ("worker_startup_seconds", "Start"),
            ("worker_dispatch_seconds", "Dispatch"),
            ("load_engine_seconds", "Load"),
            ("build_model_seconds", "Build"),
            ("solve_and_check_seconds", "Solve/check"),
            ("worker_wall_seconds", "Total"),
        )
        if key in times
    )


def query_summary(config: RunConfig, jobs: Sequence[RunConfig], skipped: Sequence[str]) -> str:
    """Describe expanded requests without compiling any optimization models."""
    provinces = len(config.holdings)
    factions = len({job.faction for job in jobs})
    solvers = len({job.algorithm for job in jobs})
    lines = [
        f"{provinces} province{'s' if provinces != 1 else ''} · "
        + ("together" if config.joint else "independent"),
        f"{factions} faction{'s' if factions != 1 else ''} · "
        f"{solvers} solver choice{'s' if solvers != 1 else ''}",
        f"{len(jobs)} case{'s' if len(jobs) != 1 else ''} · "
        + (
            "until proved / cancelled"
            if config.seconds is None
            else f"{config.seconds:g}s limit each"
        ),
    ]
    if config.joint and config.game in BORDER_GAMES and provinces > 1:
        lines.insert(1, border_summary(config))
    if not jobs:
        lines.append("Select at least one province.")
    if skipped:
        lines.append(f"{len(skipped)} incomplete profiles excluded")
    return "\n".join(lines)


def border_summary(config: RunConfig) -> str:
    borders = len(resolved_borders(config))
    source = "automatic"
    if config.adjacency is not None:
        source = "custom"
    elif config.attila.campaign is not None and "adjacency" in config.attila.campaign.data:
        source = "campaign"
    kind = "map" if source == "automatic" else "supplied"
    return f"{borders} {kind} border{'s' if borders != 1 else ''} · {source}"


def model_size_summary(models: Sequence[ModelStats]) -> str:
    if not models:
        return "Model size: no counts recorded for this case"
    current = models[-1]
    return (
        f"Model size: {current.variables:,} vars · {current.constraints:,} constraints"
        f" · {current.stage}"
    )


def model_details(models: Sequence[ModelStats], title: str) -> str:
    sections = [title]
    for model in models:
        lines = [
            f"{model.label} · {model.stage} model",
            f"Variables: {model.variables:,} · Constraints: {model.constraints:,}",
        ]
        if model.formulation:
            lines.append("Formulation: " + model.formulation.replace("_", " "))
        if model.decision_variables is not None:
            lines.append(
                f"Decision variables: {model.decision_variables:,} · "
                f"Auxiliary variables: {model.variables - model.decision_variables:,}"
            )
        if model.nonzeros is not None:
            lines.append(f"Nonzero coefficients: {model.nonzeros:,}")
        if model.storage_bytes is not None:
            lines.append(f"Constraint matrix storage: {model.storage_bytes / 1024**2:,.2f} MiB")
        sections.append("\n".join(lines))
    if not models:
        sections.append("No model counts recorded for this case.")
    sections.append(MODEL_SIZE_NOTE)
    return "\n\n".join(sections)
