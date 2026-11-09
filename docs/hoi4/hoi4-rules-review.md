# HoI4 rules and source review

The target is the latest stable game with **all gameplay DLC enabled**:
**1.19.4, November 5, 2026 hotfix,
checksum `0bdb`**, checked on November 8, 2026. The original patch shipped on
October 27. This identifies the target; it does not establish that the imported
reference data already matches that version.

The [official patch announcement][patch] and [Steam news API][news] establish
the release and hotfix dates. The newer November 3 announcement is a development
diary. The [October energy announcement][beta] explicitly describes an open beta;
its proposed power plants are not adopted as stable mechanics. Localized search
snippets gave inconsistent older patch labels, so the release check uses the
official announcement body and chronological feed.

## Evidence and limits

[Rules evidence][evidence] contains 21 sourced observations, 75 numerical
constant observations, original wiki revision IDs, pinned mirror commits, source
file hashes and line numbers. It contains no raw game files or copied wiki pages.
It is reference evidence, not an executable rules profile or optimizer defaults.

The [DLC catalog][dlc-catalog] records 16 gameplay pack identifiers with official
store or announcement evidence and exact script occurrences. The all-gameplay
profile enables these known identifiers; an unknown identifier remains unknown.
It distinguishes packs included with a base purchase from confirmed technical
integration into the base game.

The [public game-data mirror][raw] has an unverified patch identity. Its August
2026 commit predates the selected target. The [wiki mirror][wiki] preserves
original page revisions, but the pages have different ages and explicitly
outdated sections. For example, Production describes coal-era output while
Defines still lists pre-coal values. A successful import therefore proves
structural readability, not compatibility with the target patch.

## Documented mechanics

These observations guide implementation review. Except for the separately
documented calendar behavior, their complete behavior on the target release
still requires validation against matching game data or in-game measurements.

| Area | Publicly documented behavior | Remaining validation |
| --- | --- | --- |
| Calendar | No leap days; the [Event modding page][calendar] explicitly excludes them when calculating event dates. | Hourly subsystem update order is a separate question. |
| Construction | Civilian factory costs 10,800 IC; military factory 7,200; infrastructure 6,000. At most 15 civilian factories work on one project. | State slots, building flags, modifiers and completion overflow. |
| Infrastructure | For affected buildings, the default multiplier is `1 + 0.2 × infrastructure level`. | Exceptions by building type; modifier ordering. |
| Power | The raw mirror and wiki give civilian output of 4 IC/day unpowered or 5 powered; military output is 3.5 or 4.5. Developer explanations document interpolation and modifier scaling. | Complete target-patch demand accounting and conflicting historical coefficients. |
| Efficiency | Base start 10%, cap 50%; documented daily gain is `0.001 × cap² / current efficiency`. Each factory slot retains its own efficiency. | Growth modifiers, inactive slots, exact engine cadence and rounding. Hourly integration is approved provisionally. |
| Switching equipment | Retention depends on variant, family and generation relationships; starting efficiency is a floor. | Variant-change exceptions, designer DLC and exact equipment relationships. |
| Resources | Resources flow into production instead of accumulating as stockpiles; fuel is separate. Priority and cumulative shortages affect individual factories. | Exact allocation order and rounding. |
| Trade | A normal import spends one civilian factory for up to eight resource units; partial blocks still cost one factory. | Subject rates, export laws, supplier limits, convoys and access. |
| Recruitment capacity | Base concurrent training manpower cap is `max(100000, 0.75 × fielded manpower)`. | Target-patch modifiers and interaction with deployment. |
| Templates | Equipment and manpower requirements sum; base training duration uses the slowest constituent battalion or company. | Conditional templates, allowed equipment and training modifiers. |
| Training progress | Training can overlap equipment delivery and has a progress cap related to equipment availability, corroborated by the mirrored game UI. | Exact equipment weighting, manpower gate, update cadence and delivery timing. |
| Training level | The cited base rules produce **Trained** after recruitment training. Field exercises can reach **Regular** and consume equipment. | Applicable experience modifiers and scenario readiness conditions. |
| Manpower | Free manpower differs from potential recruitable population; mobilization takes time. | Country setup, conscription changes and competing demands. |

The [official consumer-goods developer diary][consumer-goods] documents two
distinct operations: add the expected-consumption modifiers, then multiply by
each individual consumer-goods factor. Apply the minimum percentage and round
the resulting factory count down. The raw mirror contains a 10% minimum fraction
and an absolute minimum of one factory; their complete interaction and the
accounting of traded, damaged, occupied and subject factories need validation.
Adding the factor modifiers together would not reproduce this rule.

The documented nonlinear efficiency curve requires explicit treatment of update
cadence. Dividing a daily nonlinear increment by 24 is not, by itself, evidence of
the game's exact hourly behavior. The user-approved hourly resolution remains
the target while these engine details are resolved. The user has approved hourly
integration of this documented curve as an explicit provisional approximation.

