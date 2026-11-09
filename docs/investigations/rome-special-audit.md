# Rome II special-building evidence

The 2026-11-08 public audit covers **all 35 excluded level-five buildings**:
30 official encyclopedia pages and 35 Honga detail pages, all retrieved and
parsed successfully. It records resource requirements for 34 buildings,
faction-specific predecessors from the official trees, technology links where
displayed, and the displayed effects with their source response hashes.

**No additional building is enabled by this audit.** Public pages still do not
establish each building's event condition, uniqueness limits, first-builder
reward, or complete regional eligibility. These omissions can change the
optimum when provinces are solved together.

The machine-readable [coverage artifact](../../games/tw/rome2/data/special_buildings_coverage.json)
contains every building ID, supported Grand Campaign faction, exact page URL,
SHA-256, prerequisite observation, numeric comparison and unresolved rule.
Its `public_details` entries retain evidence separately by source; an empty
requirement list means the page did not display requirements.

## What the pages establish

The following table summarizes the retrieved requirement observations. A dash
means **not displayed**, not “no requirement.” Resource access is not a claim
that the resource must be produced in the building's own region. The catalog's
faction roster remains the authority for which faction variant is being audited.

| Building | Displayed resource | Displayed technology |
| --- | --- | --- |
| Circus Maximus | Marble | — |
| Colosseum | Marble | — |
| Cloaca Maxima | Lead | — |
| Pantheon | Marble | — |
| Monument of Leonidas | Iron | — |
| Prytaneion | Marble | — |
| Great Market | Wine | — |
| Library of Pergamon | Glassware | — |
| Great Library | Glassware | — |
| Theatre of Syracuse | Marble | Golden Age |
| Rose Marl Building | Silk | — |
| Acropolis | Marble | — |
| Sanctuary of Demeter | Marble | — |
| Temple of Golden Fleece | Marble | — |
| Oracle of Dodona | Marble | — |
| Hieron ton Mehalon Theon (Macedon) | Marble | — |
| Cult of Ephesus | Marble | — |
| Great Altar of Pergamon | Marble | — |
| Hieron ton Mehalon Theon (Pontus) | Marble | — |
| Paradise of Daphne | Timber | — |
| Altar to Zeus | Marble | Golden Age |
| Ptolemaic Temple Complex | Marble | — |
| Tophet | Lead | — |
| High King's Hold | Timber | Murus Dacius for Getae |
| Nemeton (Iceni) | Timber | — |
| Nemeton (Arverni, Boii, Nervii) | Timber | — |
| Oak of Teiwaz | Timber | — |
| Sacrificial Grove | Timber | — |
| Kurgan Field | Timber | — |
| Hearth Altar of the Cabeiri | Timber | — |
| Caravanserai | Wine | — |
| Rekem | — | — |
| Nubian Pyramids | Marble | — |
| Madghacen | Marble | Monumental Architecture |
| Throne of Almaqah | Marble | Monumental Architecture |

The High King's Hold technology observation belongs specifically to Getae in
the official requirements table. The Honga sample uses Ardiaei and does not
display that technology. Each Honga page is requested for the first faction in
the bundled building occurrence; this does not certify every faction variant.

For all 65 pages, the recognized direct wealth, wealth-percentage, tax, food
and public-order observations match the bundled raw effects in both directions.
The audit parser now recognizes `wealth from learning (culture)`, preventing
false omission reports for the two great libraries. This comparison checks
numeric facts; it does not validate every recipient scope or effect type.
Edict-conditional effects are retained as text and excluded from the direct
numeric comparison.

Honga exposes useful scope distinctions: Colosseum's entertainment wealth is a
building effect; its party influence is faction-wide. Caravanserai's trade
agreement tariff bonus is faction-wide. A public recurring-effect listing does
not identify the separate permanent trait awarded to the first builder.

## What still blocks inclusion

The [official construction manual](https://r2encv2.totalwar.com/en/manual/single-player/0045_enc_page_campaign_play_province_construction/index.html)
states that a legendary building can require a completed chain and a particular
event, and that its first builder receives a permanent faction trait. It does
not enumerate the individual conditions or caps.

A [public Assembly Kit schema at a pinned revision](https://github.com/bukowa/twr2docs/blob/aeaece2b77f5ae7f197cf14184a367ce58a6e4e9/r2docs/docs/database/assemblykit.md)
provides a concrete acquisition checklist:

| Rule | Required database evidence and campaign state |
| --- | --- |
| Unlock and construction eligibility | `building_levels.condition`, `resource_requirement`, required-technology junctions, and the current event/research/resource state |
| Uniqueness | Actual `faction_unique` values, `building_instance_key` → `building_instances.num_instances`, chain/superchain region caps, and existing instances where applicable |
| First-builder reward | `first_in_world_bundle` → effect bundle effects/scopes, acquisition and persistence semantics, and which faction already acquired it |
| Regional eligibility | `only_in_capital`, condition expressions, building-set inclusion/exclusion rows and campaign/startpos assignments, plus faction/culture variants |

The artifact retains the exact table and column names. The published schema is
**not a row export**: the existence of `faction_unique` does not prove that any
specific building sets it, and `num_instances` alone does not establish its
counting scope. Historical names such as Colosseum or Rekem also do not prove a
Rome-only or Petra-only restriction.

The three already-supported Marib Dam stages retain their Saba-only placement,
faction-wide farming modifier and per-dam maintenance accounting. This audit
does not change their rules.

## Replay and limitations

```sh
uv run --frozen python -m games.tw.rome2.audit_special_buildings
uv run --frozen python -m games.tw.rome2.audit_special_buildings --offline
uv run --frozen pytest tests/games/rome2/test_special_audit.py --no-cov
```

The refresh command writes the audit only; it never modifies catalog effects or
solver eligibility. Source responses are cached under `.cache/rome2-specials`.
Use a fresh `--cache` directory to retrieve a new snapshot; `--offline` replays
that directory. Failed retrieval or identity validation is recorded as an error
and replaces that page's prior observation rather than silently retaining it.

The sources have no installed-build identifier, so this is a reproducible public
reference audit for the bundled Grand Campaign roster, not a latest-patch
certificate. Original installed database/startpos rows, or a trustworthy public
export with a game-build identity, are still needed to close the four rule gaps
for each building before enabling it in joint optimization.
