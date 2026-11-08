# HoI4 starting armies and production

`games.hoi4.data_pipeline.oob_resolution.resolve_starting_army` reads selected
country and order-of-battle (OOB) source documents. It now resolves the deployed
division roster and its full base requirements for France, Britain, the United
States, Germany, Italy, Japan, the Soviet Union and China. It also imports named
equipment variants, starting production declarations and stockpile-change
effects. These records are inputs to the starting-scenario work; they are not a
validated latest-patch campaign save.

The source is [the pinned public snapshot][snapshot], revision
`e249d22284449ece5416b41e68c4d73f2b79e3cc`. Its exact game patch remains unknown.
The requested target is the latest stable version recorded in the reference
manifest, with every catalogued gameplay DLC enabled. Supported official patch
overlays can be applied to the equipment/unit payload before resolving template
requirements. This does not establish that all changes between the snapshot and
the target have been applied.

## Implemented extraction

The caller supplies an explicit start date, known/enabled DLC identifiers and
the parsed country/OOB documents. An explicit `tutorial=False` selects normal
campaign setup, including Italy's production declarations. Without that context,
`is_tutorial` remains unknown. Unknown conditions containing relevant army
effects are reported; an unrelated conditional portrait does not prevent army
inspection. Scoped effects outside the supported interpreter remain visible.

Each deployed division links to one template by index, retains its declared
location, equipment/experience/manpower factors and forced equipment variants,
and records the source path, SHA-256 and line. Template requirements are
recomputed from the supplied unit definitions, rather than trusting an older
cached summary. A country/profile hash mismatch is rejected; a mismatched
template source cannot produce resolved requirements.

The report includes production from the separately selected land, air and naval
OOBs. France's selected land OOB has an unclosed final `instant_effect` parent.
Five individually balanced production children are recovered using their
original text and offsets, with `parent_incomplete=true` and the original file
hash. No missing brace is invented, and recovery does not certify that the
source's tail is complete.

## Documented semantics and unresolved defaults

The rules below come from the pinned [Country creation wiki mirror][creation],
particularly its division and equipment-production sections. The corresponding
[effects reference][effects] supplies stockpile-effect parameters. These are
versioned community documentation, not validation against the target executable.

| Field | Implemented interpretation |
| --- | --- |
| `start_equipment_factor` | An omitted factor defaults to 1. It controls equipment fill, independently of manpower. Spawned equipment is not subtracted from the country's reserve stockpile. |
| `start_experience_factor` | An omitted factor defaults to 0. The declaration is retained as a factor; it is not a claim that a new division has completed its training queue. |
| `start_manpower_factor` | An omitted factor does not mean a fully staffed division. Documentation says manpower is drawn from available reserves to the highest possible fill. Actual allocated manpower stays unknown until reserves and initialization order are resolved. |
| `force_equipment_variants` | The requested equipment type, owner, creator, variant name and optional amount are retained. An omitted creator defaults to the declared owner. A documented explicit amount leaves the rest of that archetype ungiven. |
| `requested_factories` | A request for military factories or dockyards. The documentation allows unmet requests to remain queued. It is not treated as an already assigned factory count. |
| Production `efficiency` | A declared percentage from 0 to 100, converted to a ratio by dividing by 100. |
| Production `progress` | A declared fraction of one completed equipment item. |
| Stockpile `producer` | Defaults to the current country only when absent. Applying the effect also requires equipment/producer eligibility; a declaration is not yet an effective stockpile total. |

Missing or duplicate production efficiency, progress and factory requests remain
unknown. Their defaults were not established by the referenced documentation.
Invalid or duplicate factor declarations are not replaced with an omitted-field
default. The separately documented `create_unit` effect has different edge-case
defaults; those are not transferred to initial OOB declarations.

Equipment targets are summed by archetype from each constituent unit's base
requirements. When scaling requires a fractional item, the affected archetype
remains unknown because rounding granularity has not been verified. Independent
integral archetypes remain available. Repeated forced variants for one archetype
and the interaction between a forced amount and a partial equipment factor also
remain unknown. Equipment identity, variant legality and technology eligibility
must still be resolved before treating a target as actual issued equipment.

Stockpile-change effects are listed separately from the equipment issued to
deployed units. An absent stockpile effect is not interpreted as an empty
reserve. The `starting_train_buffer` initialization rule is retained as an
unhandled army input; its generated quantity has not been established.

