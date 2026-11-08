"""Self-contained help and export dialogs."""

from datetime import datetime
from typing import ClassVar

from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Markdown, Static

from twoptimizer.export import export_session


class HelpScreen(ModalScreen):
    BINDINGS: ClassVar = [("escape", "close", "Close")]

    def compose(self):
        with Vertical(id="dialog"):
            with VerticalScroll():
                yield Markdown("""# Using twoptimizer

Choose a game, faction, province and solver on the left. **All factions** compares
the same holding. **CP-SAT** is the default; **HiGHS** is the alternative mixed-integer
solver. **Compare exact solvers** runs both supported solvers.

For **Hearts of Iron IV**, use **Inspect HoI4 data…** to browse eight countries,
literal state declarations and source diagnostics. Missing declarations show **—**;
they are not assumed to be zero. The public source patch and gameplay scenarios
remain unverified, so optimization stays unavailable. **Esc** closes the inspector.

**Multiple provinces** opens a searchable checklist with All and None controls.
Provinces run independently by default. All three games can optimize them together;
joint Attila and Rome II runs use bundled land borders when a complete map is available.
**Neighboring provinces** lets you inspect or override them; **Use map borders**
restores automatic selection. Applying an empty custom list disables adjacency effects.
**All** selects every named province; hypothetical reference layouts stay in the
single-province dropdown. Joint runs share supported faction effects and constraints.
Use **Single province** in the picker to return to the original dropdown.

**Optional constraints…** lets you search buildings by name or ID, then Require
at least one or Forbid all copies of that exact building. Requirements apply once
across a joint holding, or separately in every independent case. Existing placement,
research and known unique-building limits still apply. **Clear all** restores defaults.
Attila can require minimum state-religion influence in each province; these are
effect points, not population percentages. Shogun 2 offers state religion and
Nanban contact; Ikko requires Ikko Ikki. Rome II temples can be required by ID,
but religious conversion is not modeled. Income remains the objective.

**Compare income without requirements** adds a baseline run that removes only
optional required/forbidden buildings and the influence minimum. Faith, Nanban
contact, advanced campaign rules, world settings and available choices stay fixed.
Select a result and open **Constraint cost** for the income loss and changed
buildings. Exact loss requires both optima to be proved; unfinished results show
bounds and label current-layout differences separately. Comparison can perform
two solves per case, each with the configured time limit. With no active building
or influence requirements, it performs no extra solve.

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

The query preview counts provinces, factions, solver choices and cases before Run.
**Model size** shows variables, constraints and available details as models compile;
some native solver counts arrive after search. Reference and solver formulations
are labeled separately. Select a completed result to inspect its saved counts.
Counts describe models before presolve; they do not predict runtime.

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
