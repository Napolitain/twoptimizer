import dataclasses


@dataclasses.dataclass
class Stats:
    power_magical: float = 0  # Power stat
    power_physical: float = 0
    basic_attack_damage: float = 0  # Basic Attack Damage stat
    basic_attack_speed: float = 0  # Basic Attack Speed stat
    basic_attack_crit_rate: float = 0  # Basic Attack Crit Rate stat (chance)
    basic_attack_crit_rate_multiplier: float = 0  # Basic Attack Crit Rate Multiplier stat (devoted deathbringer)
    basic_attack_crit_multiplier: float = 0  # Basic Attack Crit Multiplier stat (deathbringer)
    target_max_hp_magical_damage: float = 0  # Target's max HP magical damage stat (soul reaver)
    target_current_hp_magical_damage: float = 0  # Target's current HP magical damage stat
    target_max_hp_physical_damage: float = 0  # Target's max HP physical damage stat (qin's)
    target_current_hp_physical_damage: float = 0  # Target's current HP physical damage stat (Bluestone)
    pen_flat: float = 0
    pen_percent: float = 0
    lifesteal_physical: float = 0
    lifesteal_magical: float = 0
    prot_physical: float = 0
    prot_magical: float = 0
    movement_speed: float = 0
    hp: float = 0
    mana: float = 0
    shield: float = 0
    hp5: float = 0
    mp5: float = 0
    cdr: float = 0
    cc: float = 0


@dataclasses.dataclass
class Buff:
    name: str = ""
    duration: float = float('inf')  # TBD
    stats: Stats = Stats()


@dataclasses.dataclass
class Spell:
    name: str
    cooldown: float
    mana_cost: float
    range: float
    damage: float
    scaling: float
    buff: Buff = None


@dataclasses.dataclass
class Spells:
    passive: Buff
    spell1: Spell
    spell2: Spell
    spell3: Spell
    spell4: Spell