The pinned source's [supply defines][supply-defines] provide concrete evidence
against a blanket empty-reserves default: `DEFAULT_STARTING_TRUCK_RATIO = 1.5`
and `DEFAULT_STARTING_TRAIN_RATIO = 1` are commented as the initial buffers
relative to need. These are logistics inventory rules, not production-line
efficiency or division-training parameters. Country history additionally
declares `starting_train_buffer` as 2 for France, 4 for Britain, 5 for the
United States, 2 for Germany, 1.5 for Italy and 3 for the Soviet Union.
The exact relationship between this country field and the default ratio, the
need calculation, chosen equipment variant and integer rounding remain
unverified. No generated train or truck count is substituted for those missing
steps. China's and Japan's absent declarations do not establish zero trains.

`logistics_declarations` preserves selected train/truck-buffer and `set_convoys`
declarations with their literal values and source locations. These remain
separate from resolved inventory. The country-history validator in
[CWTools][history-schema] independently identifies `starting_train_buffer` as a
numeric country field but does not establish its conversion into equipment.
Targeted searches of this schema, the wiki and public source comments did not
establish a general initial-reserve baseline or fractional OOB issuance rule.
Those uncertainties therefore remain explicit rather than receiving guessed
rounding or zero values.

## Imported coverage

These are source results for `1936.1.1.12`, normal campaign, with all catalogued
gameplay DLC. Full manpower is the sum of deployed templates' requirements,
not the country's available manpower or proven initial staffing. Production
counts include land, air and naval lines.

| Country | Divisions | Templates | Production lines | Named variants | Full manpower requirement |
| --- | ---: | ---: | ---: | ---: | ---: |
| France | 74 | 8 | 22 | 35 | 579,000 |
| United Kingdom | 38 | 6 | 27 | 39 | 269,600 |
| United States | 36 | 5 | 23 | 40 | 345,100 |
| Germany | 30 | 5 | 21 | 28 | 269,600 |
| Italy | 46 | 14 | 16 | 30 | 264,000 |
| Japan | 60 | 8 | 39 | 56 | 489,100 |
| Soviet Union | 138 | 7 | 16 | 27 | 1,135,200 |
| China | 85 | 4 | 2 | 6 | 475,100 |

All these deployed templates have resolvable base requirements in the current
payload. France's full deployed force requires 56,130 infantry equipment,
420 artillery equipment, 950 support equipment, 1,320 light-tank chassis and
2,505 motorized equipment before equipment substitutions or other modifiers.
These are full requirements, not starting stockpiles. Actual starting manpower
allocation remains unresolved for all eight countries.

## API and verification

```python
resolve_starting_army(
    country_profile,
    equipment_payload,
    country_document,
    oob_documents,  # keyed by OOB name, without the .txt suffix
    selection_context,
    partial_effects=recovered_children_by_source_path,
    tutorial=False,
)
```

The result is caller-owned JSON-compatible data. `sources` identifies every
country/OOB input; template unit references carry their own source fingerprints.
`blockers`, `unhandled_army_effects`, per-division `unknowns` and per-line
`unknown_defaults` preserve distinct limitations.
`fully_resolved_starting_army` remains false. A missing land OOB produces unknown
aggregate requirements, not zero. A loaded source may still contain unresolved
conditional roster effects, which are reported as blockers.

The focused regression tests cover omitted versus invalid defaults, independent
equipment rounding, forced variants, source-hash mismatches, missing templates,
conditional units, tutorial guards, production units, stockpile effects and
recovery of balanced children from the incomplete French production parent.
The reproducible derived import is documented by
`python -m games.hoi4.data_pipeline.resolved_import --help`.

[snapshot]: https://github.com/BanderaModding/vanilla-fin-hoi4/tree/e249d22284449ece5416b41e68c4d73f2b79e3cc
[creation]: https://github.com/thelight0211/hoi4-wiki/blob/1477082f0088e228c26266ca08893890690ba43d/Country%20creation%20-%20Hearts%20of%20Iron%204%20Wiki.md
[effects]: https://github.com/thelight0211/hoi4-wiki/blob/1477082f0088e228c26266ca08893890690ba43d/Effects%20-%20Hearts%20of%20Iron%204%20Wiki.md
[supply-defines]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/defines/00_defines.lua#L4353-L4359
[history-schema]: https://github.com/cwtools/cwtools-hoi4-config/blob/297dd69c42aabe10078a8b7ab7f2d07ee631d4ef/Config/history/country_history.cwt#L28-L30
