# twoptimizer

Find income-maximizing building layouts for **Total War: Attila, Rome II and
Shogun 2**. Compare factions and solvers, inspect results, and export JSON or CSV
from an interactive terminal UI or the command line. Bundled reference data lets
you run without a game installation.

## Quick start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```sh
git clone https://github.com/Napolitain/twoptimizer.git
cd twoptimizer
uv run --locked twoptimizer
```

`uv` automatically sets up Python and installs the locked dependencies. The
project requires Python 3.14 or newer; development and CI target Python 3.14.
CP-SAT is the default solver; HiGHS is the alternative in all three games.
Both backends come with the locked OR-Tools dependency.

Choose a game, faction and province in the terminal UI, then press **Ctrl+R** to
run. Use **Esc** to cancel, **Ctrl+S** to export, **F1** for help and **Ctrl+Q** to
quit. CPU selection is automatic. Solves run until optimality or infeasibility is
proved; enable **Use a time limit** for a bounded run.
Use **Multiple provinces…** for a searchable checklist with All/None controls.
Independent batches and joint holdings work in all three games. Joint Attila and
Rome II runs use bundled campaign borders automatically; **Neighboring provinces…**
lets you override them. **All** selects actual provinces; the joint mode shares
the game's applicable bonuses and constraints.
Use **Optional constraints…** to require or forbid specific buildings, set an
Attila religious-influence minimum, or choose Shogun 2 religion and Nanban contact.
These options retain the income objective and the game's modeled availability rules.
Enable **Compare income without requirements** to measure their income cost and
inspect changed buildings in the **Constraint cost** tab. Exact loss is reported
when both optima are proved; unfinished solves show bounds instead.
The query preview shows batch scope before Run. **Model size** displays compiled
variable and constraint counts, with separate reference and solver formulations.

For HoI4, select **Inspect HoI4 data…** to browse the public country and state
reference with mouse or keyboard. The inspector shows source coverage and gaps;
the new hourly campaign optimizer is still being built.

![Interactive terminal UI](docs/tui.png)

## Command line

Run from the repository directory:

```sh
uv run --locked twoptimizer rome2 --faction rom_rome --layout coastal --seconds 15
uv run --locked twoptimizer shogun2 --clan oda --soil native --seconds 15
uv run --locked twoptimizer attila --province Thracia --fertility 5 --seconds 15
uv run --locked twoptimizer hoi4 data --country FRA
uv run --locked twoptimizer hoi4 data --country all --json --output hoi4-data.json
```

`--seconds` sets an optional per-case time limit; omit it to run to completion.
Add `--help` to any subcommand for its options, or run
`uv run --locked twoptimizer --help` to list commands. Comparison reports go under
`benchmark-results/` by default; use `attila --output results.json` to save an
Attila run.

## Details

Results optimize the stated static economic models and supplied inputs; they are
not complete campaign simulations. Three Kingdoms and HoI4 are not yet supported
for optimization in the UI.

- [Usage, scenarios, exports and model assumptions](docs/usage.md)
- [Rome II model](games/tw/rome2/README.md)
- [Shogun 2 model](games/tw/shogun2/README.md)
- [HoI4 development status, public data and hourly planning](games/hoi4/README.md)
- [Data preparation and coverage](games/tw/multigame/README.md)
- [CP-SAT and HiGHS comparison](docs/cpsat-highs-performance.md)
- [Historical joint and independent holding benchmarks](docs/holding-performance.md)
- [Attila special-building audit](docs/attila-special-audit.md)
- [Rome II special-building audit](docs/rome-special-audit.md)
- [Agent and development guidelines](AGENTS.md)
