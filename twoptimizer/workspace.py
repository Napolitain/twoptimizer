"""Workspace widget composition, separate from application event handling."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
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
    SelectionList,
    Static,
    TabbedContent,
    TabPane,
)

from twoptimizer.catalog import GAMES
from twoptimizer.comparison_presentation import COMPARISON_EMPTY
from twoptimizer.three_kingdoms_options import ThreeKingdomsOptions


def compose_workspace() -> ComposeResult:
    yield Header()
    with Horizontal(id="workspace"):
        with Vertical(id="left"):
            with VerticalScroll(id="settings"):
                yield Label("SCENARIO", classes="section-title")
                yield Label("Game", classes="field-label")
                yield Select(GAMES, value="rome2", allow_blank=False, id="game")
                yield Button("Inspect HoI4 data…", id="hoi4-data")
                yield Label("Faction / clan", classes="field-label")
                yield Select([("Loading…", "loading")], allow_blank=False, id="faction")
                yield Label("Province / holding", classes="field-label")
                yield Select([("Loading…", "loading")], allow_blank=False, id="province")
                yield Static("", id="province-summary")
                yield Button("Multiple provinces…", id="choose-provinces")
                yield Button("Neighboring provinces…", id="choose-borders")
                yield Button("Optional constraints…", id="choose-constraints")
                yield Checkbox(
                    "Compare income without requirements", value=False, id="compare-constraints"
                )
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
                yield from three_kingdoms_controls()
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
                with (
                    TabPane("Runtime", id="runtime-pane"),
                    VerticalScroll(id="runtime-scroll"),
                ):
                    yield Static("No active case.", id="runtime-activity", markup=False)
                    yield Static("Completion time unknown.", id="runtime-expectation", markup=False)
                with TabPane("Buildings", id="buildings-pane"):
                    yield Static(
                        "Select a result to inspect its layout.",
                        id="layout-summary",
                        markup=False,
                    )
                    yield DataTable(id="buildings", cursor_type="row", zebra_stripes=True)
                with TabPane("Constraint cost", id="constraint-cost-pane"):
                    yield Static(COMPARISON_EMPTY, id="constraint-cost-summary", markup=False)
                    yield Static(
                        "Changes in the layout with requirements compared with the baseline:",
                        id="constraint-changes-note",
                        markup=False,
                    )
                    yield DataTable(id="constraint-changes", cursor_type="row", zebra_stripes=True)
                with (
                    TabPane("Model size", id="complexity-pane"),
                    VerticalScroll(id="complexity-scroll"),
                ):
                    yield Static(
                        "Run a case to compile its model counts.\n\n"
                        "Model size does not predict runtime or guarantee a quick proof.",
                        id="model-details",
                        markup=False,
                    )
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
            yield Static("Model size: available after compilation", id="model-size", markup=False)
            yield Static("", id="search-progress", markup=False)
            yield ProgressBar(total=1, show_eta=False, show_percentage=False, id="progress")
            with Horizontal(id="table-actions"):
                yield Button("Export JSON + CSV", id="export", disabled=True)
                yield Button("Clear results", id="clear", disabled=True)
    yield Footer()


def three_kingdoms_controls() -> ComposeResult:
    defaults = ThreeKingdomsOptions()
    with Vertical(classes="option-group", id="three-kingdoms-options"):
        yield Static("Historical 1.2.0 · common snapshot inputs")
        for label, field in (
            ("City level", "city_level"),
            ("Population (people)", "population"),
            ("Base corruption (%)", "corruption_percent"),
            ("Public order offset", "order_offset"),
            ("Minimum public order", "minimum_order"),
            ("External food per holding", "external_food"),
        ):
            yield Label(label, classes="field-label")
            yield Input(str(getattr(defaults, field)), id="three-kingdoms-" + field, type="number")
        yield Label("Faction capital", classes="field-label")
        yield Select(
            [("Not specified · capital-only buildings excluded", "none")],
            value="none",
            allow_blank=False,
            id="three-kingdoms-capital",
        )
        yield Label("External resources (trade / snapshot)", classes="field-label")
        yield SelectionList(id="three-kingdoms-resources")
        yield Checkbox("Original leader effects", value=True, id="three-kingdoms-leader-effects")
