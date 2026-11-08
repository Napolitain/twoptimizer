"""Optional building and religion requirements, edited without changing defaults."""

from math import isfinite
from typing import ClassVar

from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from twoptimizer.constraint_options import ConstraintOptions


def constraint_count(options: ConstraintOptions) -> int:
    return (
        len(options.required_buildings)
        + len(options.forbidden_buildings)
        + (options.minimum_religious_influence is not None)
        + (options.shogun_religion is not None)
        + options.nanban_contact
    )


class ConstraintPicker(ModalScreen):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    ConstraintPicker { align: center middle; background: #020814 75%; }
    #constraint-dialog { width: 88; max-width: 96%; height: 38; max-height: 95%;
        background: #14243a; border: round #68dfcb; padding: 1 2; }
    #constraint-body { height: 1fr; }
    #constraint-list { height: 7; min-height: 3; }
    #constraint-error { height: auto; color: #ffae9e; }
    #constraint-religion-note { height: auto; margin-bottom: 1; }
    .constraint-buttons { height: 3; }
    .constraint-buttons Button { width: 1fr; min-width: 12; margin-right: 1; }
    """

    def __init__(self, game, buildings, options: ConstraintOptions, *, joint=False):
        super().__init__()
        self.game, self.buildings, self.original, self.joint = game, buildings, options, joint
        self.names = {key: label for label, key in buildings}
        self.required = set(options.required_buildings)
        self.forbidden = set(options.forbidden_buildings)

    def compose(self):
        with Vertical(id="constraint-dialog"):
            with VerticalScroll(id="constraint-body"):
                yield Static("Optional constraints")
                yield Static(
                    "Require means at least one across the joint holding."
                    if self.joint
                    else "Requirements apply separately to each province / solver case."
                )
                yield Static(
                    "Forbid means none. Catalog choices still need to satisfy placement, faction, "
                    "faith, research and uniqueness rules."
                )
                yield Input(placeholder="Search buildings by name or ID…", id="constraint-search")
                yield Select(self.buildings, prompt="Choose a building", id="constraint-building")
                with Horizontal(classes="constraint-buttons"):
                    yield Button("Require", id="constraint-require")
                    yield Button("Forbid", id="constraint-forbid")
                    yield Button("Remove marked", id="constraint-remove")
                yield SelectionList(id="constraint-list")
                yield from self.religion_controls()
                yield Static("", id="constraint-error")
            with Horizontal(classes="constraint-buttons"):
                yield Button("Clear all", id="constraints-clear")
                yield Button("Apply", id="constraints-apply", variant="primary")
                yield Button("Cancel", id="constraints-cancel")

    def religion_controls(self):
        if self.game == "attila":
            yield Static("Minimum state-religion influence in each province")
            minimum = self.original.minimum_religious_influence
            yield Input(
                "" if minimum is None else str(minimum),
                placeholder="Optional influence points",
                type="number",
                id="constraint-influence",
            )
            yield Static(
                "Uses the religion selected in the main settings. Influence points are not "
                "population percentages. Leave blank for no minimum.",
                id="constraint-religion-note",
            )
        elif self.game == "shogun2":
            yield Static("State religion")
            yield Select(
                [
                    ("Clan default", "default"),
                    ("Buddhist", "buddhist"),
                    ("Christian", "christian"),
                    ("Ikko", "ikko"),
                ],
                value=self.original.shogun_religion or "default",
                allow_blank=False,
                id="constraint-faith",
            )
            yield Checkbox(
                "Nanban contact established",
                value=self.original.nanban_contact,
                id="constraint-nanban",
            )
            yield Static(
                "Religion selects available building chains; Ikko requires the Ikko Ikki clan. "
                "Population conversion is not simulated.",
                id="constraint-religion-note",
            )

    def on_mount(self):
        self.rebuild_list()
        self.query_one("#constraint-search", Input).focus()

    @on(Input.Changed, "#constraint-search")
    def search_buildings(self):
        query = self.query_one("#constraint-search", Input).value.casefold().strip()
        visible = [
            (label, key)
            for label, key in self.buildings
            if query in label.casefold() or query in key.casefold()
        ]
        widget = self.query_one("#constraint-building", Select)
        previous = widget.value
        widget.set_options(visible)
        if previous in {key for _, key in visible}:
            widget.value = previous

    def rebuild_list(self):
        widget = self.query_one("#constraint-list", SelectionList)
        widget.clear_options()
        widget.add_options(
            [
                (f"{kind}: {self.names.get(key, key)}", (kind, key))
                for kind, selected in (("Require", self.required), ("Forbid", self.forbidden))
                for key in sorted(selected)
            ]
        )

    def add_building(self, *, require):
        value = self.query_one("#constraint-building", Select).value
        error = self.query_one("#constraint-error", Static)
        if value is Select.BLANK:
            error.update("Choose a building first.")
            return
        key = str(value)
        selected, opposite = (
            (self.required, self.forbidden)
            if require
            else (
                self.forbidden,
                self.required,
            )
        )
        if key in opposite:
            error.update(
                "Remove the existing rule before changing Require to Forbid or vice versa."
            )
            return
        selected.add(key)
        error.update("")
        self.rebuild_list()

    @on(Button.Pressed, "#constraint-require")
    def require_building(self):
        self.add_building(require=True)

    @on(Button.Pressed, "#constraint-forbid")
    def forbid_building(self):
        self.add_building(require=False)

    @on(Button.Pressed, "#constraint-remove")
    def remove_buildings(self):
        for kind, key in self.query_one("#constraint-list", SelectionList).selected:
            (self.required if kind == "Require" else self.forbidden).discard(key)
        self.query_one("#constraint-error", Static).update("")
        self.rebuild_list()

    @on(Button.Pressed, "#constraints-clear")
    def clear_constraints(self):
        self.required.clear()
        self.forbidden.clear()
        if self.game == "attila":
            self.query_one("#constraint-influence", Input).value = ""
        elif self.game == "shogun2":
            self.query_one("#constraint-faith", Select).value = "default"
            self.query_one("#constraint-nanban", Checkbox).value = False
        self.query_one("#constraint-error", Static).update("")
        self.rebuild_list()

    def options(self):
        minimum, faith, contact = None, None, False
        if self.game == "attila":
            value = self.query_one("#constraint-influence", Input).value.strip()
            if value:
                minimum = float(value)
                if not isfinite(minimum) or minimum < 0:
                    raise ValueError("Minimum influence must be finite and nonnegative.")
        elif self.game == "shogun2":
            selected = str(self.query_one("#constraint-faith", Select).value)
            faith = None if selected == "default" else selected
            contact = self.query_one("#constraint-nanban", Checkbox).value
        return ConstraintOptions(
            required_buildings=tuple(sorted(self.required)),
            forbidden_buildings=tuple(sorted(self.forbidden)),
            minimum_religious_influence=minimum,
            shogun_religion=faith,
            nanban_contact=contact,
        )

    @on(Button.Pressed, "#constraints-apply")
    def apply_constraints(self):
        try:
            options = self.options()
        except ValueError as error:
            self.query_one("#constraint-error", Static).update(str(error))
            return
        self.dismiss(options)

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#constraints-cancel")
    def cancel_button(self):
        self.action_cancel()
