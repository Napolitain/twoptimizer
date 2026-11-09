"""Optional province and border pickers; single-province controls stay in place."""

from dataclasses import dataclass
from typing import ClassVar

from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from games.tw.maps.catalog import province_borders
from twoptimizer.holdings import BORDER_GAMES, JOINT_GAMES

# None means cancel for a modal result, so automatic borders need a distinct action.
USE_MAP_BORDERS = object()


@dataclass(frozen=True)
class ProvinceSelection:
    provinces: tuple[str, ...] | None = None
    joint: bool = False
    adjacency: tuple[tuple[str, str], ...] | None = None
    borders_need_review: bool = False

    def with_provinces(self, selected: tuple[str, ...], joint: bool):
        borders = self.adjacency
        review = self.borders_need_review
        if not set(selected) <= set(self.provinces or ()):
            review = review or borders is not None
            borders = None
        if borders is not None:
            borders = tuple(pair for pair in borders if set(pair) <= set(selected))
        return ProvinceSelection(selected, joint, borders, review)


class ProvincePicker(ModalScreen):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    ProvincePicker { align: center middle; background: #020814 75%; }
    #province-dialog { width: 80; max-width: 96%; height: 34; max-height: 95%;
        background: #14243a; border: round #68dfcb; padding: 1 2; }
    #province-picker-body { height: 1fr; }
    #province-list { height: 12; min-height: 4; }
    #province-count { height: 1; }
    #joint-note { height: auto; margin: 1 0; }
    .picker-buttons { height: 3; }
    .picker-buttons Button { width: 1fr; min-width: 12; margin-right: 1; }
    """

    def __init__(self, game, options, state: ProvinceSelection, current: str):
        super().__init__()
        self.game, self.options, self.original = game, options, state
        available = {key for _, key in options}
        self.selected = set((current,) if state.provinces is None else state.provinces) & available
        self.visible_keys = [key for _, key in options]

    def compose(self):
        with Vertical(id="province-dialog"):
            with VerticalScroll(id="province-picker-body"):
                yield Static("Choose provinces / holdings")
                yield Input(placeholder="Search provinces…", id="province-search")
                yield Static("", id="province-count")
                yield SelectionList(
                    *[(label, key, key in self.selected) for label, key in self.options],
                    id="province-list",
                )
                yield Checkbox(
                    "Optimize selected provinces together",
                    value=self.original.joint,
                    disabled=self.game not in JOINT_GAMES,
                    id="joint-provinces",
                )
                yield Static("", id="joint-note")
            with Horizontal(classes="picker-buttons"):
                yield Button("All", id="provinces-all")
                yield Button("None", id="provinces-none")
                yield Button("Single province", id="provinces-single")
            with Horizontal(classes="picker-buttons"):
                yield Button("Apply", id="provinces-apply", variant="primary")
                yield Button("Cancel", id="provinces-cancel")

    def on_mount(self):
        self.update_summary()
        self.query_one("#province-search", Input).focus()

    def update_summary(self):
        self.query_one("#province-count", Static).update(
            f"{len(self.selected)} of {len(self.options)} selected"
        )
        together = self.query_one("#joint-provinces", Checkbox).value
        text = "Each province runs independently, for every selected faction and solver."
        if together:
            text = "One joint holding per faction and solver. " + (
                self.border_note()
                if self.game in BORDER_GAMES
                else "Shares food, faction effects and unique-building limits across the holding."
            )
        self.query_one("#joint-note", Static).update(text)

    def border_note(self):
        if self.original.adjacency is not None or self.original.borders_need_review:
            return "Custom borders are retained; adding provinces requires a border review."
        if province_borders(self.game, tuple(self.selected)) is not None:
            return (
                "Uses bundled land borders automatically; Neighboring provinces can override them."
            )
        if self.game == "three_kingdoms":
            return (
                "Map borders are incomplete. At zero base corruption adjacent bonuses are "
                "inactive; nonzero corruption requires explicit neighboring provinces."
            )
        return (
            "Set neighboring provinces before running; map borders are unavailable "
            "for this selection."
        )

    @on(Input.Changed, "#province-search")
    def filter_provinces(self):
        self.rebuild_list()

    def rebuild_list(self):
        query = self.query_one("#province-search", Input).value.casefold().strip()
        visible = [
            (label, key)
            for label, key in self.options
            if query in label.casefold() or query in key.casefold()
        ]
        widget = self.query_one("#province-list", SelectionList)
        with widget.prevent(SelectionList.SelectedChanged):
            widget.clear_options()
            widget.add_options([(label, key, key in self.selected) for label, key in visible])
        self.visible_keys = [key for _, key in visible]
        self.update_summary()

    @on(SelectionList.SelectedChanged, "#province-list")
    def selection_changed(self):
        self.selected.difference_update(self.visible_keys)
        self.selected.update(self.query_one("#province-list", SelectionList).selected)
        self.update_summary()

    @on(Checkbox.Changed, "#joint-provinces")
    def joint_changed(self):
        self.update_summary()

    @on(Button.Pressed, "#provinces-all")
    def select_all(self):
        self.selected = {key for _, key in self.options}
        self.rebuild_list()

    @on(Button.Pressed, "#provinces-none")
    def select_none(self):
        self.selected.clear()
        self.rebuild_list()

    @on(Button.Pressed, "#provinces-single")
    def use_single(self):
        self.dismiss(ProvinceSelection())

    @on(Button.Pressed, "#provinces-apply")
    def apply_selection(self):
        selected = tuple(key for _, key in self.options if key in self.selected)
        self.dismiss(
            self.original.with_provinces(
                selected, self.query_one("#joint-provinces", Checkbox).value
            )
        )

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#provinces-cancel")
    def cancel_button(self):
        self.action_cancel()


class BorderPicker(ModalScreen):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    BorderPicker { align: center middle; background: #020814 75%; }
    #border-dialog { width: 80; max-width: 96%; height: 34; max-height: 95%;
        background: #14243a; border: round #68dfcb; padding: 1 2; }
    #border-picker-body { height: 1fr; }
    #border-list { height: 8; min-height: 3; }
    #border-error { height: auto; color: #ffae9e; }
    .picker-buttons { height: 3; }
    .picker-buttons Button { width: 1fr; min-width: 12; margin-right: 1; }
    """