## Follow-up findings and concrete gaps

Energy has stronger publisher evidence than the initial wiki summary. The
[June 2025 Thermodynamics diary][thermodynamics] explains that half the required
energy gives halfway between unpowered and fully powered base output. The
[November 19 launch-eve diary][energy-launch] adds a second effect: shortages
scale the relevant **sum** of output or construction-speed modifiers when that
sum is positive. A nonpositive sum avoids this additional scaling. Interpolating
only base IC would therefore omit a documented effect.

These are historical developer explanations, not a validated complete 1.19.4
equation. The launch-eve diary illustrates military output of 4.0 to 4.5, whereas
the later raw mirror and wiki give 3.5 to 4.5. The discrepancy remains visible in
the evidence. [Released patch 1.17.2][energy-patch-172] introduced a consumption
cap, reduced the scaling contribution of export-earned factories, and removed
the penalty when energy demand is zero. It also added two mutually exclusive
state buildings affecting energy use or resource extraction. [Patch 1.17.4][energy-patch-174]
raised the cap from 6 to 6.6. Those changes make the original launch description
insufficient for current demand accounting.
Current coal coefficients and unresolved energy accounting must be explicit
profile inputs or overrides. The older numerical observations do not become
silent defaults for the selected target patch.

The [2017 publisher diary][efficiency-change] confirms that production efficiency
changed from linear to nonlinear growth. Mirrored UI labels describe daily gain;
they do not establish whether the underlying update occurs hourly or daily.
One player report suggests midnight production updates, but it is retained only
as a validation lead. The approved hourly timeline can represent daily events;
the provisional hourly efficiency integration does not establish that the game
updates every subsystem fractionally each hour.

Three details remain unresolved after targeted searches and the publisher
announcement archive:

- **Recruitment arithmetic:** UI text confirms an equipment-dependent training
  cap, but does not identify the weighting across equipment types or manpower.
  The user approved a conservative fully-equipped-before-start gate for the
  provisional model. It removes the documented overlap and may reject plans
  that the game could complete.
- **Production cadence:** exact efficiency/output ordering, rounding and effects
  of intraday reallocation need observation on the target build.
- **Construction completion:** no authoritative statement found establishes
  whether excess IC carries forward or is discarded, or when new factories
  become available.

The JSON records focused validation probes for these cases. Installed files can
resolve data identity and modifiers; engine behavior may still require an
in-game comparison. These gaps remain explicit. The approved provisional
efficiency and recruitment rules allow implementation to proceed without
claiming exact engine equivalence; construction overflow remains unresolved.

## Model decisions

The agreed objective is to meet equipment and fully equipped, trained division
deadlines using specified templates, then maximize civilian construction
capacity **at the final deadline**. There is no secondary objective to delay
military spending. Equipment targets are reserve stockpiles **in addition to**
equipment issued to the required divisions; issued equipment cannot count
toward both requirements. The latest stable version is selected.

The approved first optimizer chooses construction, production allocation and
recruitment while following a supplied, dated research, national-focus and law
plan. Research optimization is deferred. Other inputs still need explicit
definitions: concrete deadlines, templates and reserve targets; treatment of
existing army deficits; and the exact measure of civilian construction capacity.
Trade availability and national
modifiers must also be represented explicitly before a result can claim to
satisfy them. Hourly efficiency integration and fully-equipped-before-training
are approved provisional approximations. Other unverified engine timing and
shortage formulas remain separate from those approvals.

Missing mechanics must appear in coverage diagnostics. Neither the public
snapshot nor the reference simulator establishes a complete, validated France
campaign model on its own.

[patch]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1847286114049046
[news]: https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=394360&count=100&maxlength=0&feeds=steam_community_announcements&format=json
[beta]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1846018067926058
[evidence]: ../games/hoi4/data/public_reference/rules_evidence.json
[dlc-catalog]: ../games/hoi4/data/public_reference/dlc_catalog.json
[raw]: https://github.com/BanderaModding/vanilla-fin-hoi4/tree/e249d22284449ece5416b41e68c4d73f2b79e3cc
[wiki]: https://github.com/CooderAtom/hoi4-zh-wiki/tree/9f15dbe333f50742f0afd075bcb5a69c7c2ff39c
[calendar]: https://hoi4.paradoxwikis.com/index.php?title=Event_modding&oldid=102070
[consumer-goods]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/5124584051966124338
[thermodynamics]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1803527891506227
[energy-launch]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1816849002007641
[energy-patch-172]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1818118366172856
[energy-patch-174]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/1825093633185039
[efficiency-change]: https://steamstore-a.akamaihd.net/news/externalpost/steam_community_announcements/4249665521683217168
