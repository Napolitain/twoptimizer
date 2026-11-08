"""Mouse and keyboard workbench; engine work stays in cancellable processes."""

from dataclasses import asdict
from datetime import datetime
from time import perf_counter
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    LoadingIndicator,
    Markdown,
    ProgressBar,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from twoptimizer.catalog import EXACT, GAMES, NOTES, choices, faction_name
from twoptimizer.export import export_session
from twoptimizer.models import RunConfig
from twoptimizer.runner import CaseRunner
from twoptimizer.service import make_jobs


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


class HelpScreen(ModalScreen):
    BINDINGS: ClassVar = [("escape", "close", "Close")]

    def compose(self):
        with Vertical(id="dialog"):
            with VerticalScroll():
                yield Markdown("""# Using twoptimizer

Choose a game, faction, province and solver on the left. **All factions** compares
the same holding. **Compare exact solvers** runs each supported formulation.

Mouse clicks, wheel scrolling, **Tab / Shift+Tab**, **arrow keys** and **Enter**
work throughout. Selects support typing to search. Click a result or move with
the arrows to inspect its income, bound and building layout. **Enter** opens the
layout; click column headings to sort.

**Ctrl+R** Run · **Esc** Cancel current batch · **Ctrl+S** Export JSON + CSV ·
**F1** Help · **Ctrl+Q** Quit

Cancellation stops the active solver process and preserves completed cases.
Runs have no time limit by default: they continue to an optimality or infeasibility
proof. Enable the optional time limit to allow an earlier, unfinished result.
CPU parallelism is selected automatically for supported backends.
The status line shows startup, model building, solving and validation. Exported
JSON includes settings, source hashes and original engine details. CSV is a summary.

**OPTIMAL** is a solver proof for the stated model. **FEASIBLE** is a valid layout
with an unresolved bound. **INFEASIBLE** proves the supplied requirements cannot
all hold. **UNKNOWN** means no usable result yet. **ERROR** has details in the log.
Income means the selected game's declared domestic/recurring-income objective;
values from different games are not comparable. See Model notes for assumptions.
""")
            yield Button("Close", id="close", variant="primary")

    def action_close(self):
        self.dismiss()

    @on(Button.Pressed, "#close")
    def close_button(self):
        self.dismiss()


class ExportScreen(ModalScreen):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]

    def __init__(self, results, skipped):
        super().__init__()
        self.results, self.skipped = results, skipped

    def compose(self):
        with Vertical(id="dialog"):
            yield Label("Export results", classes="dialog-title")
            yield Static("Save full JSON and a matching CSV summary.")
            yield Input(
                f"benchmark-results/tui/session-{datetime.now():%Y%m%d-%H%M%S}.json",
                id="export-path",
            )
            yield Checkbox("Replace existing JSON and CSV", id="overwrite")
            yield Static("", id="export-error")
            with Horizontal(classes="dialog-buttons"):
                yield Button("Save", id="save-file", variant="primary")
                yield Button("Cancel", id="cancel-export")

    @on(Button.Pressed, "#save-file")
    @on(Input.Submitted, "#export-path")
    def save(self):
        try:
            paths = export_session(
                self.query_one("#export-path", Input).value,
                self.results,
                skipped=self.skipped,
                overwrite=self.query_one("#overwrite", Checkbox).value,
            )
        except (OSError, ValueError) as error:
            self.query_one("#export-error", Static).update(str(error))
        else:
            self.dismiss(paths)

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#cancel-export")
    def cancel_button(self):
        self.dismiss(None)


