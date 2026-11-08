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
project defaults to Python 3.14.

Choose a game, faction and province in the terminal UI, then press **Ctrl+R** to
run. Use **Esc** to cancel, **Ctrl+S** to export, **F1** for help and **Ctrl+Q** to
quit. CPU selection is automatic. Solves run until optimality or infeasibility is
proved; enable **Use a time limit** for a bounded run.
Use **Multiple provinces…** for a searchable checklist with All/None controls.
Independent batches work in all three games; joint holdings are available for
Attila and Shogun 2, with explicit neighboring-province inputs for Attila.

![Interactive terminal UI](docs/tui.png)

## Command line

Run from the repository directory:

```sh
uv run --locked twoptimizer rome2 --faction rom_rome --layout coastal --seconds 15
uv run --locked twoptimizer shogun2 --clan oda --soil native --seconds 15
uv run --locked twoptimizer attila --province Thracia --fertility 5 --seconds 15
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
- [Data preparation and coverage](games/tw/multigame/README.md)
- [Agent and development guidelines](AGENTS.md)
