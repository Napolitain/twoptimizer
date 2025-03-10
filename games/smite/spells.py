import dataclasses


@dataclasses.dataclass
class Buff:
    name: str
    duration: float = float('inf')
    power: float = 0
    power_scaling: float = 0
    pen_flat: float = 0
    pen_percent: float = 0
    lifesteal: float = 0
    physical_prot: float = 0
    magical_prot: float = 0
    hp: float = 0
    mana: float = 0
    shield: float = 0
    hp5: float = 0
    mp5: float = 0


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
