# Three Kingdoms historical economy optimizer

This model optimizes domestic building income for a **historical vanilla 1.2.0,
190 CE reference**. It runs without installed game files. It is not a model of
the current game: later patches changed population, factions, geography and
buildings. The version is part of the scenario's meaning, not merely a data date.

The numerical reference comes from the public vanilla Assembly Kit export in
[ZadesSC/tt3k_dw9_dave at commit 31020c8](https://github.com/ZadesSC/tt3k_dw9_dave/tree/31020c8a75f8a08f83abe5410680a309d58475f1).
The importers select the original database tables and omit the repository's
`TWaD_` mod tables. Every imported table records its pinned URL, byte count and
SHA-256 digest. Public HTML catalogs remain useful for names and source audits;
their incomplete or newer numerical effects are not mixed into this ruleset.

## Run

```sh
uv run --locked twoptimizer three-kingdoms \
  --faction 3k_main_faction_cao_cao \
  --commandery 3k_main_province_yingchuan

uv run --locked twoptimizer three-kingdoms \
  --faction 3k_main_faction_cao_cao \
  --commandery all --joint --seconds 60

uv run --locked twoptimizer three-kingdoms \
  --commandery 3k_main_province_yingchuan \
  --algorithm cp-sat --algorithm highs --seconds 30
```

Omit `--seconds` to let the selected solver run until it proves optimality or
infeasibility. The default solver is CP-SAT; HiGHS is supplied through OR-Tools.
The no-argument `uv run --locked twoptimizer` command opens the shared terminal UI.
Choose Three Kingdoms, then select one or several commanderies and independent
or joint mode. The UI exposes the same snapshot inputs as the CLI.

The default is a controlled snapshot: optimized city levels, one million people per
commandery, zero base corruption, normal taxes, no researched reforms, no
external food or resources, and a nonnegative public-order change requirement.
These are inputs for comparing layouts, not reconstructed 190 CE starting states.
Use `--city-level`, `--population`, `--corruption`, `--public-order-offset`,
`--minimum-public-order`, `--external-food` and `--reforms none|all` to change them.
`--city-level auto` lets each commandery choose a level from 1 to 10 independently.
The solver balances the extra building slots and income against food consumption;
it can leave a city smaller when upgrading would hurt the economy. Population
stays fixed and must fit the chosen city and resource settlements. `--city-level 5`
reproduces the original fixed-level comparison. The TUI offers the same automatic
and fixed choices.
External resources supplied with repeated `--resource` arguments are explicit
availability assumptions, such as resources obtained through trade.
The original faction leader's imported economic traits are enabled by default;
`--no-leader-effects` gives a comparison without those fixed leader effects.

## What the optimization means

The holding includes all counties in each selected commandery. The reference
contains **70 commanderies and 187 counties**, including 117 resource settlements.
The solver chooses city levels, resource-settlement levels and district chains.
An explicit fixed city level removes that city's level decision. It uses the
selected city's unlocked capacity, resource-settlement and port
templates, faction availability, reform requirements and resource prerequisites.
Faction-unique and capital-only restrictions remain constraints. A harbour uses
one of the unlocked city slots; its separate port template does not grant a free
additional district. Contemporary player observations corroborate this placement
rule ([2019 economy guide](https://www.reddit.com/r/totalwar/comments/bwepxi),
[2019 construction guide](https://gl.ali213.net/html/2019-7/346915.html)).

Income categories retain their own base values and percentage modifiers. Local
county, commandery and faction effects are routed to their declared recipients.
The objective is domestic income after modeled corruption and recurring building
upkeep. Construction cost and construction time are outside this static snapshot;
it does not optimize a sequence of upgrades or repay initial investments.

Food is shared across the selected joint holding, with the supplied external
food added once. Farming and fishing multipliers affect their respective
production categories; they do not multiply food sold at markets or city
distribution costs. Public-order effects and population penalties are checked
per commandery. Independent mode solves each commandery separately, so it cannot
benefit from another selected commandery's food, resources or faction effects.
An independent case can therefore be infeasible even when the same commandery is
viable in a joint holding. The original fixed level-5 Chang'an comparison was
infeasible without external food. Automatic city sizing instead selects level 4,
keeps the supplied million inhabitants, and produces 810.25 income with a food
surplus of 1. Both solvers prove that result. To keep level 5, supplying
`--city-level 5 --external-food 6` also makes the isolated case feasible.
Other incompatible inputs, such as excessive population or required buildings,
can still make automatic sizing infeasible.

The historical population rules have 21 exact integer bands, using thousands of
people internally. The supplied number of people is divided by 1,000 with any
remainder discarded before lookup. Population refers to the owned commandery,
including its resource counties. At one million people, the source supplies
65% extra peasantry income and a public-order change of -2. At three million,
the corresponding values are 150% and -14. Population stays fixed during a solve;
growth, migration, recruitment and later population-rule changes are excluded.

Base corruption is a supplied percentage. Anti-corruption modifiers scale that
base; they are not percentage-point deductions from income. For example, a
20% reduction of 50% base corruption leaves 40% corruption. The model retains
exact fractional arithmetic. Display rounding and the game's internal rounding
order still require installed-game validation. Raw difficulty/territory-count
corruption reference points are retained in `data/rules.json`, but their
interpolation is not guessed to replace the explicit input.

## Adjacency and coverage limits

The historical public database provides 55 additional adjacency links, not a
complete campaign-border graph. They are retained for audit and are not treated
as the complete map. A modern DLC07 topology was inspected but contains changed
regions and omits historical counties, so it cannot silently substitute for the
historical graph.

Zero-base-corruption scenarios can run without borders because the modeled
adjacent economic modifiers only reduce corruption and therefore have no effect
there. A scenario where these bonuses matter requires an explicit border graph
via the shared border controls. An explicitly empty graph is a declared scenario
assumption, not a claim that the game's commanderies have no neighbours.

The initial model does not simulate character changes and assignments, diplomacy and
trade-agreement income, dynamic faction currencies, military upkeep, population
changes or campaign events. Its baseline fertility is normal outside harvest;
the source's six fertility/harvest bundles are retained for explicit scenario
support. A full campaign economy cannot be inferred from a building-income
ranking. Source data coverage and solver optimality are separate questions:
`OPTIMAL` proves the best layout for the implemented snapshot and its inputs.

## Rebuild the references

```sh
uv run --locked python -m games.tw.three_kingdoms.import_reference
uv run --locked python -m games.tw.three_kingdoms.import_geography
uv run --locked python -m games.tw.three_kingdoms.import_rules
```

Each importer supports `--cache` and `--offline`. An offline replay requires the
previously fetched pinned XML files in the selected cache. These commands do not
execute source scripts. Normal optimizer runs read the bundled JSON and do not
fetch internet data.

When installed exports become available, the next validation step is to compare
building panels and complete commandery income/food/public-order breakdowns, then
build a separate current-version profile. The current-version profile needs
effective base and patch tables, DLC selection, full campaign borders, scripted
fertility assignment and population rules. Keeping it separate preserves the
meaning and reproducibility of existing historical results.