class OptimizerApp(App):
    TITLE = "twoptimizer"
    SUB_TITLE = "Total War economy workbench"
    BINDINGS: ClassVar = [
        Binding("ctrl+r", "run", "Run"),
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "export", "Export"),
        Binding("f1", "help", "Help"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "quit", show=False),
    ]
    CSS = """
    Screen { background: #0c1423; }
    Header { background: #14243a; color: #e3eefa; }
    Footer { background: #14243a; }
    #workspace { height: 1fr; }
    #left { width: 36; min-width: 30; background: #101e31; border-right: solid #28405c; }
    #settings { height: 1fr; padding: 1 2; }
    .section-title { color: #68dfcb; text-style: bold; margin-top: 1; }
    .field-label { color: #aec3db; margin-top: 1; height: 1; }
    Select, Input { width: 100%; }
    .option-group { height: auto; }
    #preview { height: auto; min-height: 2; padding: 0 2; color: #b3c5da; }
    #buttons { height: 3; padding: 0 1; }
    #buttons Button { width: 1fr; min-width: 10; margin: 0 1; }
    #right { width: 1fr; padding: 0 1; }
    #intro { height: 2; padding: 0 1; color: #a9bdd6; }
    #stats { height: 5; }
    .stat { width: 1fr; padding: 0 1; border: round #28405c; background: #101e31; }
    .stat Label { color: #9ab1cd; height: 1; }
    .stat Static { color: #e4f8f3; text-style: bold; height: 1; }
    #tabs { height: 1fr; }
    TabPane { padding: 0; }
    DataTable { height: 1fr; background: #101b2c; }
    #selection { height: auto; min-height: 2; padding: 0 1; color: #b4c9dd; }
    #layout-summary { height: auto; padding: 0 1; color: #b4c9dd; }
    #run-status { width: 1fr; height: 2; padding-left: 1; }
    #activity { height: 2; }
    #spinner { width: 5; height: 2; }
    #progress { height: 1; margin: 0 1; }
    #table-actions { height: 3; }
    #table-actions Button { margin-right: 1; }
    #log { height: 1fr; }
    #notes-scroll { height: 1fr; padding: 0 1; }
    HelpScreen, ExportScreen { align: center middle; background: #020814 75%; }
    #dialog {
        width: 76; max-width: 96%; height: auto; max-height: 90%;
        background: #14243a; border: round #68dfcb; padding: 1 2;
    }
    HelpScreen #dialog { height: 28; }
    HelpScreen VerticalScroll { height: 1fr; }
    .dialog-title { text-style: bold; color: #68dfcb; margin-bottom: 1; }
    .dialog-buttons { height: 3; }
    .dialog-buttons Button { margin-right: 1; }
    #export-error { color: #ffae9e; height: auto; margin-bottom: 1; }
    """

    def __init__(self, runner_factory=CaseRunner):
        super().__init__()
        self._ui_ready = False
        self.runner_factory = runner_factory
        self.runner = None
        self.results, self.skipped = [], []
        self.busy = False
        self._loading_settings = True
        self.started = None
        self.current_case = "Ready"
        self.current_phase = ""
        self.sort_column, self.sort_reverse = "income", True

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="left"):
                with VerticalScroll(id="settings"):
                    yield Label("SCENARIO", classes="section-title")
                    yield Label("Game", classes="field-label")
                    yield Select(GAMES, value="rome2", allow_blank=False, id="game")
                    yield Label("Faction / clan", classes="field-label")
                    yield Select([("Loading…", "loading")], allow_blank=False, id="faction")
                    yield Label("Province / holding", classes="field-label")
                    yield Select([("Loading…", "loading")], allow_blank=False, id="province")
                    yield Label("Research", classes="field-label")
                    yield Select([("Loading…", "loading")], allow_blank=False, id="research")
                    with Vertical(classes="option-group", id="rome-options"):
                        yield Checkbox("Regional / wonder bonuses", value=True, id="world-bonuses")
                    with Vertical(classes="option-group", id="attila-options"):
                        yield Label("Fertility", classes="field-label")
                        yield Input("5", id="fertility", type="number")
                        yield Label("Common religion", classes="field-label")
                        from games.tw.models.model_attila import AttilaReligion

                        yield Select(
                            [(r.name.replace("_", " ").title(), r.name) for r in AttilaReligion],
                            value="CHRIST_ORTHODOX",
                            allow_blank=False,
                            id="religion",
                        )
                    with Vertical(classes="option-group", id="shogun-options"):
                        yield Label("Soil", classes="field-label")
                        yield Select(
                            [
                                ("Native province soil", "native"),
                                ("Barren", "barren"),
                                ("Very fertile", "very_fertile"),
                            ],
                            value="native",
                            allow_blank=False,
                            id="soil",
                        )
                        yield Label("Base tax (%)", classes="field-label")
                        yield Input("30", id="tax", type="number")
                        yield Label("Starting town wealth", classes="field-label")
                        yield Input("0", id="town-wealth", type="number")
                    yield Label("SOLVER", classes="section-title")
                    yield Select([("Loading…", "loading")], allow_blank=False, id="algorithm")
                    yield Checkbox("Use a time limit", value=False, id="time-limit")
                    with Vertical(classes="option-group", id="time-options"):
                        yield Label("Solver time limit (seconds)", classes="field-label")
                        yield Input("10", id="seconds", type="number")
                yield Static("", id="preview", markup=False)
                with Horizontal(id="buttons"):
                    yield Button("Run", id="run", variant="primary")
                    yield Button("Cancel", id="cancel", disabled=True)
            with Vertical(id="right"):
                yield Static(
                    "Choose a holding, run a solver, then inspect the results.",
                    id="intro",
                    markup=False,
                )
                with Horizontal(id="stats"):
                    with Vertical(classes="stat"):
                        yield Label("SELECTED INCOME / TURN")
                        yield Static("—", id="income")
                    with Vertical(classes="stat"):
                        yield Label("UPPER BOUND")
                        yield Static("—", id="bound")
                    with Vertical(classes="stat"):
                        yield Label("SOLVER STATUS")
                        yield Static("Ready", id="status")
                with TabbedContent(id="tabs"):
                    with TabPane("Results", id="results-pane"):
                        yield Static(
                            "No results yet. Tab through settings or click Run.",
                            id="selection",
                            markup=False,
                        )
                        yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
                    with TabPane("Buildings", id="buildings-pane"):
                        yield Static(
                            "Select a result to inspect its layout.",
                            id="layout-summary",
                            markup=False,
                        )
                        yield DataTable(id="buildings", cursor_type="row", zebra_stripes=True)
                    with (
                        TabPane("Model notes", id="notes-pane"),
                        VerticalScroll(id="notes-scroll"),
                    ):
                        yield Markdown("", id="model-notes")
                    with TabPane("Log", id="log-pane"):
                        yield RichLog(id="log", wrap=True, max_lines=600, markup=False)
                with Horizontal(id="activity"):
                    yield LoadingIndicator(id="spinner")
                    yield Static(
                        "Ready · Ctrl+R to run · F1 for help",
                        id="run-status",
                        markup=False,
                    )
                yield ProgressBar(total=1, show_eta=False, show_percentage=False, id="progress")
                with Horizontal(id="table-actions"):
                    yield Button("Export JSON + CSV", id="export", disabled=True)
                    yield Button("Clear results", id="clear", disabled=True)
        yield Footer()

    def on_mount(self):
        self._ui_ready = True
        table = self.query_one("#results", DataTable)
        for key, label, width in [
            ("faction", "Faction / clan", 20),
            ("income", "Income", 14),
            ("status", "Status", 12),
            ("gap", "Gap %", 9),
            ("solver", "Solver", 16),
            ("province", "Province", 20),
            ("seconds", "Total s", 10),
        ]:
            table.add_column(label, key=key, width=width)
        table.fixed_columns = 1
        self.query_one("#buildings", DataTable).add_columns("Region", "Building", "Source ID")
        self.query_one("#spinner").display = False
        self._configure_game()
        self.set_interval(0.5, self._tick)
        self.query_one("#game").focus()
        self.call_after_refresh(
            self.query_one("#settings").scroll_home, animate=False, immediate=True
        )

    @on(Select.Changed, "#game")
    def game_changed(self):
        if self._ui_ready:
            self._configure_game()

    def _configure_game(self):
        self._loading_settings = True
        game = str(self.query_one("#game", Select).value)
        options = choices(game)
        available = game in EXACT
        self.query_one("#rome-options").display = game == "rome2"
        self.query_one("#attila-options").display = game == "attila"
        self.query_one("#shogun-options").display = game == "shogun2"
        for field in ("faction", "province", "research", "algorithm"):
            widget = self.query_one("#" + field, Select)
            widget.disabled = not available
            if not available:
                widget.set_options([("Not available yet", "unavailable")])
                widget.value = "unavailable"
        if available:
            for field in ("faction", "province", "research"):
                widget = self.query_one("#" + field, Select)
                values = (
                    options["factions"]
                    if field == "faction"
                    else options["provinces"]
                    if field == "province"
                    else options["research"]
                )
                widget.set_options(
                    ([("All factions / clans", "all"), *values]) if field == "faction" else values
                )
                widget.value = options["default_" + field]
            solvers = [("CP-SAT", "cp-sat"), ("CBC", "cbc"), ("SCIP · MILP", "scip")]
            if game == "rome2":
                solvers = [
                    ("Portfolio · CP-SAT + SCIP", "portfolio"),
                    *solvers,
                    ("SCIP · nonlinear", "scip-nonlinear"),
                ]
            solvers.append(("Compare exact solvers", "compare"))
            self.query_one("#algorithm", Select).set_options(solvers)
            self.query_one("#algorithm", Select).value = (
                "portfolio" if game == "rome2" else "cp-sat"
            )
        self.query_one("#model-notes", Markdown).update(
            "# "
            + {key: label for label, key in GAMES}[game]
            + "\n\n"
            + NOTES[game]
            + (
                "\n\nSelects support typing to search. Each run uses the existing "
                "game engine and independently checks returned layouts. Export "
                "preserves source hashes and the full engine result. CLI commands "
                "remain available for advanced campaign inputs."
            )
        )
        self._loading_settings = False
        self._refresh_preview()

    def _config(self):
        def selected(name):
            return str(self.query_one("#" + name, Select).value)

        game = selected("game")
        try:
            return RunConfig(
                game=game,
                faction=selected("faction"),
                province=selected("province"),
                algorithm=selected("algorithm"),
                research=selected("research"),
                seconds=float(self.query_one("#seconds", Input).value)
                if self.query_one("#time-limit", Checkbox).value
                else None,
                workers=None,
                fertility=float(self.query_one("#fertility", Input).value)
                if game == "attila"
                else 5,
                religion=selected("religion"),
                soil=selected("soil"),
                tax=float(self.query_one("#tax", Input).value) if game == "shogun2" else 30,
                town_wealth=float(self.query_one("#town-wealth", Input).value)
                if game == "shogun2"
                else 0,
                world_bonuses=self.query_one("#world-bonuses", Checkbox).value,
            )
        except ValueError as error:
            raise ValueError("Enter numeric values for the selected settings.") from error

    @on(Select.Changed)
    @on(Input.Changed)
    @on(Checkbox.Changed)
    def settings_changed(self):
        if self._ui_ready and not self._loading_settings and not self.busy:
            self._refresh_preview()

    def _refresh_preview(self):
        self.query_one("#time-options").display = self.query_one("#time-limit", Checkbox).value
        try:
            config = self._config()
            self.query_one("#world-bonuses", Checkbox).disabled = (
                config.game == "rome2" and config.province in {"coastal", "inland", "grain"}
            )
            jobs, skipped = make_jobs(config)
        except ValueError as error:
            self.query_one("#preview", Static).update(str(error))
            self.query_one("#run", Button).disabled = True
        else:
            self.query_one("#preview", Static).update(
                f"{len(jobs)} case{'s' if len(jobs) != 1 else ''} · "
                + (
                    "until proved / cancelled"
                    if config.seconds is None
                    else f"{config.seconds:g}s limit each"
                )
                + (f"\n{len(skipped)} incomplete profiles excluded" if skipped else "")
            )
            self.query_one("#run", Button).disabled = False

    @on(Button.Pressed, "#run")
    def run_button(self):
        self.action_run()

    def action_run(self):
        if self.busy:
            return
        try:
            jobs, self.skipped = make_jobs(self._config())
        except ValueError as error:
            self.notify(str(error), severity="error", timeout=8)
            return
        self.action_clear()
        self.runner = self.runner_factory()
        self.started = perf_counter()
        self._set_busy(True)
        self.query_one("#progress", ProgressBar).update(total=len(jobs), progress=0)
        for message in self.skipped:
            self.query_one("#log", RichLog).write("Excluded: " + message)
        self._solve(jobs)

    def _set_busy(self, busy):
        self.busy = busy
        self.query_one("#settings").disabled = busy
        self.query_one("#run", Button).disabled = busy
        self.query_one("#cancel", Button).disabled = not busy
        self.query_one("#spinner").display = busy
        self.query_one("#export", Button).disabled = busy or not self.results
        self.query_one("#clear", Button).disabled = busy or not self.results
        if not busy:
            self._refresh_preview()

    @work(exclusive=True, group="solve")
    async def _solve(self, jobs):
        runner, started = self.runner, self.started
        if runner is None or started is None:
            raise RuntimeError("Start a run before processing solver jobs")
        log = self.query_one("#log", RichLog)
        errors = 0
        try:
            for i, job in enumerate(jobs, 1):
                if runner.cancelled:
                    break
                self.current_case = (
                    "Case "
                    f"{i}"
                    "/"
                    f"{len(jobs)}"
                    " · "
                    f"{faction_name(job.game, job.faction)}"
                    " · "
                    f"{job.algorithm}"
                )
                self.current_phase = "Starting engine"
                self._tick()
                log.write(self.current_case)
                try:
                    result: dict[str, Any] | None = await runner.run(
                        job,
                        lambda line: log.write(line),
                        on_progress=self._phase_changed,
                    )
                except (RuntimeError, OSError, ValueError) as error:
                    errors += 1
                    log.write(f"ERROR: {error}")
                    result = {
                        "request": asdict(job),
                        "faction": faction_name(job.game, job.faction),
                        "province": {key: label for label, key in choices(job.game)["provinces"]}[
                            job.province
                        ],
                        "solver": {
                            "algorithm": job.algorithm,
                            "status": "ERROR",
                            "seconds": 0,
                            "bound": None,
                        },
                        "income": None,
                        "gap_percent": None,
                        "metrics": {},
                        "buildings": [],
                        "assumptions": NOTES[job.game],
                        "raw": {"error": str(error)},
                    }
                if result is None:
                    break
                self.results.append(result)
                if result.get("timings"):
                    log.write("Timing: " + timing_summary(result))
                if result["solver"].get("timings"):
                    log.write("Solver timing: " + str(result["solver"]["timings"]))
                self._add_result(result)
                self.query_one("#progress", ProgressBar).update(progress=i)
            label = "Cancelled" if runner.cancelled else "Finished"
            self.current_case = f"{label} · {len(self.results)}/{len(jobs)} cases · {errors} errors"
        finally:
            await runner.stop()
            self._set_busy(False)
            self.query_one("#run-status", Static).update(
                self.current_case + f" · {perf_counter() - started:.1f}s elapsed"
            )

    def _tick(self):
        if self.busy and self.started is not None:
            self.query_one("#run-status", Static).update(
                f"{self.current_case}"
                " · "
                f"{self.current_phase}"
                " · "
                f"{perf_counter() - self.started:.1f}"
                "s elapsed"
            )

    def _phase_changed(self, phase):
        self.current_phase = phase
        self._tick()

    def _add_result(self, result):
        table = self.query_one("#results", DataTable)
        gap = result["gap_percent"]
        total_seconds = result.get("timings", {}).get(
            "worker_wall_seconds", result["solver"]["seconds"]
        )
        table.add_row(
            result["faction"],
            money(result["income"]),
            result["solver"]["status"],
            "—" if gap is None else f"{gap:.2f}",
            result["solver"]["algorithm"],
            result["province"],
            f"{total_seconds:.2f}",
            key=str(len(self.results) - 1),
        )
        self._sort_results()
        self._show_result(result)

    def _sort_results(self):
        numeric = self.sort_column in {"income", "gap", "seconds"}

        def key(value):
            if not numeric:
                return str(value).casefold()
            return float(str(value).replace(",", "")) if str(value) != "—" else float("-inf")

        self.query_one("#results", DataTable).sort(
            self.sort_column, key=key, reverse=self.sort_reverse
        )

    @on(DataTable.HeaderSelected, "#results")
    def sort_header(self, event):
        column = str(event.column_key.value)
        self.sort_reverse = (
            not self.sort_reverse if column == self.sort_column else column == "income"
        )
        self.sort_column = column
        self._sort_results()

    @on(DataTable.RowHighlighted, "#results")
    def highlight_result(self, event):
        index = int(event.row_key.value)
        if index < len(self.results):
            self._show_result(self.results[index])

    @on(DataTable.RowSelected, "#results")
    def open_layout(self):
        self.query_one("#tabs", TabbedContent).active = "buildings-pane"
        self.query_one("#buildings", DataTable).focus()

    def _show_result(self, result):
        for key, value in (
            ("income", money(result["income"])),
            ("bound", money(result["solver"].get("bound"))),
            ("status", result["solver"]["status"]),
        ):
            self.query_one("#" + key, Static).update(value)
        settings = result["request"]
        label = (
            f"{result['faction']}"
            " · "
            f"{result['province']}"
            " · "
            f"{settings['game']}"
            " · research: "
            f"{settings['research']}"
        )
        self.query_one("#selection", Static).update(
            label
            + "\nArrow keys browse · Enter opens buildings · click headings to sort"
            + ("\n" + timing_summary(result) if result.get("timings") else "")
        )
        metrics = result["metrics"]
        food, order = metrics.get("food_surplus"), metrics.get("public_order")
        message = label + (
            "\nFood: "
            f"{money(food)}"
            " · Public order: "
            f"{money(order)}"
            " · "
            f"{len(result['buildings'])}"
            " buildings"
        )
        if result["income"] is None:
            message += "\n" + result["raw"].get(
                "error",
                {
                    "INFEASIBLE": (
                        "The solver proved that these requirements cannot all be satisfied."
                    ),
                    "UNKNOWN": (
                        "No usable layout returned. Disable the optional time limit to "
                        "continue until proved."
                    ),
                }.get(
                    result["solver"]["status"],
                    "No validated layout was returned. See the log for details.",
                ),
            )
        self.query_one("#layout-summary", Static).update(message)
        table = self.query_one("#buildings", DataTable)
        table.clear()
        for building in result["buildings"]:
            table.add_row(building["region"], building["building"], building["id"])

    @on(Button.Pressed, "#cancel")
    async def cancel_button(self):
        await self.action_cancel()

    async def action_cancel(self):
        if self.busy and self.runner:
            self.query_one("#run-status", Static).update("Stopping the active solver…")
            await self.runner.stop()

    @on(Button.Pressed, "#export")
    def export_button(self):
        self.action_export()

    def action_export(self):
        if self.busy or not self.results:
            self.notify("Finish or cancel a run before exporting its completed cases.")
            return

        def saved(paths):
            if paths:
                self.notify(f"Saved {paths[0]} and {paths[1]}", timeout=8)

        self.push_screen(ExportScreen(self.results, self.skipped), saved)

    @on(Button.Pressed, "#clear")
    def clear_button(self):
        self.action_clear()

    def action_clear(self):
        if self.busy:
            return
        self.results = []
        self.query_one("#results", DataTable).clear()
        self.query_one("#buildings", DataTable).clear()
        for key in ("income", "bound", "status"):
            self.query_one("#" + key, Static).update("—")
        self.query_one("#selection", Static).update("No results yet. Choose settings and Run.")
        self.query_one("#layout-summary", Static).update("Select a result to inspect its layout.")
        self.query_one("#progress", ProgressBar).update(total=1, progress=0)
        self.query_one("#export", Button).disabled = True
        self.query_one("#clear", Button).disabled = True

    def action_help(self):
        self.push_screen(HelpScreen())

    async def action_quit(self):
        if self.runner:
            await self.runner.stop()
        self.exit()
