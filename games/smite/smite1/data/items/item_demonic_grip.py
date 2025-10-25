"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2300
Stats:	+75 Magical Power
+30% Attack Speed
Passive Effect:	PASSIVE - Your Basic Attacks reduce your target's Magical Protection by 10% for 3s (max 3 Stacks).
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

demonic_grip = Item(
    name='Demonic Grip',
    cost=2300,
    stats=Stats(
        power_magical=75,
        basic_attack_speed=30,
    )
)

item = demonic_grip
