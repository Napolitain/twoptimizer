import dataclasses

from games.smite.enums import PowerType
from games.smite.item import Build
from games.smite.spells import Spells


@dataclasses.dataclass
class StatCap:
    hp: float = 5500
    mana: float = 4000
    movement_speed: float = 1000
    basic_attack_sec: float = 2.5
    magical_power: float = 900
    magical_lifesteal: float = 70
    physical_power: float = 400
    physical_lifesteal: float = 80
    pen_flat: float = 50
    pen_percent: float = 40
    prot_physical: float = 325
    prot_magical: float = 325
    hp5: float = 100
    mp5: float = 100
    cdr: float = 40
    cc: float = 40


@dataclasses.dataclass
class God:
    name: str
    hp: float
    mana: float
    movement_speed: float
    basic_attack_range: float
    basic_attack_sec: float
    physical_power: float
    physical_power_scaling: float
    magical_power: float
    magical_power_scaling: float
    prot_physical: float
    prot_magical: float
    prot_mitigation: float
    hp5: float
    mp5: float
    cdr: float
    cc: float
    power_type: PowerType
    spells: Spells
    build: Build
    stat_cap: StatCap = StatCap()

    def get_hp(self) -> float:
        total_hp = self.hp
        if self.spells:
            total_hp += self.spells.passive.hp
            for spell in [self.spells.spell1, self.spells.spell2, self.spells.spell3, self.spells.spell4]:
                if spell.buff:
                    total_hp += spell.buff.hp
        return min(total_hp, self.stat_cap.hp)

    def get_dps_basic_attack(self) -> float:
        return self.physical_power * self.basic_attack_sec
