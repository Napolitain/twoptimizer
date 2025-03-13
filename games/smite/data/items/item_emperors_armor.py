"""
Item Type:	Defensive, Utility
Item Tier:	Tier 3
Cost:	1000
Total Cost:	2250
Stats:	+50 Physical Protection
+250 Health
Passive Effect:	AURA - Damageable enemy structures within 55 units have their Attack Speed reduced by 30%.
Damageable allied structures within 55 units have their Attack Speed increased by 30%.
"""

from games.smite.item import Item
from games.smite.spells import Stats

emperors_armor = Item(
    name='Emperor\'s Armor',
    cost=2250,
    stats=Stats(
        prot_physical=50,
        hp=250
    )
)
