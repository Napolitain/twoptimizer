# HoI4 source ingestion

`games.hoi4.data_pipeline` inspects exported Clausewitz text without running game
scripts. It supports the bundled legacy files and local exports of installed or
publicly sourced data. Importing syntax does not establish complete game data or
an executable model. Hourly gameplay rules are configured separately.

```sh
uv run --frozen python -m games.hoi4.data_pipeline games/hoi4/data \
  --output /tmp/hoi4-source-inventory.json
```

For a known source revision, supply `--origin-url`, `--revision`, and optionally
`--retrieved-at-utc`. Supply `--game-build` only when the source establishes it;
the tool leaves unknown metadata null. It performs no network requests or source
updates. Output is deterministic for identical bytes and provenance arguments.

The report records every file's relative path, exact byte SHA-256, size, category,
BOM presence, parse status, and relevant source locations. Its aggregate source
hash includes relative paths and byte hashes. UTF-8 decoding is strict. Syntax
and encoding failures remain explicit, and the command exits with status 1 after
writing the report if either occurs. Unsupported extensions are inventoried but
not parsed; read/write errors fail with status 2. These statuses concern source
inspection only, never gameplay coverage or feasibility.

Coverage includes source categories, parsed record counts, missing categories,
and zero executed effects. Building, state-category, idea and focus records
expose selected direct source fields without applying defaults. Conditions,
effects, variables, DLC selection, repeated definitions and load-order overrides
are not evaluated. Unhandled record fields retain locations in the hashed
source. Focus prerequisite groups retain their ordered syntax independently;
they are not converted into an AND/OR gameplay decision.

The `parse_script`, `parse_bytes` and `parse_file` APIs return immutable Documents
with the original text. Blocks hold ordered entries; repeated keys remain
separate, comparison operators remain distinct from assignments, list entries
remain unkeyed, and empty braces remain ambiguous. Values retain strings,
variables, inline expressions and tagged blocks. Character spans select exact
source fragments; line and column numbers are one based. `syntax_record`
serializes this structure as ordered JSON-safe records. `Atom.literal()` only
decodes scalar syntax; dates and variable/expression text stay unresolved.

The legacy `FocusParser` now uses this parser boundary so separate focus blocks
are not merged into invented focus IDs. Its `documents` dictionary retains the
ordered source. Its old Focus models still flatten prerequisites and retain old
numeric defaults; that compatibility view must not drive hourly planning or
claim that conditions or effects were executed.

The original bundled directory contains buildings, state categories, ideas and
focuses only. It does not establish starting countries/states, equipment,
technologies or defines. A syntax scan also reports unclosed blocks in the
bundled `ideas/SOV.txt`, `ideas/persia.txt` and `ideas/switzerland.txt`; ingestion
does not silently repair those snapshots. A public reference import or an
installed export must carry its own provenance and coverage separately.
