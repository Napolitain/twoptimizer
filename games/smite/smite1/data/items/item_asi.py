"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2400
Stats:	+35 Physical Power
+18% Physical Lifesteal
+20% Attack Speed
+10 Physical Penetration
Passive Effect:	PASSIVE - While below 60% Health, you gain an additional 22.5% Physical Lifesteal for 5 seconds. Can only occur once every 15 seconds.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

asi = Item(
    name='Asi',
    cost=2400,
    stats=Stats(
        power_physical=35,
        lifesteal_physical=18,
        basic_attack_speed=20,
        pen_flat=10
    )
)

item = asi
