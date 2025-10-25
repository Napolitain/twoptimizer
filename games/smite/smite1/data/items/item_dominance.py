"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1300
Total Cost:	2500
Stats:	+40 Physical Power
+200 Mana
+20 MP5
+20% Attack Speed
Passive Effect:	PASSIVE - Your Basic Attacks benefit from an additional 20% Physical Penetration.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

dominance = Item(
    name='Dominance',
    cost=2500,
    stats=Stats(
        power_physical=40,
        mana=200,
        mp5=20,
        basic_attack_speed=20,
        pen_percent=20
    )
)

item = dominance
