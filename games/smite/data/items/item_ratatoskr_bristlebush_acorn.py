"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1350
Total Cost:	2050
Stats:	+45 Physical Power
+6% Movement Speed
+25% Critical Strike Chance
Passive Effect:	PASSIVE: Dart deals 40% increased damage and can Critically Strike. When Dart damages an enemy Ratatoskr gains 22.5% Physical Lifesteal and 25% Basic Attack damage for 6s.
"""

from games.smite.item import RatatoskrAcorn
from games.smite.spells import Buff

bristlebush_acorn = RatatoskrAcorn(
    name="Bristlebush Acorn",
    cost=2050,
    stats=Stats(
        power_physical=45,
        movement_speed=6,
        basic_attack_crit_rate=25
    )
)
