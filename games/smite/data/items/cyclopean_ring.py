"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2600
Stats:	+60 Magical Power
+25% Attack Speed
+10% Cooldown Reduction
Passive Effect:	PASSIVE - Your next basic attack against an enemy god deals bonus Magical Damage equal to 9% of the target's maximum Health. This effect can only occur once every 8s, reduced by 2s for each successful Basic Attack on an enemy god.
"""

from games.smite.item import Item
from games.smite.spells import Buff

cyclopean_ring = Item(
    name='Cyclopean Ring',
    cost=2600,
    buff=Buff(
        power_magical=60,
        basic_attack_speed=25,
        cdr=10,
        target_max_hp_magical_damage=9
    )
)
