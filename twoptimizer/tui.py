"""Mouse and keyboard workbench; engine work stays in cancellable processes."""

from dataclasses import replace
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
    SelectionList,
    Static,
    TabbedContent,
)

from games.tw.maps.catalog import province_borders
from twoptimizer.catalog import EXACT, GAMES, NOTES, choices, faction_name
from twoptimizer.comparison_presentation import (
    COMPARISON_EMPTY,
    comparison_rows,
    comparison_summary,
)
from twoptimizer.constraint_catalog import building_choices
from twoptimizer.constraint_options import ConstraintOptions
from twoptimizer.constraint_picker import ConstraintPicker, constraint_count
from twoptimizer.hoi4_data_screen import HoI4DataScreen
from twoptimizer.holdings import (
    BORDER_GAMES,
    named_province_choices,
    province_label,
    selected_provinces,
)
from twoptimizer.models import RunConfig
from twoptimizer.presentation import (
    MODEL_SIZE_NOTE,
    model_details,
    model_size_summary,
    money,
    query_summary,
    search_summary,
    timing_summary,
)
from twoptimizer.progress import ModelStats, SearchStats
from twoptimizer.province_picker import (
    USE_MAP_BORDERS,
    BorderPicker,
    ProvincePicker,
    ProvinceSelection,
)
from twoptimizer.runner import BatchRunner
from twoptimizer.runtime_view import RuntimeView
from twoptimizer.screens import ExportScreen, HelpScreen
from twoptimizer.search_activity import format_duration
from twoptimizer.service import error_result, make_jobs
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions
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

    def __init__(self, runner_factory=BatchRunner):
        super().__init__()
        self._ui_ready = False
        self.runner_factory = runner_factory
        self.runner = None
        self.results, self.skipped = [], []
        self.busy = False
        self.stop_requested = False
        self.force_stopping = False
        self._loading_settings = True
        self.started = None
        self.current_case = "Ready"
        self.current_phase = ""
        self.current_models: list[ModelStats] = []
        self.current_search: SearchStats | None = None
        self.runtime = RuntimeView()
        self.sort_column, self.sort_reverse = "income", True
        self.province_selection = ProvinceSelection()
        self.constraint_options = ConstraintOptions()

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
        self.query_one("#constraint-changes", DataTable).add_columns(
            "Change", "Region", "Building", "Source ID"
        )
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
        self.constraint_options = ConstraintOptions()
        self.query_one("#compare-constraints", Checkbox).value = False
        game = str(self.query_one("#game", Select).value)
        options = choices(game)
        available = game in EXACT
        self.query_one("#hoi4-data").display = game == "hoi4"
        self.query_one("#rome-options").display = game == "rome2"
        self.query_one("#attila-options").display = game == "attila"
        self.query_one("#shogun-options").display = game == "shogun2"
        self.query_one("#three-kingdoms-options").display = game == "three_kingdoms"
        self._configure_three_kingdoms(game, options)
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
            solvers = [("CP-SAT", "cp-sat"), ("HiGHS", "highs")]
            solvers.append(("Compare exact solvers", "compare"))
            self.query_one("#algorithm", Select).set_options(solvers)
            self.query_one("#algorithm", Select).value = "cp-sat"
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

    def _configure_three_kingdoms(self, game, options):
        if game != "three_kingdoms":
            return
        from games.tw.three_kingdoms.catalog import load_data

        capital = self.query_one("#three-kingdoms-capital", Select)
        capital.set_options(
            [("Not specified · capital-only buildings excluded", "none"), *options["provinces"]]
        )
        capital.value = "none"
        resources = self.query_one("#three-kingdoms-resources", SelectionList)
        resources.clear_options()
        resources.add_options(
            [(label, key, False) for key, label in load_data()["resources"].items()]
        )

    @on(Button.Pressed, "#hoi4-data")
    def inspect_hoi4_data(self):
        if not self.busy and str(self.query_one("#game", Select).value) == "hoi4":
            self.push_screen(HoI4DataScreen())

    @on(Button.Pressed, "#choose-constraints")
    def choose_constraints(self):
        if self.busy or str(self.query_one("#game", Select).value) not in EXACT:
            return
        try:
            config = self._config()
            discovery = replace(
                config,
                constraints=replace(
                    config.constraints, required_buildings=(), forbidden_buildings=()
                ),
            )
            buildings = building_choices(discovery)
        except ValueError as error:
            self.notify(str(error), severity="error", timeout=8)
            return
        self.push_screen(
            ConstraintPicker(config.game, buildings, self.constraint_options, joint=config.joint),
            self.constraints_chosen,
        )

    def constraints_chosen(self, options):
        if options is not None:
            self.constraint_options = options
            self._refresh_preview()

    @on(Button.Pressed, "#choose-provinces")
    def choose_provinces(self):
        game = str(self.query_one("#game", Select).value)
        if self.busy or game not in EXACT:
            return
        self.push_screen(
            ProvincePicker(
                game,
                named_province_choices(game),
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
        game = str(self.query_one("#game", Select).value)
        selected = set(self.province_selection.provinces or ())
        options = [(label, key) for label, key in named_province_choices(game) if key in selected]
        if self.busy or game not in BORDER_GAMES or len(options) < 2:
            return
        self.push_screen(
            BorderPicker(
                options,
                self.province_selection.adjacency,
                map_borders=province_borders(game, tuple(selected)),
            ),
            self.borders_chosen,
        )

    def borders_chosen(self, borders):
        if borders is not None:
            self.province_selection = ProvinceSelection(
                self.province_selection.provinces,
                self.province_selection.joint,
                None if borders is USE_MAP_BORDERS else borders,
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
            game in BORDER_GAMES and state.joint and len(state.provinces or ()) > 1
        )

    def _config(self):
        state = self.province_selection
        if state.joint and state.borders_need_review and len(state.provinces or ()) > 1:
            raise ValueError(
                "Review custom borders after adding provinces, or choose Use map borders."
            )

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
                constraints=self.constraint_options,
                three_kingdoms=self._three_kingdoms_options(game),
                compare_constraints=self.query_one("#compare-constraints", Checkbox).value,
            )
        except ValueError as error:
            raise ValueError("Enter numeric values for the selected settings.") from error

    def _three_kingdoms_options(self, game):
        if game != "three_kingdoms":
            return ThreeKingdomsOptions()
        values = {
            field: self.query_one("#three-kingdoms-" + field, Input).value
            for field in ThreeKingdomsOptions.__dataclass_fields__
            if field
            not in {
                "city_level",
                "capital_commandery",
                "external_resources",
                "include_leader_effects",
            }
        }
        capital = str(self.query_one("#three-kingdoms-capital", Select).value)
        city = str(self.query_one("#three-kingdoms-city_level", Select).value)
        return ThreeKingdomsOptions(
            **{field: int(value) for field, value in values.items()},
            city_level=None if city == "auto" else int(city),
            capital_commandery=None if capital == "none" else capital,
            external_resources=tuple(
                sorted(self.query_one("#three-kingdoms-resources", SelectionList).selected)
            ),
            include_leader_effects=self.query_one("#three-kingdoms-leader-effects", Checkbox).value,
        )

    @on(Select.Changed)
    @on(Input.Changed)
    @on(Checkbox.Changed)
    @on(SelectionList.SelectedChanged, "#three-kingdoms-resources")
    def settings_changed(self):
        if (
            self.is_running
            and self._ui_ready
            and not self._loading_settings
            and not self.busy
            and not isinstance(self.screen, ModalScreen)
        ):
            self._refresh_preview()

    def _refresh_preview(self, *, reset_model=True):
        if reset_model:
            self._reset_model_size("available after compilation")
        self._province_controls()
        count = constraint_count(self.constraint_options)
        constraint_button = self.query_one("#choose-constraints", Button)
        constraint_button.label = (
            f"Optional constraints… ({count})" if count else "Optional constraints…"
        )
        constraint_button.disabled = str(self.query_one("#game", Select).value) not in EXACT
        self.query_one("#compare-constraints", Checkbox).disabled = constraint_button.disabled
        self.query_one("#time-options").display = self.query_one("#time-limit", Checkbox).value
        try:
            config = self._config()
            self.query_one("#world-bonuses", Checkbox).disabled = config.game == "rome2" and set(
                selected_provinces(config)
            ) <= {"coastal", "inland", "grain"}
            jobs, skipped = make_jobs(config)
        except ValueError as error:
            self.query_one("#preview", Static).update(str(error))
            self.query_one("#intro", Static).update("Runtime: choose valid settings.")
            self.query_one("#runtime-expectation", Static).update(str(error))
            self.query_one("#run", Button).disabled = True
        else:
            preview = query_summary(config, jobs, skipped)
            if config.compare_constraints:
                preview += "\nComparison: up to 2 solves per case; limit applies to each solve."
            self.query_one("#preview", Static).update(preview)
            self._show_runtime_outlook(config, jobs)
            self.query_one("#run", Button).disabled = not jobs

    def _show_runtime_outlook(self, config, jobs):
        summary, details = self.runtime.preview(config, jobs)
        intro = self.query_one("#intro", Static)
        intro.update("Runtime: " + summary)
        intro.tooltip = summary + "\nOpen the Runtime tab for evidence and live activity."
        self.query_one("#runtime-expectation", Static).update(details)

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
        self.stop_requested = self.force_stopping = False
        self.query_one("#settings").disabled = busy
        self.query_one("#run", Button).disabled = busy
        cancel = self.query_one("#cancel", Button)
        cancel.disabled = not busy
        cancel.label = "Cancel"
        cancel.tooltip = "Stop the search and retain its best validated layout."
        self.query_one("#spinner").display = busy
        self.query_one("#export", Button).disabled = busy or not self.results
        self.query_one("#clear", Button).disabled = busy or not self.results
        if not busy:
            self._reset_search()
            self._refresh_preview(reset_model=False)

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
                self._reset_model_size("compiling this case…")
                self._reset_search()
                self.runtime.begin(job, perf_counter())
                self._show_runtime_outlook(job, [job])
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
                    result = error_result(job, error).to_dict()
                self.runtime.finish(result, perf_counter())
                self._update_runtime()
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
            if self.results:
                self._show_result(self.results[-1])
            else:
                self._reset_model_size("cancelled · no result retained")
            self.query_one("#run-status", Static).update(
                self.current_case + f" · {format_duration(perf_counter() - started)} elapsed"
            )

    def _tick(self):
        if self.busy and self.started is not None:
            phase = self.current_phase
            if self.stop_requested:
                phase = "Force stopping…" if self.force_stopping else self.runtime.stop_message
            self.query_one("#run-status", Static).update(
                f"{self.current_case}"
                " · "
                f"{phase}"
                " · "
                f"{format_duration(perf_counter() - self.started)} elapsed"
            )
            self._update_runtime()

    def _update_runtime(self):
        now = perf_counter()
        activity = self.query_one("#runtime-activity", Static)
        activity.update(self.runtime.details(now))
        activity.display = self.runtime.job is not None
        if self.busy and self.current_search is not None and self.runtime.searching:
            stats = self.runtime.search.snapshot(now).stats
            if stats is not None:
                self.query_one("#search-progress", Static).update(search_summary(stats))
        self._sync_activity_panels()

    @on(TabbedContent.TabActivated, "#tabs")
    def activity_tab_changed(self):
        if self._ui_ready and self.is_running:
            self._sync_activity_panels()

    def _sync_activity_panels(self):
        # Runtime already contains live values. Avoid duplicate footers consuming
        # its entire scrollable viewport in a small terminal.
        footer = self.query_one("#tabs", TabbedContent).active != "runtime-pane"
        self.query_one("#model-size").display = footer
        self.query_one("#search-progress").display = (
            footer and self.busy and self.current_search is not None
        )

    def _phase_changed(self, phase):
        if not self.is_running or not self.busy:
            return
        self.runtime.observe(phase, perf_counter())
        if isinstance(phase, SearchStats):
            if self.is_running and self.busy:
                self.current_search = phase
                self.query_one("#search-progress", Static).update(search_summary(phase))
                self.query_one("#search-progress").display = True
                self._update_runtime()
            return
        if isinstance(phase, ModelStats):
            self.current_models.append(phase)
            self._show_model_size(self.current_models, "Active · " + self.current_case)
            return
        self.current_phase = phase
        self._reset_search()
        self._tick()

    def _reset_search(self):
        self.current_search = None
        self.query_one("#search-progress").display = False
        self.query_one("#search-progress", Static).update("")

    def _reset_model_size(self, message):
        self.current_models = []
        self.query_one("#model-size", Static).update("Model size: " + message)
        self.query_one("#model-details", Static).update(
            message.capitalize() + "\n\n" + MODEL_SIZE_NOTE
        )

    def _show_model_size(self, models, title, *, selected=False):
        if not selected or not self.busy:
            self.query_one("#model-size", Static).update(model_size_summary(models))
        self.query_one("#model-details", Static).update(model_details(models, title))

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
        if not self.is_running:
            return
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
        self._show_model_size(
            [ModelStats.from_dict(item) for item in result["raw"].get("model_complexity", [])],
            "Selected · " + label,
            selected=True,
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
                        "No usable layout returned; this does not prove infeasibility. "
                        "Run again to search for a layout."
                    ),
                }.get(
                    result["solver"]["status"],
                    "No validated layout was returned. See the log for details.",
                ),
            )
        cancellation = result["raw"].get("cancellation", {})
        if cancellation.get("requested"):
            message += (
                "\nCancellation requested; validated layout retained. See status and gap for proof."
                if result["income"] is not None
                else "\nCancellation requested; no validated layout retained."
            )
        self.query_one("#layout-summary", Static).update(message)
        table = self.query_one("#buildings", DataTable)
        table.clear()
        for building in result["buildings"]:
            table.add_row(building["region"], building["building"], building["id"])
        self.query_one("#constraint-cost-summary", Static).update(comparison_summary(result))
        changes = self.query_one("#constraint-changes", DataTable)
        changes.clear()
        for row in comparison_rows(result):
            changes.add_row(*row)

    @on(Button.Pressed, "#cancel")
    async def cancel_button(self):
        await self.action_cancel()

    async def action_cancel(self):
        if self.busy and self.runner:
            if self.stop_requested:
                self.force_stopping = True
                self._tick()
                await self.runner.stop()
                return
            self.stop_requested = self.runtime.stop_requested = True
            cancel = self.query_one("#cancel", Button)
            cancel.label = "Force stop"
            cancel.tooltip = "Terminate the worker; the active layout may be lost."
            self._tick()
            await self.runner.request_stop()

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
        self._reset_search()
        self._reset_model_size("available after compilation")
        self.query_one("#results", DataTable).clear()
        self.query_one("#buildings", DataTable).clear()
        self.query_one("#constraint-changes", DataTable).clear()
        self.query_one("#constraint-cost-summary", Static).update(COMPARISON_EMPTY)
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
