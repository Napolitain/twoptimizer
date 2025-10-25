"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	950
Total Cost:	2400
Stats:	+45 Physical Power
+15 Physical Penetration
Passive Effect:	PASSIVE - Enemies hit by your Abilities have 40% reduced healing for 5 seconds. Getting a kill or assist on an enemy god creates a field that lasts 10s, providing allies within it 20 Power + 2 Per level. This effect can only occur once every 10 seconds.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

brawlers_beat_stick = Item(
    name="Brawler's Beat Stick",
    cost=2400,
    stats=Stats(
        power_physical=45,
        pen_flat=15
    )
)

item = brawlers_beat_stick
