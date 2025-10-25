"""
Item Type:	Offensive
Item Tier:	Tier 3
Cost:	1100
Total Cost:	2450
Stats:	+75 Magical Power
+15 Magical Penetration
Passive Effect:	PASSIVE - Enemies hit by your abilities have 40% reduced healing for 5 seconds. Your next successful damaging ability on an enemy triggers a chain lightning, damaging the target and up to 4 nearby enemies for 40 damage + 10% of your Magical Power. This can only occur once every 20 seconds.
"""

from games.smite.smite1.item import Item
from games.smite.smite1.spells import Stats

divine_ruin = Item(
    name="Divine Ruin",
    cost=2450,
    stats=Stats(
        power_magical=75,
        pen_flat=15
    )
)

item = divine_ruin
