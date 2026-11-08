"""Mouse and keyboard workbench; engine work stays in cancellable processes."""

from dataclasses import asdict
from time import perf_counter
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DataTable,
    Input,
    Markdown,
    ProgressBar,
    RichLog,
    Select,
    Static,
    TabbedContent,
)

from twoptimizer.catalog import EXACT, GAMES, NOTES, choices, faction_name
from twoptimizer.holdings import province_label, selected_provinces
from twoptimizer.models import RunConfig
from twoptimizer.presentation import money, timing_summary
from twoptimizer.province_picker import BorderPicker, ProvincePicker, ProvinceSelection
from twoptimizer.runner import CaseRunner
from twoptimizer.screens import ExportScreen, HelpScreen
from twoptimizer.service import make_jobs
from twoptimizer.workspace import compose_workspace


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
    CSS_PATH = "workspace.tcss"

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
        self.province_selection = ProvinceSelection()

    def compose(self) -> ComposeResult:
        yield from compose_workspace()

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
        self.province_selection = ProvinceSelection()
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

    @on(Button.Pressed, "#choose-provinces")
    def choose_provinces(self):
        game = str(self.query_one("#game", Select).value)
        if self.busy or game not in EXACT:
            return
        self.push_screen(
            ProvincePicker(
                game,
                choices(game)["provinces"],
                self.province_selection,
                str(self.query_one("#province", Select).value),
            ),
            self.provinces_chosen,
        )

    def provinces_chosen(self, state):
        if state is not None:
            self.province_selection = state
            self._refresh_preview()

    @on(Button.Pressed, "#choose-borders")
    def choose_borders(self):
        selected = set(self.province_selection.provinces or ())
        options = [(label, key) for label, key in choices("attila")["provinces"] if key in selected]
        if self.busy or len(options) < 2:
            return
        self.push_screen(
            BorderPicker(options, self.province_selection.adjacency), self.borders_chosen
        )

    def borders_chosen(self, borders):
        if borders is not None:
            self.province_selection = ProvinceSelection(
                self.province_selection.provinces, self.province_selection.joint, borders
            )
            self._refresh_preview()

    def _province_controls(self):
        state = self.province_selection
        game = str(self.query_one("#game", Select).value)
        self.query_one("#province").display = state.provinces is None
        self.query_one("#province-summary").display = state.provinces is not None
        self.query_one("#province-summary", Static).update(
            f"{len(state.provinces or ())} selected · "
            + ("together" if state.joint else "independent")
        )
        self.query_one("#choose-provinces", Button).disabled = game not in EXACT
        self.query_one("#choose-borders").display = (
            game == "attila" and state.joint and len(state.provinces or ()) > 1
        )

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
                provinces=self.province_selection.provinces,
                joint=self.province_selection.joint,
                adjacency=self.province_selection.adjacency
                if self.province_selection.joint
                else None,
            )
        except ValueError as error:
            raise ValueError("Enter numeric values for the selected settings.") from error

    @on(Select.Changed)
    @on(Input.Changed)
    @on(Checkbox.Changed)
    def settings_changed(self):
        if (
            self._ui_ready
            and not self._loading_settings
            and not self.busy
            and not isinstance(self.screen, ModalScreen)
        ):
            self._refresh_preview()

    def _refresh_preview(self):
        self._province_controls()
        self.query_one("#time-options").display = self.query_one("#time-limit", Checkbox).value
        try:
            config = self._config()
            self.query_one("#world-bonuses", Checkbox).disabled = config.game == "rome2" and set(
                selected_provinces(config)
            ) <= {"coastal", "inland", "grain"}
            jobs, skipped = make_jobs(config)
        except ValueError as error:
            self.query_one("#preview", Static).update(str(error))
            self.query_one("#run", Button).disabled = True
        else:
            self.query_one("#preview", Static).update(
                ("Select at least one province.\n" if not jobs else "")
                + f"{len(jobs)} case{'s' if len(jobs) != 1 else ''} · "
                + (
                    "until proved / cancelled"
                    if config.seconds is None
                    else f"{config.seconds:g}s limit each"
                )
                + (f"\n{len(skipped)} incomplete profiles excluded" if skipped else "")
            )
            self.query_one("#run", Button).disabled = not jobs

    @on(Button.Pressed, "#run")
    def run_button(self):
        self.action_run()

    def action_run(self):
        if self.busy or isinstance(self.screen, ModalScreen):
            return
        try:
            jobs, skipped = make_jobs(self._config())
        except ValueError as error:
            self.notify(str(error), severity="error", timeout=8)
            return
        if not jobs:
            self.notify("Select at least one province before running.", severity="warning")
            return
        self.action_clear()
        self.skipped = skipped
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
                    f"{province_label(job)} · "
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
                        "province": province_label(job),
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
