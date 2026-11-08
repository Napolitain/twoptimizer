"""Formatting shared by terminal result views."""


def money(value):
    return "—" if value is None else f"{value:,.3f}"


def timing_summary(result):
    times = result.get("timings", {})
    return " · ".join(
        f"{label} {times[key]:.2f}s"
        for key, label in (
            ("worker_startup_seconds", "Start"),
            ("load_engine_seconds", "Load"),
            ("build_model_seconds", "Build"),
            ("solve_and_check_seconds", "Solve/check"),
            ("worker_wall_seconds", "Total"),
        )
        if key in times
    )
