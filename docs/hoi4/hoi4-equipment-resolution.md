# HoI4 equipment economics

`equipment_resolution.resolve_equipment_catalog` resolves base IC costs and
production-resource declarations from source definitions. This is executable
resolution for ordinary equipment, rather than a dependency inventory. It does
not establish that the entire public snapshot matches the requested patch.

On the pinned public source, the reader finds 308 direct definitions and 34
duplicate-archetype declarations. Supported expansion adds 148 definitions for
456 equipment IDs. **440 have resolved base IC and resources**, 12 have partial
economics and four remain unresolved. This includes modular chassis/airframes;
their resolved base costs are not the cost of a completed designer variant.

| Equipment | Base IC | Production resources |
| --- | ---: | --- |
| `infantry_equipment_0` | 0.43 | 2 steel |
| `infantry_equipment_1` | 0.50 | 2 steel |
| `support_equipment_1` | 4.00 | 1 aluminium, 2 steel |
| `artillery_equipment_1` | 3.50 | 1 tungsten, 2 steel |
| `light_tank_chassis_1` | 2.35 | 1 steel, before designer effects |
| Generated `small_plane_cas_airframe_1` | 5.00 | 3 aluminium, 1 rubber, before designer effects |

## Inheritance and generation rules

The pinned [Equipment modding revision][inheritance] describes `archetype` as the
source of inherited general attributes. `parent` identifies the superseded
equipment. Therefore missing costs/resources inherit through the archetype,
without falling back to a predecessor's changed cost or resources. Explicit
local values take precedence. Missing root values remain unknown, while an
explicit empty resource declaration is retained as empty.

Partial resource-map overriding is not established by that documentation. A
local map omitting a known inherited nonzero resource remains unresolved; the
resolver does not guess whether the omitted resource disappears. Invalid or
ambiguous values and inheritance cycles also remain explicit.

The source [duplicate-archetype comments][duplicates] document copying the
source archetype and its derived types, excluding alias/type/variant names.
The resolver generates declared families using their source ID relationship,
honors `only_duplicate_archetype`, and keeps source provenance. `for_each`
applies to derived types rather than their archetype. Non-economic transformations
such as hardness or variant display names do not change base IC/resources;
unsupported economic transformations block the affected field. Definitions that
collide are diagnosed instead of choosing a load-order winner.

Module-slot inheritance is distinct. [Source documentation][documentation]
describes parent-based module-slot inheritance and matching module-count-limit
overrides. The resolver marks equipment that requires a designer variant;
that marker does not validate its slot layout, module eligibility or unlocks.

## Input and result APIs

```python
from games.hoi4.data_pipeline.equipment_sources import read_equipment_resolution_inputs
from games.hoi4.data_pipeline.equipment_resolution import resolve_equipment_catalog
from games.hoi4.data_pipeline.patch_overlay import apply_patch_overlays

inputs = read_equipment_resolution_inputs("/path/to/pinned/source")
inputs, patch_report = apply_patch_overlays(inputs)
catalog = resolve_equipment_catalog(inputs)
```

The reader returns ordinary definitions, duplication details, 312 module
definitions, 37 upgrade definitions and 225 direct technology-unlock records
from the reviewed snapshot. It preserves repeated stat blocks. Its `input_sources`
contains exact fingerprints for the 65 files read or used as source documentation.
The surrounding import pipeline validates the checkout revision; this reader
does not label an arbitrary directory as the pinned public revision.

Catalog rows contain `id`, `archetype_id`, `predecessor_id`, `status`, `base_cost_ic`, `base_resources`,
`requires_variant`, `field_sources`, `unknowns` and `unlocked_by`. Each resolved
field retains its source file/hash/line and any guarded patch-overlay evidence.
Unlock records identify technology relationships; they do not imply that a
country has researched them or passes other availability conditions.

`resolve_equipment_variant(catalog, variant, module_records=..., upgrade_records=...)`
accepts the named-variant records produced by OOB resolution. Cosmetic variants
of fully resolved nonmodular equipment can retain their base economics. Designer
variants expose the base plus selected module/upgrade economic declarations,
including patched values and repeated modifier blocks.

Upgrade inputs also retain `add_stats`, `multiply_stats` and complete
`resource_cost_thresholds` maps. Each selected upgrade exposes `selected_effects`:
the validated level and highest applicable source threshold, with field evidence.
The [land-upgrade source][upgrades] explicitly identifies these maps as total
added resource costs, rather than cumulative costs. Thus the armor upgrade's
level-10 threshold selects one steel; it does not sum the level-5 and level-10
maps into two steel. Invalid levels, missing/ambiguous maximum levels and duplicate
threshold levels remain diagnostic. A missing applicable threshold stays null;
this field is a selected input, not a completed variant resource requirement.

The inspected sources establish additive and multiplicative modifier declarations,
but not a complete target-version rule for their combined order, resource
adjustments, clamping and rounding. Designer `variant_cost_ic` and
`variant_resources` therefore remain null when those operations are needed.
Country and industrial-organization modifiers, variant legality and technology
eligibility remain separate. In particular, the resolver never silently quotes
a bare chassis cost as the cost of an equipped tank.

The remaining dependency is a version-matched designer evaluation rule or
validation fixture covering additive IC with multiple percentage modifiers,
upgrade IC, inherited/default module slots and fixed-point rounding. The source
declarations alone cannot distinguish the possible evaluation orders. Research
on November 8, 2026 did not establish that rule from the reviewed documentation;
no external calculator's formula has been adopted as an engine guarantee.
Upgrade XP cost and conversion/refit cost are separate from manufacturing IC.

[inheritance]: https://hoi4.paradoxwikis.com/index.php?title=Equipment_modding&oldid=104717
[duplicates]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/units/equipment/x_tank_chassis.txt
[documentation]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/units/equipment/_documentation.md
[upgrades]: https://github.com/BanderaModding/vanilla-fin-hoi4/blob/e249d22284449ece5416b41e68c4d73f2b79e3cc/common/units/equipment/upgrades/land_upgrades.txt#L68
