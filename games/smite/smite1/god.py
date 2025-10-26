from __future__ import annotations

import dataclasses

from games.smite.smite1.enums import PowerType, Damage
from games.smite.smite1.item import Build
from games.smite.smite1.spells import Spells, Stats


@dataclasses.dataclass
class Limits:
    hp_limit: float = 5500
    mana_limit: float = 4000
    movement_speed_limit: float = 1000
    basic_attack_damage_limit: float = 10000
    basic_attack_sec_limit: float = 2.5
    power_magical_limit: float = 900
    lifesteal_magical_limit: float = 70
    power_physical_limit: float = 400
    lifesteal_physical_limit: float = 80
    pen_flat_limit: float = 50
    pen_percent_limit: float = 40
    prot_physical_limit: float = 325
    prot_magical_limit: float = 325
    hp5_limit: float = 100
    mp5_limit: float = 100
    cdr_limit: float = 40
    cc_limit: float = 40


@dataclasses.dataclass
class God:
    name: str
    basic_attack_scaling = 100
    stats: Stats
    power_type: PowerType
    spells: Spells
    build: Build
    limits: Limits = dataclasses.field(default_factory=Limits)

    def get_hp(self) -> float:
        total_hp = self.stats.hp
        if self.spells:
            total_hp += self.spells.passive.stats.hp
            for spell in [self.spells.spell1, self.spells.spell2, self.spells.spell3, self.spells.spell4]:
                if spell.buff:
                    total_hp += spell.buff.stats.hp
        return min(total_hp, self.limits.hp_limit)

    def get_effective_hp_physical(self) -> float:
        return self.get_hp() * (1 + self.stats.prot_physical / 100)

    def get_effective_hp_magical(self) -> float:
        return self.get_hp() * (1 + self.stats.prot_magical / 100)

    def get_basic_attack_damage(self) -> Damage:
        """Calculate basic attack damage including items from build."""
        # Add power from build items if build exists
        total_power = self.stats.power_physical
        if self.build:
            for item in [self.build.item1, self.build.item2, self.build.item3, 
                        self.build.item4, self.build.item5, self.build.item6]:
                if item and item.stats:
                    if self.power_type == PowerType.PHYSICAL:
                        total_power += item.stats.power_physical
                    else:
                        total_power += item.stats.power_magical
        
        damage_value = self.stats.basic_attack_damage + (self.basic_attack_scaling / 100) * total_power
        
        if self.power_type == PowerType.PHYSICAL:
            return Damage(
                basic_physical=min(damage_value, self.limits.basic_attack_damage_limit))
        else:
            return Damage(
                basic_magical=min(damage_value, self.limits.basic_attack_damage_limit))

    def get_dps_basic_attack(self) -> float:
        """Calculate DPS including items from build."""
        # Add attack speed from build items if build exists
        total_attack_speed = self.stats.basic_attack_speed
        if self.build:
            for item in [self.build.item1, self.build.item2, self.build.item3, 
                        self.build.item4, self.build.item5, self.build.item6]:
                if item and item.stats:
                    total_attack_speed += item.stats.basic_attack_speed / 100
        
        total_attack_speed = min(total_attack_speed, self.limits.basic_attack_sec_limit)
        
        damage = self.get_basic_attack_damage()
        if self.power_type == PowerType.PHYSICAL:
            return damage.basic_physical * total_attack_speed
        else:
            return damage.basic_magical * total_attack_speed

    def get_time_to_kill(self, dps_function: callable, target: God) -> float:
        return target.get_hp() / dps_function()
