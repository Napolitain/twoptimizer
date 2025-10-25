from __future__ import annotations

import dataclasses
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.smite.smite1.god import God


class PowerType(Enum):
    PHYSICAL = 1
    MAGICAL = 2


@dataclasses.dataclass
class Damage:
    basic_physical: float = 0
    basic_magical: float = 0
    ability_magical: float = 0
    ability_physical: float = 0
    true: float = 0

    def get_damage(self, source_god: God, target_god: God):
        # Actual protections = (Protection × (1-%Reduction) - Flat Reduction) × (1-%Pen) - Flat Pen
        prot_physical = (target_god.prot_physical * (1 - 0) - 0) * (1 - target_god.pen_percent) - target_god.pen_flat
        prot_magical = (target_god.prot_magical * (1 - 0) - 0) * (1 - target_god.pen_percent) - target_god.pen_flat
        # Damage = (100 × Unmitigated Damage)/(Protections + 100)
        damage_basic_physical = (100 * self.basic_physical) / (target_god.prot_physical + 100 - source_god.pen_flat)
        damage_ability_physical = (100 * self.ability_physical) / (target_god.prot_physical + 100 - source_god.pen_flat)
        damage_basic_magical = (100 * self.basic_magical) / (target_god.prot_magical + 100 - source_god.pen_flat)
        damage_ability_magical = (100 * self.ability_magical) / (target_god.prot_magical + 100 - source_god.pen_flat)
        damage_true = self.true
        # Return the sum of all damages multiplied by the target's mitigation (which reduces even true damage!)
        return (
                damage_basic_physical + damage_ability_physical + damage_basic_magical + damage_ability_magical + damage_true) * (
                1 - target_god.prot_mitigation)
