"""Readable income comparisons without confusing incumbents with proven optima."""

from twoptimizer.presentation import money

COMPARISON_NOTE = (
    "The baseline removes required/forbidden buildings and the optional religious-influence "
    "minimum. Faith, Nanban contact, campaign inputs and world settings stay the same."
)
COMPARISON_EMPTY = (
    "Enable Compare income without requirements, add optional building or influence "
    "requirements, then run and select a result.\n\n" + COMPARISON_NOTE
)


def comparison_summary(result: dict) -> str:
    comparison = result.get("raw", {}).get("constraint_comparison")
    if comparison is None:
        if result.get("request", {}).get("compare_constraints"):
            return (
                "No comparison was returned for this result. Check the case status and "
                "whether any optional building or influence requirements are set.\n\n"
                + COMPARISON_NOTE
            )
        return COMPARISON_EMPTY
    lines = [
        f"Income without requirements: {money(comparison.get('baseline_income'))}",
        f"Income with requirements: {money(comparison.get('constrained_income'))}",
    ]
    status = comparison.get("status")
    if status == "exact":
        lines.append(f"Proven income loss: {money(comparison.get('exact_cost'))} per turn")
        if comparison.get("percent") is not None:
            lines.append(f"{comparison['percent']:.2f}% of income without requirements")
    elif status == "bounded":
        lines.extend(_bounded_summary(comparison))
    else:
        lines.append("Income cost unavailable: " + comparison.get("reason", "No valid comparison."))
    baseline = comparison.get("baseline", {})
    if baseline:
        lines.append(
            "Solver status: without requirements "
            f"{baseline.get('solver', {}).get('status', 'unknown')} · "
            f"with requirements {result.get('solver', {}).get('status', 'unknown')}"
        )
    lines.extend(("", COMPARISON_NOTE))
    return "\n".join(lines)


def _bounded_summary(comparison):
    upper = comparison.get("cost_upper")
    interval = (
        f"{money(comparison.get('cost_lower'))} to {money(upper)} per turn"
        if upper is not None
        else f"at least {money(comparison.get('cost_lower'))}; no finite upper bound"
    )
    lines = ["Income-loss bounds: " + interval, "Exact income loss is not yet proved."]
    observed = comparison.get("observed_income_difference")
    if observed is not None:
        lines.append(
            f"Observed income difference: {money(observed)} "
            "(current layouts, without minus with requirements)."
        )
    return lines


def comparison_rows(result: dict) -> list[tuple[str, str, str, str]]:
    comparison = result.get("raw", {}).get("constraint_comparison", {})
    return [
        (label, row["region"], row["building"], row["id"])
        for key, label in (("added_buildings", "Added"), ("removed_buildings", "Removed"))
        for row in comparison.get(key, ())
    ]
