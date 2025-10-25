"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	900
Total Cost:	2300
Stats:	+50 Physical Power
+22.5% Physical Lifesteal
+15 Physical Penetration
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

devourers_gauntlet = Item(
    name='Devourer\'s Gauntlet',
    cost=2300,
    stats=Stats(
        power_physical=50,
        lifesteal_physical=22.5,
        pen_flat=15
    )
)

item = devourers_gauntlet
