"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1050
Total Cost:	2350
Stats:	+30 Physical Power
+20% Attack Speed
+20% Critical Strike Chance
Passive Effect:	PASSIVE - Your next basic attack on an enemy god creates a deployable that, when picked up, provides you with 2% Movement Speed and 10% Critical Strike Chance for 10s. This effect stacks up to 3 times and can only occur once every 2 seconds.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

bladed_boomerang = Item(
    name="Bladed Boomerang",
    cost=2350,
    stats=Stats(
        power_physical=30,
        basic_attack_speed=20,
        basic_attack_crit_rate=20
    )
)

item = bladed_boomerang
