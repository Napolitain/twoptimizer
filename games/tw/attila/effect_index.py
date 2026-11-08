"""Per-economy resolved effects, indexed by their natural recipients.

An Economy is a compiled snapshot: its existing expression caches already assume
the sources are fixed for its lifetime. This index has the same ownership and
never shares mutable decisions or cached expressions between economies.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from games.tw.attila.effects import Reach, Rule

if TYPE_CHECKING:
    from games.tw.attila.economy import Economy


@dataclass(frozen=True, slots=True)
class ResolvedEffect:
    source: Any
    effect: str
    rule: Rule
    scope: Reach
    value: float


class EffectIndex:
    def __init__(self, economy: Economy):
        self.economy = economy
        self.by_kind = defaultdict(list)
        self.by_region = defaultdict(list)
        self.by_province = defaultdict(list)
        self.wealth = defaultdict(list)
        self.regions = {p.name: tuple(r.name for r in p.regions) for p in economy.provinces}
        for source in economy.sources:
            for effect, rule, scope, value in economy.effects(source):
                record = ResolvedEffect(source, effect, rule, scope, value)
                self.by_kind[rule.kind].append(record)
                recipients = self.recipients(record)
                for region in recipients:
                    self.by_region[region, rule.kind].append(record)
                    if rule.kind in ("wealth", "fertility_wealth"):
                        self.wealth[region].append(record)
                for province in dict.fromkeys(economy.owner[region] for region in recipients):
                    self.by_province[province, rule.kind].append(record)

    def recipients(self, record: ResolvedEffect) -> tuple[str, ...]:
        economy = self.economy
        source = record.source.region.name
        owner = economy.owner[source]
        mapping = economy.scenario.conditional_targets.get(record.effect)
        conditional_food = record.effect == "att_effect_food_production_fertility_neighbouring"
        if mapping is not None and (record.scope == Reach.CONDITIONAL or conditional_food):
            return self.province_regions(mapping.get(owner, ()))
        if conditional_food:
            return ()
        if record.scope in (Reach.BUILDING, Reach.LOCAL):
            return (source,)
        if record.scope == Reach.PROVINCE:
            return self.regions[owner]
        if record.scope == Reach.FACTION:
            return tuple(economy.owner)
        if record.scope == Reach.ADJACENT:
            return self.province_regions(economy.adjacency.get(owner, ()))
        return ()

    def province_regions(self, provinces) -> tuple[str, ...]:
        return tuple(region for name in dict.fromkeys(provinces) for region in self.regions[name])
