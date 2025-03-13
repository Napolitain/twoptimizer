"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2700
Stats:	+95 Magical Power
+25 MP5
+10 Magical Penetration
+6% Movement Speed
Passive Effect:	PASSIVE - Killing or assisting an enemy minion provides you with 1 stack, granting 1% Movement Speed and 4 Magical Power per stack. Stacks last for 15s and stack up to 5 times. Enemy gods provide 5 stacks.
Stacks up to 20 magical power and 5% movement speed.
Each stack gained refreshes the duration, even at full stacks.
"""

from games.smite.item import Item
from games.smite.spells import Stats

doom_orb = Item(
    name="Doom Orb",
    cost=2700,
    stats=Stats(
        power_magical=95,
        mp5=25,
        pen_flat=10,
        movement_speed=6
    )
)

item = doom_orb
