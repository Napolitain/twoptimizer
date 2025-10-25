"""
Item Type:	Offensive, Utility
Item Tier:	Tier 3
Cost:	1200
Total Cost:	2600
Stats:	+70 Magical Power
+20 MP5
+20% Cooldown Reduction
Passive Effect:	PASSIVE - Every 10s the Pendant activates, subtracting 1s from all of your abilities currently on Cooldown. The initial countdown will not start until you leave the fountain.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

chronos_pendant = Item(
    name="Chronos Pendant",
    cost=2600,
    stats=Stats(
        power_magical=70,
        mp5=20,
        cdr=20
    )
)

item = chronos_pendant
