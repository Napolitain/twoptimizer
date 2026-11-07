# Additional Total War game data

The public reference catalogs and installed-export ingestion path cover
Shogun 2, Rome II and Three Kingdoms. A [Shogun 2 domestic-tax optimizer](../shogun2/README.md)
now runs from public references with explicit scenario inputs. Rome II and
Three Kingdoms still await game-specific models and validation.

| Catalog | Buildings | Faction entries | Additional facts |
| --- | ---: | ---: | --- |
| Shogun 2 | 115 | 12 playable clans | 45 arts; 65 province soil/port/specialty records |
| Rome II | 813 | 207 Grand Campaign entries | Shared culture and political-party effect text |
| Three Kingdoms | 583 | 659 reference entries | Construction costs/turns, listed upkeep and food-cost metadata |

Faction entries include NPCs, separatists and different start dates where the
source lists them. They are not counts of playable civilizations. Identical
public rosters share a `roster_id`; every faction identity remains separate.

## Sources and current limitations

Shogun 2 facts come from the [mirrored official encyclopedia](https://liquidwork.github.io/shogun2-encyclopedia/buildings.html).
Rome II and Three Kingdoms facts come from
[Honga](https://www.honga.net/totalwar/rome2/faction.php?l=en).
Every response has a URL, byte count and SHA-256 hash. No source JavaScript is
executed. Only factual fields, names, IDs and effect statements are retained.
These references do not identify an installed patch version.

The checked-in [coverage audit](data/coverage.json) records integrity checks and
specific blockers. Some Three Kingdoms slot values and Rome II conditional
effects contain `%n` placeholders. Those strings remain unresolved. A missing
upkeep column remains `null`; explicit maintenance effects stay in the facts.
Three Kingdoms' source `food_cost` column is retained separately from recurring
food-production/consumption effects, so a later model can avoid double counting.

Public page visibility is not proof of in-game building eligibility. In
particular, Three Kingdoms lists settlement traditions under factions that
cannot necessarily build them. The original Shogun 2 province mirror supplies
only names; a [second index](https://shogun2-encyclopedia.com/regions.html)
now supplies soil, ports and specialty locations. Numeric farm bonuses and
economy rules have separate source references. Starting town wealth remains an
explicit scenario input, rather than a guessed historical state.

All three catalogs retain `ready_for_full_economy_model: false`: none is a full
campaign simulation verified against installed data. The Shogun 2 model publishes
[controlled clan comparisons](../../../reports/shogun2-income-comparison.csv),
including assumptions and three-solver optimality checks. Those results establish
an optimum for domestic tax income in the declared scenario, rather than an
unconditional strongest-campaign ranking.

## Refresh or replay the public catalogs

```sh
.venv/bin/python -m games.tw.multigame.import_catalogues
.venv/bin/python -m games.tw.multigame.import_catalogues --offline
.venv/bin/python -m games.tw.multigame.audit_catalogues
```

Responses are cached under `.cache/multigame/`. `--games shogun2 rome2` selects
games. `--workers 1` reduces concurrent requests; the maximum is three.
Transient server errors receive bounded retries respecting short `Retry-After`
values. `--native-only` is an optional smaller discovery set, not an exhaustive
playability classifier. Use a new `--cache` directory for a fresh snapshot.
Unexpected table shapes and conflicting numeric records are reported rather
than filled with invented values.

## When installed data is available

Include the installed game/build version and enabled DLC/mod list. For modded
games, include the relevant base and patch data as well as the mod tables and
their load order. A mod-only export does not describe the effective game.

[RPFM's database editor](https://frodo45127.github.io/rpfm/manual/editors/db.html)
can export database tables as TSV. A full DB export is acceptable; the importer
keeps unrecognized tables for later schema resolution. The economy work needs:

- Building levels, chains, upgrades, culture/faction availability and prerequisites.
- Building effects, effect definitions, scopes and bonus-value mappings.
- Faction/culture/leader effects, effect bundles, technologies, arts and reforms.
- Region/province/commandery/county definitions, resource locations and slot templates.
- Campaign starting conditions, settlement capacities, population, fertility,
  food, taxation and growth rules. Some of these also need campaign/startpos data.
- Localization tables where possible, to connect stable IDs to displayed names.

The ingestion command accepts exported TSVs. Binary `.pack` archives need a
game-aware export step first; they are never treated as text files.

```sh
.venv/bin/python -m games.tw.multigame.import_exports \
  --game rome2 --input /path/to/exported-tables \
  --output installed-game-data/rome2 --version YOUR_BUILD --vanilla
```

Use `--game shogun2` or `--game three_kingdoms` for the other games. For mods,
replace `--vanilla` with repeated `--mod NAME` arguments in declared load order.
Omitting both leaves mod status unknown.

The bundle contains a manifest with source hashes, encodings, metadata, named
columns when present, table/chunk/row counts and missing minimal core tables.
Every chunk becomes a JSONL file of original string values. Base/patch duplicate
keys remain separate; load order is never guessed. UTF-8 BOM and UTF-16 exports
are supported. Headerless tables retain all rows without invented column names.
Malformed rows fail before a new manifest is published. Generated installed-data
bundles are git-ignored.

The presence of the minimal core tables does not certify completeness. The
following validation will resolve schemas, foreign keys, campaign filters,
faction restrictions, numeric placeholders and game-specific mechanics, then
compare independently evaluated layouts and in-game economy panels before
running the faction comparisons.

Shogun 2 already enforces shared food and reports growth components. Extending
the static model to future income requires validated town-wealth dynamics over
an explicit horizon. Rome II requires its own settlement/food/culture/slavery rules.
Three Kingdoms requires commandery/county scopes, population, city capacity,
category income, upkeep and reform/faction modifiers. Attila's constraints will
not be copied into these games as a substitute for those mechanics.
