"""Keyboard and mouse inspection of bundled, unresolved HoI4 reference facts."""

from typing import ClassVar

from textual import on
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Select, Static, TabbedContent, TabPane

from twoptimizer.errors import ApplicationError
from twoptimizer.hoi4_data import (
    COUNTRIES,
    country_summary,
    inspect_reference,
    source_summary,
    state_row,
    state_source,
)


class HoI4DataScreen(ModalScreen):
    BINDINGS: ClassVar = [("escape", "close", "Close")]
    DEFAULT_CSS = """
    HoI4DataScreen { align: center middle; background: #020814 75%; }
    #hoi4-dialog { width: 100; max-width: 96%; height: 40; max-height: 95%;
        background: #14243a; border: round #68dfcb; padding: 1 2; }
    #hoi4-heading, #hoi4-provisional, #hoi4-country-summary, #hoi4-state-source {
        height: auto; margin-bottom: 1; }
    #hoi4-provisional { color: #f6d484; }
    #hoi4-country { width: 100%; }
    #hoi4-tabs { height: 1fr; }
    #hoi4-states { height: 1fr; min-height: 4; }
    #hoi4-coverage { height: auto; }
    #hoi4-close { width: 100%; }
    """

    def __init__(self):
        super().__init__()
        self.profile: dict = {}
        self._ready = False

    def compose(self):
        with Vertical(id="hoi4-dialog"):
            yield Static("Hearts of Iron IV · public reference inspector", id="hoi4-heading")
            yield Static(
                "PROVISIONAL · Source patch unverified · No validated gameplay scenario",
                id="hoi4-provisional",
            )
            yield Select(
                [(f"{name} ({tag})", tag) for tag, name in COUNTRIES.items()],
                value="FRA",
                allow_blank=False,
                id="hoi4-country",
            )
            yield Static("", id="hoi4-country-summary", markup=False)
            with TabbedContent(id="hoi4-tabs"):
                with TabPane("Literal state declarations", id="hoi4-state-tab"):
                    yield DataTable(id="hoi4-states", cursor_type="row")
                    yield Static("", id="hoi4-state-source", markup=False)
                with TabPane("Sources / coverage", id="hoi4-source-tab"), VerticalScroll():
                    yield Static("", id="hoi4-coverage", markup=False)
            yield Button("Close", id="hoi4-close", variant="primary")

    def on_mount(self):
        self.query_one("#hoi4-states", DataTable).add_columns(
            "State", "Name key", "Category", "CIV", "MIL", "Dock", "Infra"
        )
        self._ready = True
        self.load_country()
        self.query_one("#hoi4-country", Select).focus()

    @on(Select.Changed, "#hoi4-country")
    def country_changed(self):
        if self._ready:
            self.load_country()

    def load_country(self):
        table = self.query_one("#hoi4-states", DataTable)
        table.clear()
        self.profile = {}
        self.query_one("#hoi4-state-source", Static).update("")
        try:
            report = inspect_reference(str(self.query_one("#hoi4-country", Select).value))
        except ApplicationError as error:
            self.query_one("#hoi4-country-summary", Static).update(str(error))
            self.query_one("#hoi4-coverage", Static).update("Reference data unavailable.")
            return
        self.profile = report["countries"][0]
        self.query_one("#hoi4-country-summary", Static).update(country_summary(self.profile))
        self.query_one("#hoi4-coverage", Static).update(source_summary(report))
        for state in self.profile["states"]:
            table.add_row(*state_row(state), key=str(state["id"]))
        self.show_state()

    @on(DataTable.RowHighlighted, "#hoi4-states")
    def state_highlighted(self):
        self.show_state()

    def show_state(self):
        row = self.query_one("#hoi4-states", DataTable).cursor_row
        states = self.profile.get("states", [])
        if row < len(states):
            self.query_one("#hoi4-state-source", Static).update(state_source(states[row]))

    def action_close(self):
        self.dismiss()

    @on(Button.Pressed, "#hoi4-close")
    def close_button(self):
        self.action_close()
