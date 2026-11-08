# HoI4 public reference data

The bundled public reference contains France, the United Kingdom, the United
States, Germany, Italy, Japan, the Soviet Union and China. It supports inspection
without an installed game. It is not an executable or validated campaign start.

The importer examined 1,081 state files and retained 487 records with an
unambiguous direct owner among those eight countries. It also extracted 308
equipment records, 157 unit definitions, 55 building definitions, 13 state
categories and 23 selected numeric defines. Country files contain candidate
1936 order-of-battle templates and production declarations where source syntax
permits. An optional separate `source_selection` records country-history
candidate declarations for the explicitly supplied date and DLC catalog.

## Provenance and target

The source is the public
[BanderaModding/vanilla-fin-hoi4 repository](https://github.com/BanderaModding/vanilla-fin-hoi4/tree/e249d22284449ece5416b41e68c4d73f2b79e3cc),
pinned to `e249d22284449ece5416b41e68c4d73f2b79e3cc` (20 August 2026).
The repository declares no license or exact game build. Its defines contain
`SAVE_VERSION = 33` with the inconsistent comment `1.17.0 (Case Green)`.
Its vanilla fidelity has not been independently validated.

The user-confirmed ruleset is the latest stable game with all gameplay DLC
enabled. The manifest records that request separately from its unresolved source
branches; recording the preference does not resolve or validate a campaign start.
On 8 November 2026, the official
[Steam announcement](https://steamcommunity.com/ogg/394360/announcements/detail/684142629662760620)
identifies version **1.19.4**, updated on 5 November with checksum **0bdb**.
This target is recorded separately from the unknown reference-source patch.
The importer does not claim that its August snapshot matches that November build.
See [the rules review](hoi4-rules-review.md) for mechanics evidence and pending
gameplay decisions.

A separate [pinned wiki mirror](https://github.com/CooderAtom/hoi4-zh-wiki/tree/9f15dbe333f50742f0afd075bcb5a69c7c2ff39c)
provides a useful crosscheck. Its country articles have mixed version coverage;
agreement does not certify a patch, and differences remain unresolved. The
following triples are civilian factories / military factories / dockyards:

| Country | Direct state declarations | Wiki industry table |
| --- | ---: | ---: |
| France | 35 / 8 / 11 | 33 / 8 / 11 |
| United Kingdom | 32 / 14 / 19 | 31 / 14 / 19 |
| United States | 129 / 10 / 22 | 128 / 10 / 22 |
| Germany | 35 / 28 / 10 | 35 / 28 / 10 |
| Italy | 21 / 20 / 15 | 21 / 20 / 15 |
| Japan | 26 / 16 / 15 | 24 / 16 / 14 |
| Soviet Union | 46 / 33 / 6 | 46 / 33 / 6 |
| China | 16 / 11 / 2 | 11 / 8 / 2 |

Only factual declarations, identifiers, locations and provenance are bundled;
the downloaded game-text tree remains outside the repository. Each referenced
input has its original byte SHA-256, including BOMs and line endings, in
`games/hoi4/data/public_reference/manifest.json`. The manifest records generated
artifact hashes and all extraction inputs.

## What the values mean

`literal_state_totals` adds the direct factory declarations in the base history
of states with an unambiguous direct owner. These counts are not usable civilian
construction capacity or a fully resolved 1936 snapshot. Consumer goods,
occupation, puppets, trade, laws, national spirits, power availability and
initialization effects can change effective capacity.

Country scripts, future dated history, DLC branches, building conditions and
other unexecuted statements retain source locations. Scalar declarations and
repeated entries retain their order. Equipment parent/archetype references are
preserved; costs and resource needs are not inherited or defaulted. Unit
training times are source facts rather than an implemented training formula.
Numeric defines are selected literal Lua assignments; Lua is not executed.
Ambiguous repeated or noninteger factory declarations prevent reporting that
factory category's total, instead of selecting an override or evaluating it.

The source's `FRA_1936.txt` and `FRA_1936_nsb.txt` both end with an unclosed
`instant_effect` block beginning at line 944. The importer preserves templates
and five complete production children in each file, marking those children
`parent_incomplete`. It never inserts closing braces, changes source hashes or
accepts an incomplete final child. Independent
[vanilla corpus tests](https://github.com/hagane-works/hagane-studio/blob/524f66cc9f2aee84f5791f8906582f4123e2fd4a/internal/hoi4/paradox/vanilla_corpus_test.go)
and [versioned parser corrections](https://github.com/zgavin/paradoxical/blob/9709805fb9ed44702d9b4b564e7e3c5644931cc3/lib/paradoxical/games/hoi4.rb)
document the same missing-brace anomaly in vanilla game files. Its presence
does not by itself establish corruption of this particular mirror.

The history selector uses three-valued logic: true, false or unknown. It handles
explicitly catalogued gameplay DLC, `always`, AND/OR/NOT, date comparisons and
dated history. As documented by the pinned wiki, NOT is NOR across its children,
and a dated history block applies only to strictly later starts. Unknown
conditions and mixed nested/adjacent alternatives remain blockers. Unknown
scopes and selected effects remain unexecuted source statements. Therefore even
a profile with no control-flow blockers is not a validated starting country.

## Rebuild

Obtain the public repository in a separate reference directory, then check out
the pinned revision. From this optimizer checkout:

```sh
git clone https://github.com/BanderaModding/vanilla-fin-hoi4.git /tmp/hoi4-reference
git -C /tmp/hoi4-reference checkout e249d22284449ece5416b41e68c4d73f2b79e3cc
uv run --frozen python -m games.hoi4.data_pipeline.public_import \
  --source-root /tmp/hoi4-reference \
  --output games/hoi4/data/public_reference \
  --start 1936.1.1.12 \
  --dlc-catalog games/hoi4/data/public_reference/dlc_catalog.json
```

The importer requires the pinned revision and rejects modified or untracked
`common`/`history` files. It performs no network requests. Rebuilding replaces
its generated profiles, equipment, buildings and manifest; the independently
maintained `rules_evidence.json` is preserved. Every generated file stays below
500 KiB; the equipment file uses compact JSON to keep all selected records.

Python consumers can use `load_reference_manifest()`, `load_reference_equipment()`
and `load_reference_country("FRA")` from
`games.hoi4.data_pipeline.public_import`. Each call returns caller-owned data.