    def __init__(self, options, borders, *, map_borders=None):
        super().__init__()
        self.options = options
        self.names = {key: label for label, key in options}
        self.map_borders = map_borders
        self.automatic = borders is None and map_borders is not None
        effective = map_borders if self.automatic else borders
        self.borders = {tuple(sorted(pair)) for pair in effective or ()}

    def compose(self):
        with Vertical(id="border-dialog"):
            with VerticalScroll(id="border-picker-body"):
                yield Static("Neighboring provinces in this holding")
                yield Static(
                    "Add each shared border once; provinces are neighbors in both directions. "
                    "Apply stores a custom list; an empty list disables adjacency effects."
                )
                yield Static(
                    "Showing automatic map borders. Sea routes are not included."
                    if self.automatic
                    else "Showing custom borders. Use map borders restores automatic selection."
                    if self.map_borders is not None
                    else "Map borders are unavailable for this selection.",
                    id="border-source",
                )
                yield Select(
                    self.options, value=self.options[0][1], allow_blank=False, id="border-first"
                )
                yield Select(
                    self.options, value=self.options[1][1], allow_blank=False, id="border-second"
                )
                with Horizontal(classes="picker-buttons"):
                    yield Button("Add border", id="border-add")
                    yield Button("Remove marked", id="border-remove")
                yield Static("", id="border-error")
                yield SelectionList(id="border-list")
            with Horizontal(classes="picker-buttons"):
                yield Button("Use map borders", id="borders-map", disabled=self.map_borders is None)
                yield Button("Apply borders", id="borders-apply", variant="primary")
                yield Button("Cancel", id="borders-cancel")

    def on_mount(self):
        self.rebuild_list()

    def rebuild_list(self):
        widget = self.query_one("#border-list", SelectionList)
        widget.clear_options()
        widget.add_options(
            [(f"{self.names[a]} ↔ {self.names[b]}", (a, b)) for a, b in sorted(self.borders)]
        )

    def mark_custom(self):
        self.automatic = False
        self.query_one("#border-source", Static).update(
            "Custom border list. Apply stores these borders for the selected provinces."
        )

    @on(Button.Pressed, "#border-add")
    def add_border(self):
        first = str(self.query_one("#border-first", Select).value)
        second = str(self.query_one("#border-second", Select).value)
        if first == second:
            self.query_one("#border-error", Static).update("Choose two different provinces.")
            return
        self.query_one("#border-error", Static).update("")
        self.borders.add(tuple(sorted((first, second))))
        self.mark_custom()
        self.rebuild_list()

    @on(Button.Pressed, "#border-remove")
    def remove_borders(self):
        self.borders.difference_update(self.query_one("#border-list", SelectionList).selected)
        self.mark_custom()
        self.rebuild_list()

    @on(Button.Pressed, "#borders-apply")
    def apply_borders(self):
        self.dismiss(tuple(sorted(self.borders)))

    @on(Button.Pressed, "#borders-map")
    def use_map_borders(self):
        if self.map_borders is not None:
            self.dismiss(USE_MAP_BORDERS)

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed, "#borders-cancel")
    def cancel_button(self):
        self.action_cancel()
